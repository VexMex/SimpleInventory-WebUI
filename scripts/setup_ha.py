#!/opt/simpleinventory-webui/venv/bin/python
"""Manual HA setup and restart-safe, read-only connection check."""
from __future__ import annotations
import argparse
import asyncio
import getpass
import json
import logging
import os
from pathlib import Path
import re
import stat
import sys
import subprocess
import tempfile
import warnings
from urllib.parse import urlsplit, urlunsplit
from websockets.asyncio.client import connect

CONFIG = Path("/etc/simpleinventory-webui/app.env")
FIELDS = {"HA_URL", "HA_TOKEN", "SIW_INVENTORY_ID", "HA_ALLOW_HTTP"}
LOG = logging.getLogger("simpleinventory.private_transport")
LOG.addHandler(logging.NullHandler())
LOG.propagate = False
LOG.setLevel(logging.CRITICAL + 1)

class SetupError(Exception):
    """Safe message only: never include remote payloads or credentials."""

def normalize_url(value):
    if not isinstance(value, str) or re.search(r"[\s\\\"'<>]", value):
        raise SetupError("Ungueltige HA-Adresse.")
    try:
        url = urlsplit(value)
        port = url.port
    except ValueError:
        raise SetupError("Ungueltige HA-Adresse.") from None
    if (url.scheme not in {"https", "http"} or not url.hostname
            or url.username is not None or url.password is not None
            or url.query or url.fragment or ".." in url.path.split("/")):
        raise SetupError("HA-Adresse muss http(s) ohne Zugangsdaten oder URL-Parameter sein.")
    return urlunsplit((url.scheme, url.netloc, url.path.rstrip("/"), "", ""))

def validate(values):
    if set(values) != FIELDS:
        raise SetupError("Konfiguration ist unvollstaendig oder enthaelt unbekannte Felder.")
    result = dict(values)
    result["HA_URL"] = normalize_url(result["HA_URL"])
    if not re.fullmatch(r"[A-Za-z0-9_.-]{20,8192}", result["HA_TOKEN"]):
        raise SetupError("Tokenformat ungueltig; langlebigen HA-Zugriffstoken verwenden.")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", result["SIW_INVENTORY_ID"]):
        raise SetupError("Ungueltige Inventar-ID.")
    if result["HA_ALLOW_HTTP"] not in {"true", "false"}:
        raise SetupError("Ungueltige Transporteinstellung.")
    if result["HA_URL"].startswith("http://") and result["HA_ALLOW_HTTP"] != "true":
        raise SetupError("Unverschluesseltes HTTP wurde nicht freigegeben.")
    return result

def load_config(path=CONFIG):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "r", encoding="utf-8") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o600:
                raise SetupError("Konfigurationsdatei muss root gehoeren und Modus 0600 haben.")
            values = {}
            for line in stream:
                line = line.rstrip("\n")
                if not line or line.startswith("#"):
                    continue
                key, sep, value = line.partition("=")
                if not sep or key in values:
                    raise SetupError("Konfigurationsdatei ist ungueltig.")
                values[key] = value
        return validate(values)
    except SetupError:
        raise
    except (OSError, UnicodeError):
        raise SetupError("Private Konfiguration fehlt oder ist nicht sicher lesbar.") from None

def save_config(values, path=CONFIG):
    values = validate(values)
    directory = path.parent
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0:
        raise SetupError("Privater Konfigurationsordner ist nicht sicher.")
    os.chmod(directory, 0o700)
    if path.exists() or path.is_symlink():
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0:
            raise SetupError("Vorhandene Konfiguration ist nicht sicher ersetzbar.")
    fd, temporary = tempfile.mkstemp(prefix=".app-", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            os.fchmod(stream.fileno(), 0o600)
            for key in sorted(FIELDS):
                stream.write(f"{key}={values[key]}\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        dfd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

async def receive(ws):
    message = json.loads(await ws.recv())
    if not isinstance(message, dict):
        raise SetupError("Unerwartete Antwort von Home Assistant.")
    return message

async def request(ws, number, command, **kwargs):
    await ws.send(json.dumps({"id": number, "type": command, **kwargs}))
    for _ in range(20):
        result = await receive(ws)
        if result.get("id") == number:
            if result.get("type") != "result" or result.get("success") is not True:
                raise SetupError("API-Abfrage abgewiesen. Integration und Benutzerrechte pruefen.")
            return result.get("result")
    raise SetupError("Keine passende API-Antwort erhalten.")

async def query(base, credential, inventory=None):
    """Only authenticate, discover sensors and read items; never mutate inventory."""
    url = urlsplit(normalize_url(base))
    endpoint = urlunsplit(("wss" if url.scheme == "https" else "ws",
                          url.netloc, url.path + "/api/websocket", "", ""))
    try:
        async with asyncio.timeout(25):
            async with connect(endpoint, proxy=None, open_timeout=10, close_timeout=3,
                               max_size=8 * 1024 * 1024, logger=LOG) as ws:
                if (await receive(ws)).get("type") != "auth_required":
                    raise SetupError("Kein HA-WebSocket-Endpunkt.")
                await ws.send(json.dumps({"type": "auth", "access_token": credential}))
                if (await receive(ws)).get("type") != "auth_ok":
                    raise SetupError("Anmeldung abgelehnt. Token und HA-Benutzer pruefen.")
                if inventory is not None:
                    result = await request(ws, 1, "simple_inventory/list_items",
                                           inventory_id=inventory)
                    if not isinstance(result, dict) or not isinstance(result.get("items"), list):
                        raise SetupError("Simple Inventory liefert keine gueltige Artikelliste.")
                    return len(result["items"])
                states = await request(ws, 1, "get_states")
                if not isinstance(states, list):
                    raise SetupError("Inventare konnten nicht ermittelt werden.")
                inventories = {}
                for state in states:
                    if not isinstance(state, dict):
                        continue
                    attrs = state.get("attributes", {})
                    if not isinstance(attrs, dict):
                        continue
                    key = attrs.get("inventory_id")
                    if (isinstance(key, str) and "total_items" in attrs
                            and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", key)):
                        name = str(attrs.get("friendly_name", state.get("entity_id", key)))
                        # Server-provided text cannot inject terminal control characters.
                        inventories[key] = re.sub(r"[\x00-\x1f\x7f-\x9f]", "?", name)[:100]
                if not inventories:
                    raise SetupError("Kein Inventar gefunden. Simple Inventory in HA einrichten.")
                return list(inventories.items())
    except SetupError:
        raise
    except Exception:
        # No exception text, remote frames, response bodies or token values in logs.
        raise SetupError("HA nicht erreichbar, TLS ungueltig oder Protokollfehler. Konfiguration unveraendert.") from None

async def check_saved(path=CONFIG):
    values = load_config(path)
    return await query(values["HA_URL"], values["HA_TOKEN"], values["SIW_INVENTORY_ID"])

def setup():
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        raise SetupError("Einrichtung nur interaktiv in der LXC-Konsole ausfuehren.")
    previous = load_config() if CONFIG.exists() or CONFIG.is_symlink() else None
    if previous and input("Vorhandene Anmeldung ersetzen? [j/N]: ").strip().lower() != "j":
        print("Abgebrochen; gespeicherte Anmeldung bleibt erhalten.")
        return
    default = previous["HA_URL"] if previous else ""
    base = normalize_url(input(f"HA-Adresse mit http(s) [{default}]: ").strip() or default)
    allow_http = "false"
    if base.startswith("http://"):
        print("HTTP uebertraegt den Token unverschluesselt. Nur in einem vertrauenswuerdigen Netz verwenden.")
        if input("Diese HTTP-Verbindung verwenden? [j/N]: ").strip().lower() != "j":
            raise SetupError("Abgebrochen; HTTPS-Adresse verwenden.")
        allow_http = "true"
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        credential = getpass.getpass("Langlebiger HA-Zugriffstoken (Eingabe unsichtbar): ").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{20,8192}", credential):
        raise SetupError("Tokenformat ungueltig.")
    inventories = asyncio.run(query(base, credential))
    for number, (_, name) in enumerate(inventories, 1):
        print(f"{number}: {name}")
    answer = input("Inventar waehlen [1]: ").strip() or "1"
    if not answer.isdecimal() or not 1 <= int(answer) <= len(inventories):
        raise SetupError("Ungueltige Inventarauswahl.")
    inventory = inventories[int(answer) - 1][0]
    values = validate({"HA_URL": base, "HA_TOKEN": credential,
                       "SIW_INVENTORY_ID": inventory, "HA_ALLOW_HTTP": allow_http})
    count = asyncio.run(query(base, credential, inventory))
    save_config(values)
    print(f"Anmeldung geprueft und lokal gespeichert; {count} Artikel lesbar.")
    print("Zugangsdaten werden nach Neustarts wiederverwendet. Kein HA-Passwort gespeichert.")
    if Path("/etc/systemd/system/simpleinventory-web.service").exists():
        result = subprocess.run(["systemctl", "restart", "simpleinventory-web.service"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode:
            print("Konfiguration gespeichert. Webdienst bitte manuell neu starten.")

def main():
    parser = argparse.ArgumentParser(description="Home Assistant fuer SimpleInventory-WebUI einrichten.")
    parser.add_argument("--check", action="store_true", help="Gespeicherte Anmeldung lesend pruefen.")
    args = parser.parse_args()
    if os.geteuid() != 0:
        print("Als root im LXC ausfuehren.", file=sys.stderr)
        return 1
    try:
        if args.check:
            asyncio.run(check_saved())
            print("Gespeicherte HA-Anmeldung und Simple-Inventory-Lesezugriff funktionieren.")
        else:
            setup()
        return 0
    except (KeyboardInterrupt, EOFError):
        print("\nAbgebrochen; vorhandene Konfiguration bleibt erhalten.", file=sys.stderr)
        return 1
    except SetupError as error:
        print(str(error), file=sys.stderr)
        return 1
    except Exception:
        print("Einrichtung fehlgeschlagen; keine vertraulichen Fehlerdetails ausgegeben.", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
