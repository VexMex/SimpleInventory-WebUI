"""Read-only inventory WebUI. Credentials stay in the server process."""
from __future__ import annotations
import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass
import hashlib
import hmac
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import parse_qs
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeTimedSerializer, BadSignature

ROOT = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(ROOT / "templates"))
HELPER = Path("/opt/simpleinventory-webui/setup-ha.py")

def load_helper():
    spec = importlib.util.spec_from_file_location("siw_ha_setup", HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class InventoryUnavailable(Exception):
    pass

class InventoryClient:
    async def read(self):
        try:
            helper = load_helper()
            settings = helper.validate({key: os.environ.get(key, "") for key in helper.FIELDS})
            url = helper.urlsplit(settings["HA_URL"])
            endpoint = helper.urlunsplit(("wss" if url.scheme == "https" else "ws",
                                          url.netloc, url.path + "/api/websocket", "", ""))
            async with asyncio.timeout(15):
                async with helper.connect(endpoint, proxy=None, open_timeout=8, close_timeout=2,
                                          max_size=8 * 1024 * 1024, logger=helper.LOG) as ws:
                    if (await helper.receive(ws)).get("type") != "auth_required":
                        raise InventoryUnavailable()
                    await ws.send(json.dumps({"type":"auth","access_token":settings["HA_TOKEN"]}))
                    if (await helper.receive(ws)).get("type") != "auth_ok":
                        raise InventoryUnavailable()
                    states = await helper.request(ws, 1, "get_states")
                    name = "Konfiguriertes Inventar"
                    for state in states if isinstance(states, list) else []:
                        attrs = state.get("attributes", {})
                        if (attrs.get("inventory_id") == settings["SIW_INVENTORY_ID"]
                                and "total_items" in attrs):
                            name = str(attrs.get("friendly_name", name))
                            break
                    result = await helper.request(ws, 2, "simple_inventory/list_items",
                                                  inventory_id=settings["SIW_INVENTORY_ID"])
                    if not isinstance(result, dict) or not isinstance(result.get("items"), list):
                        raise InventoryUnavailable()
                    fields = ("name","quantity","unit","category","categories","location","locations")
                    items = [{key: row[key] for key in fields if key in row}
                             for row in result["items"] if isinstance(row, dict)]
                    return {"name":name,"items":items}
        except Exception:
            # Never expose HA URLs, tokens, server exception messages or tracebacks.
            raise InventoryUnavailable() from None

PRIVATE_V4 = tuple(ipaddress.ip_network(net) for net in ("10.0.0.0/8","172.16.0.0/12","192.168.0.0/16"))

def networks_from_addresses(addresses):
    result = []
    for interface in addresses:
        if "UP" not in interface.get("flags", []):
            continue
        for info in interface.get("addr_info", []):
            if info.get("family") != "inet" or info.get("scope") != "global":
                continue
            try:
                network = ipaddress.ip_network(f'{info["local"]}/{info["prefixlen"]}', strict=False)
                if any(network.subnet_of(private) for private in PRIVATE_V4):
                    result.append(network)
            except (KeyError, ValueError, TypeError):
                continue
    return result

class LocalNetworks:
    def __init__(self):
        self.expires = 0.0
        self.networks = []
    def __call__(self):
        if time.monotonic() >= self.expires:
            try:
                raw = subprocess.run(["/usr/sbin/ip","-j","-4","addr","show"],
                                     capture_output=True, text=True, timeout=2, check=True)
                self.networks = networks_from_addresses(json.loads(raw.stdout))
            except Exception:
                self.networks = []  # Failure must never grant password bypass.
            self.expires = time.monotonic() + 30
        return self.networks

@dataclass
class AccessPolicy:
    enabled: bool = False
    local_bypass: bool = True
    digest: str = ""
    signing_key: str = ""

    @classmethod
    def from_env(cls):
        enabled = os.environ.get("SIW_AUTH_ENABLED", "false").lower()
        bypass = os.environ.get("SIW_LOCAL_BYPASS", "true").lower()
        if enabled not in {"true","false"} or bypass not in {"true","false"}:
            raise RuntimeError("Invalid authentication configuration")
        policy = cls(enabled == "true", bypass == "true",
                     os.environ.get("SIW_PASSWORD_HASH",""), os.environ.get("SIW_SESSION_SECRET",""))
        if policy.enabled:
            if len(policy.signing_key) < 32 or not re.fullmatch(
                    r"pbkdf2_sha256\$600000\$[0-9a-f]{32}\$[0-9a-f]{64}", policy.digest):
                raise RuntimeError("Authentication enabled but private settings incomplete")
        return policy

def password_matches(password, encoded):
    if not isinstance(password, str) or len(password) > 1024:
        return False
    try:
        _, rounds, salt, expected = encoded.split("$")
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds)).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False

def create_app(client=None, policy=None, networks=None):
    client = client or InventoryClient()
    policy = policy if policy is not None else AccessPolicy.from_env()
    networks = networks if networks is not None else LocalNetworks()
    session = URLSafeTimedSerializer(policy.signing_key or "disabled-mode", salt="siw-session")
    csrf = URLSafeTimedSerializer(policy.signing_key or "disabled-mode", salt="siw-login")
    attempts = defaultdict(deque)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    def allowed(request):
        if not policy.enabled:
            return True
        try:
            peer = ipaddress.ip_address(request.client.host)
            if policy.local_bypass and (peer.is_loopback or any(peer in net for net in networks())):
                return True
        except (ValueError, AttributeError, TypeError):
            pass
        try:
            return session.loads(request.cookies.get("siw_session",""), max_age=43200) == "authenticated"
        except BadSignature:
            return False

    @app.middleware("http")
    async def access_and_headers(request, call_next):
        if request.url.path not in {"/login","/health"} and not allowed(request):
            response = (JSONResponse({"error":"Anmeldung erforderlich."}, status_code=401)
                        if request.url.path.startswith("/api/") else RedirectResponse("/login", status_code=303))
        else:
            response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
        return response

    @app.get("/health")
    async def health():
        return {"status":"ok"}

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        try:
            data = await client.read()
            return TEMPLATES.TemplateResponse(request=request, name="index.html",
                                              context={"inventory":data,"error":None})
        except InventoryUnavailable:
            return TEMPLATES.TemplateResponse(request=request, name="index.html",
                context={"inventory":None,"error":"Home Assistant oder das konfigurierte Inventar ist derzeit nicht erreichbar."},
                status_code=503)

    @app.get("/api/inventory")
    async def inventory_api():
        try:
            return await client.read()
        except InventoryUnavailable:
            return JSONResponse({"error":"Inventar derzeit nicht erreichbar."}, status_code=503)

    @app.get("/login", response_class=HTMLResponse)
    async def login_form(request: Request):
        if allowed(request):
            return RedirectResponse("/", status_code=303)
        nonce = csrf.dumps(os.urandom(16).hex())
        response = TEMPLATES.TemplateResponse(request=request, name="login.html",
                                             context={"csrf":nonce,"error":None})
        response.set_cookie("siw_login", nonce, httponly=True, samesite="strict",
                            secure=request.url.scheme == "https", max_age=600)
        return response

    @app.post("/login")
    async def login_submit(request: Request):
        if allowed(request):
            return RedirectResponse("/", status_code=303)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 8192:
                return HTMLResponse("Eingabe zu gross.", status_code=413)
        try:
            values = parse_qs(body.decode("utf-8"), max_num_fields=3, keep_blank_values=True)
            if any(len(value) != 1 for value in values.values()):
                raise ValueError()
            form = {key:value[0] for key,value in values.items()}
        except (ValueError, UnicodeError):
            return HTMLResponse("Ungueltige Eingabe.", status_code=400)
        nonce = form.get("csrf","")
        try:
            if not hmac.compare_digest(nonce, request.cookies.get("siw_login","")):
                raise BadSignature("Mismatch")
            csrf.loads(nonce, max_age=600)
        except BadSignature:
            return HTMLResponse("Anmeldeseite bitte neu laden.", status_code=400)
        peer = request.client.host if request.client else "unknown"
        recent = attempts[peer]
        now = time.monotonic()
        while recent and recent[0] < now - 60:
            recent.popleft()
        if len(recent) >= 5:
            return HTMLResponse("Bitte spaeter erneut versuchen.", status_code=429)
        recent.append(now)
        if not password_matches(form.get("password",""), policy.digest):
            return TEMPLATES.TemplateResponse(request=request, name="login.html",
                context={"csrf":nonce,"error":"Passwort ungueltig."}, status_code=401)
        recent.clear()
        response = RedirectResponse("/", status_code=303)
        response.set_cookie("siw_session", session.dumps("authenticated"), httponly=True,
                            samesite="strict", secure=request.url.scheme == "https", max_age=43200)
        response.delete_cookie("siw_login")
        return response

    return app

app = create_app()
