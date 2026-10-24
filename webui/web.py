"""Inventory WebUI. Credentials stay in the server process."""
from __future__ import annotations
import asyncio
from collections import defaultdict, deque, OrderedDict
from contextlib import asynccontextmanager
from decimal import Decimal, InvalidOperation
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

def euro_value(value):
    if value is None or value == "":
        return "—"
    try:
        amount = Decimal(str(value))
        if not amount.is_finite():
            return "—"
        return format(amount, ",.2f").replace(",", "_").replace(".", ",").replace("_", ".") + " €"
    except (InvalidOperation, ValueError, TypeError):
        return "—"

TEMPLATES.env.filters["euro_value"] = euro_value

def load_helper():
    spec = importlib.util.spec_from_file_location("siw_ha_setup", HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class InventoryUnavailable(Exception):
    pass

class WriteConflict(Exception):
    pass

class WriteUncertain(Exception):
    pass

class InvalidFields(Exception):
    pass

EDIT_FIELDS = ("name", "quantity", "unit", "category", "location", "price")

def editable(item):
    values = {key: item.get(key, "") for key in EDIT_FIELDS}
    values["price"] = item.get("price") if item.get("price") is not None else 0
    for singular, plural in (("category", "categories"), ("location", "locations")):
        if isinstance(item.get(plural), list):
            values[singular] = ", ".join(str(value) for value in item[plural])
    return values

def item_choices(items):
    """Existing values from the configured inventory, without blank duplicates."""
    choices = {}
    for singular, plural in (("category", "categories"), ("location", "locations")):
        found = set()
        for item in items:
            values = item.get(plural)
            if not isinstance(values, list):
                value = item.get(singular, "")
                values = value.split(",") if isinstance(value, str) else []
            for value in values:
                if isinstance(value, str) and value.strip():
                    found.add(value.strip())
        choices[singular] = sorted(found, key=lambda value: (value.casefold(), value))
    choices["unit"] = sorted({"stück"} | {item["unit"].strip() for item in items
                                          if isinstance(item.get("unit"), str) and item["unit"].strip()},
                             key=lambda value: (value.casefold(), value))
    return choices

def fingerprint(item):
    values = editable(item)
    for key in ("quantity", "price"):
        values[key] = str(Decimal(str(values[key])).normalize())
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()

def validate_fields(form):
    result = {}
    for key, maximum in (("name", 200), ("unit", 40), ("category", 500), ("location", 500)):
        value = str(form.get(key, "")).strip()
        if len(value) > maximum or re.search(r"[\x00-\x1f\x7f-\x9f]", value):
            raise InvalidFields()
        result[key] = value
    if not result["name"]:
        raise InvalidFields()
    value = str(form.get("quantity", "")).strip().replace(",", ".")
    if not re.fullmatch(r"\d{1,10}(?:\.\d{1,6})?", value, flags=re.ASCII):
        raise InvalidFields()
    amount = Decimal(value)
    if amount > 1000000000:
        raise InvalidFields()
    result["quantity"] = float(amount)
    value = str(form.get("price", "0")).strip().replace(",", ".")
    if not re.fullmatch(r"\d{1,10}(?:\.\d{1,2})?", value, flags=re.ASCII):
        raise InvalidFields()
    amount = Decimal(value)
    if amount > 1000000000:
        raise InvalidFields()
    result["price"] = float(amount)
    for key in ("category", "location"):
        result[key] = ", ".join(dict.fromkeys(part.strip() for part in result[key].split(",") if part.strip()))
    return result

def exact_item(items, name):
    matches = [item for item in items if item.get("name") == name]
    if len(matches) != 1:
        raise WriteConflict()
    return matches[0]

class InventoryClient:
    @asynccontextmanager
    async def connection(self):
        helper = load_helper()
        settings = helper.validate({key: os.environ.get(key, "") for key in helper.FIELDS})
        url = helper.urlsplit(settings["HA_URL"])
        endpoint = helper.urlunsplit(("wss" if url.scheme == "https" else "ws",
                                      url.netloc, url.path + "/api/websocket", "", ""))
        async with asyncio.timeout(20):
            async with helper.connect(endpoint, proxy=None, open_timeout=8, close_timeout=2,
                                      max_size=8 * 1024 * 1024, logger=helper.LOG) as ws:
                if (await helper.receive(ws)).get("type") != "auth_required":
                    raise InventoryUnavailable()
                await ws.send(json.dumps({"type":"auth","access_token":settings["HA_TOKEN"]}))
                if (await helper.receive(ws)).get("type") != "auth_ok":
                    raise InventoryUnavailable()
                yield helper, ws, settings

    async def list_items(self, helper, ws, settings, number):
        result = await helper.request(ws, number, "simple_inventory/list_items",
                                      inventory_id=settings["SIW_INVENTORY_ID"])
        if not isinstance(result, dict) or not isinstance(result.get("items"), list):
            raise InventoryUnavailable()
        return [row for row in result["items"] if isinstance(row, dict)]

    async def read(self):
        try:
            async with self.connection() as (helper, ws, settings):
                states = await helper.request(ws, 1, "get_states")
                name = "Konfiguriertes Inventar"
                for state in states if isinstance(states, list) else []:
                    attrs = state.get("attributes", {})
                    if attrs.get("inventory_id") == settings["SIW_INVENTORY_ID"] and "total_items" in attrs:
                        name = str(attrs.get("friendly_name", name))
                        break
                rows = await self.list_items(helper, ws, settings, 2)
                fields = ("name","quantity","unit","category","categories","location","locations","price")
                return {"name":name, "items":[{key:row[key] for key in fields if key in row} for row in rows]}
        except Exception:
            raise InventoryUnavailable() from None

    async def write(self, fields, old_name=None, expected=None):
        fields = validate_fields(fields)
        dispatched = False
        try:
            async with self.connection() as (helper, ws, settings):
                items = await self.list_items(helper, ws, settings, 1)
                if old_name is not None:
                    if fingerprint(exact_item(items, old_name)) != expected:
                        raise WriteConflict()
                for item in items:
                    if item.get("name") == old_name:
                        continue
                    aliases = item.get("aliases")
                    names = [item.get("name", "")] + (aliases if isinstance(aliases, list) else [])
                    if any(str(name).strip().casefold() == fields["name"].casefold() for name in names):
                        raise WriteConflict()
                data = {"inventory_id":settings["SIW_INVENTORY_ID"], **fields}
                if old_name is not None:
                    data["old_name"] = old_name
                dispatched = True
                await helper.request(ws, 2, "call_service", domain="simple_inventory",
                                     service="add_item" if old_name is None else "update_item",
                                     service_data=data)
                after = await self.list_items(helper, ws, settings, 3)
                if fingerprint(exact_item(after, fields["name"])) != fingerprint(fields):
                    raise WriteUncertain()
        except (InvalidFields, WriteConflict):
            if dispatched:
                raise WriteUncertain() from None
            raise
        except Exception:
            # Never retry a mutation: the service may already have saved it.
            if dispatched:
                raise WriteUncertain() from None
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
    signing = policy.signing_key or os.urandom(32).hex()
    session = URLSafeTimedSerializer(signing, salt="siw-session")
    csrf = URLSafeTimedSerializer(signing, salt="siw-login")
    forms = URLSafeTimedSerializer(signing, salt="siw-items")
    submitted = OrderedDict()
    write_lock = asyncio.Lock()
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
                                              context={"inventory":data,"error":None,
                                                       "saved":request.query_params.get("saved") == "1"})
        except InventoryUnavailable:
            return TEMPLATES.TemplateResponse(request=request, name="index.html",
                context={"inventory":None,"error":"Home Assistant oder das konfigurierte Inventar ist derzeit nicht erreichbar."},
                status_code=503)

    def item_form(request, values, action, choices, old_name=None, expected=None):
        binding = request.cookies.get("siw_forms", "")
        if not re.fullmatch(r"[0-9a-f]{64}", binding):
            binding = os.urandom(32).hex()
        proof = forms.dumps({"action":action, "old_name":old_name, "expected":expected,
                             "binding":hashlib.sha256(binding.encode()).hexdigest(),
                             "nonce":os.urandom(16).hex()})
        response = TEMPLATES.TemplateResponse(request=request, name="item.html",
                                             context={"values":values,"action":action,"proof":proof,"choices":choices})
        response.set_cookie("siw_forms", binding, httponly=True, samesite="strict",
                            secure=request.url.scheme == "https", max_age=3600)
        return response

    @app.get("/items/new", response_class=HTMLResponse)
    async def new_item(request: Request):
        try:
            inventory = await client.read()
            return item_form(request, {"quantity":1,"unit":"stück","price":"0,00"}, "new", item_choices(inventory["items"]))
        except InventoryUnavailable:
            return HTMLResponse("Inventar derzeit nicht erreichbar.", status_code=503)

    @app.get("/items/edit", response_class=HTMLResponse)
    async def edit_item(request: Request):
        try:
            inventory = await client.read()
            item = exact_item(inventory["items"], request.query_params.get("item", ""))
            return item_form(request, editable(item), "edit", item_choices(inventory["items"]),
                             item["name"], fingerprint(item))
        except WriteConflict:
            return HTMLResponse("Artikel nicht eindeutig vorhanden. Bitte Bestand neu laden.", status_code=409)
        except InventoryUnavailable:
            return HTMLResponse("Inventar derzeit nicht erreichbar.", status_code=503)

    @app.post("/items/{action}")
    async def save_item(action: str, request: Request):
        if action not in {"new", "edit"}:
            return HTMLResponse("Seite nicht gefunden.", status_code=404)
        if request.headers.get("content-type", "").split(";")[0] != "application/x-www-form-urlencoded":
            return HTMLResponse("Ungueltige Eingabe.", status_code=400)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 16384:
                return HTMLResponse("Eingabe zu gross.", status_code=413)
        try:
            raw = parse_qs(body.decode("utf-8"), max_num_fields=7, keep_blank_values=True)
            if any(len(value) != 1 for value in raw.values()) or set(raw) - set(EDIT_FIELDS) - {"proof"}:
                raise ValueError()
            form = {key:value[0] for key,value in raw.items()}
            claim = forms.loads(form.get("proof", ""), max_age=900)
            binding = hashlib.sha256(request.cookies.get("siw_forms", "").encode()).hexdigest()
            if (claim["action"] != action or not hmac.compare_digest(claim["binding"], binding)
                    or not re.fullmatch(r"[0-9a-f]{32}", claim["nonce"])):
                raise ValueError()
            if action == "edit" and not isinstance(claim["old_name"], str):
                raise ValueError()
        except (ValueError, UnicodeError, BadSignature, KeyError, TypeError, AttributeError):
            return HTMLResponse("Formular ungueltig oder abgelaufen. Bitte neu oeffnen.", status_code=400)
        try:
            fields = validate_fields(form)
        except InvalidFields:
            return HTMLResponse("Name und eine Menge von 0 bis 1000000000 angeben (max. 6 Nachkommastellen). "
                                "Wert als Zahl von 0 bis 1000000000 mit maximal 2 Nachkommastellen angeben. "
                                "Textfelder duerfen keine Steuerzeichen enthalten. Mit Zurueck korrigieren.",
                                status_code=422)
        async with write_lock:
            now = time.monotonic()
            while submitted and next(iter(submitted.values())) < now - 1800:
                submitted.popitem(last=False)
            nonce = claim["nonce"]
            if nonce in submitted:
                return HTMLResponse("Dieses Formular wurde bereits abgesendet. Bitte Bestand neu laden.",
                                    status_code=409)
            if len(submitted) >= 1000:
                return HTMLResponse("Bitte spaeter erneut versuchen.", status_code=429)
            submitted[nonce] = now
            try:
                await client.write(fields, old_name=claim["old_name"], expected=claim["expected"])
            except WriteConflict:
                return HTMLResponse("Artikel bereits vorhanden oder zwischenzeitlich geaendert. "
                                    "Bitte Bestand neu laden und das Formular erneut oeffnen.", status_code=409)
            except InventoryUnavailable:
                return HTMLResponse("Home Assistant nicht erreichbar. Bitte Verbindung pruefen.", status_code=503)
            except WriteUncertain:
                return HTMLResponse("Speicherung nicht bestaetigt. Bitte zuerst den Bestand pruefen, "
                                    "bevor du erneut speicherst.", status_code=502)
        return RedirectResponse("/?saved=1", status_code=303)

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
