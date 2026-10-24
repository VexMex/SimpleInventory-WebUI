"""Installation defaults are local INI settings; cookies contain display choices only."""
import asyncio
import configparser
from dataclasses import dataclass
import hmac
import json
import os
from pathlib import Path
import time
from urllib.parse import parse_qs
from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature
from .localization import translate, number, currency, SYMBOLS, timestamp

OPTIONS = {"language":{"auto","de","en"}, "currency":set(SYMBOLS),
           "theme":{"auto","light","dark"}, "accent":{"teal","blue"},
           "density":{"comfortable","compact"}}
FALLBACK = {"language":"auto","currency":"EUR","theme":"auto","accent":"teal","density":"comfortable"}

@dataclass
class InstallationSettings:
    display: dict
    enabled: bool = False
    local_bypass: bool = True

    @classmethod
    def read(cls, path=None):
        if path is None:
            directory = os.environ.get("CREDENTIALS_DIRECTORY")
            path = Path(directory) / "ui-settings" if directory else Path("/etc/simpleinventory-webui/settings.ini")
        config = configparser.ConfigParser(interpolation=None)
        if Path(path).exists():
            try:
                with Path(path).open(encoding="utf-8") as stream:
                    config.read_file(stream)
            except (OSError, configparser.Error, UnicodeError):
                raise RuntimeError("Invalid installation settings") from None
        try:
            display = {key:config.get("display",key,fallback=value) for key,value in FALLBACK.items()}
            if any(display[key] not in OPTIONS[key] for key in OPTIONS):
                raise ValueError()
            return cls(display,config.getboolean("access","enabled",fallback=False),
                       config.getboolean("access","local_bypass",fallback=True))
        except (ValueError, configparser.Error):
            raise RuntimeError("Invalid installation settings") from None

def cookie_preferences(value):
    try:
        if len(value) > 512:
            return {}
        parsed = json.loads(value)
        if not isinstance(parsed,dict):
            return {}
        return {key:val for key,val in parsed.items()
                if key in OPTIONS and isinstance(val,str) and val in OPTIONS[key]}
    except (ValueError, TypeError):
        return {}

class PreferenceController:
    def __init__(self, client, configuration, policy, signing):
        self.client, self.configuration, self.policy = client, configuration, policy
        self.locale = ("de","UTC")
        self.expires = 0
        self.lock = asyncio.Lock()
        self.forms = URLSafeTimedSerializer(signing, salt="siw-preferences")

    async def prepare(self, request):
        override = cookie_preferences(request.cookies.get("siw_preferences",""))
        display = {**self.configuration.display, **override}
        if request.url.path != "/health" and time.monotonic() > self.expires and hasattr(self.client,"locale_info"):
            async with self.lock:
                if time.monotonic() > self.expires:
                    try:
                        self.locale = await asyncio.wait_for(self.client.locale_info(), timeout=3)
                        self.expires = time.monotonic() + 300
                    except Exception:
                        self.expires = time.monotonic() + 30
        language = display["language"]
        if language == "auto":
            language = self.locale[0].lower().replace("_","-").split("-")[0]
            if language not in {"de","en"}:
                language = "de"
        request.state.ui = {
            "language":language, "display":display, "overrides":override,
            "t":lambda text:translate(text,language),
            "quantity":lambda value:number(value,language),
            "money":lambda value:currency(value,language,display["currency"]),
            "currency_symbol":SYMBOLS[display["currency"]],
            "loaded_at":timestamp(language,self.locale[1]),
            "configuration":self.configuration, "access":self.policy,
        }

    def install(self, app, render, error_page):
        @app.get("/settings", response_class=HTMLResponse)
        async def settings(request: Request):
            nonce = self.forms.dumps(os.urandom(16).hex())
            response = render(request=request,name="settings.html",
                              context={"proof":nonce,"saved":request.query_params.get("saved")=="1"})
            response.set_cookie("siw_settings",nonce,httponly=True,samesite="strict",
                                secure=request.url.scheme=="https",max_age=600)
            return response

        @app.post("/settings")
        async def save_settings(request: Request):
            if request.headers.get("content-type","").split(";")[0] != "application/x-www-form-urlencoded":
                return error_page(request,"Ungueltige Eingabe.",status_code=400)
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body)>4096:
                    return error_page(request,"Eingabe zu gross.",status_code=413)
            try:
                raw = parse_qs(body.decode("utf-8"),max_num_fields=7,keep_blank_values=True)
                if any(len(val)!=1 for val in raw.values()) or set(raw)-set(OPTIONS)-{"proof","reset"}:
                    raise ValueError()
                form = {key:val[0] for key,val in raw.items()}
                proof = form.pop("proof","")
                if not hmac.compare_digest(proof,request.cookies.get("siw_settings","")):
                    raise ValueError()
                self.forms.loads(proof,max_age=600)
                reset = form.pop("reset","")
                if reset not in {"","1"} or any(val != "default" and val not in OPTIONS[key] for key,val in form.items()):
                    raise ValueError()
                choices = {} if reset else {key:val for key,val in form.items() if val!="default"}
            except (ValueError,UnicodeError,TypeError,BadSignature):
                return error_page(request,"Ungueltige Eingabe.",status_code=400)
            response = RedirectResponse("/settings?saved=1",status_code=303)
            if choices:
                response.set_cookie("siw_preferences",json.dumps(choices,separators=(",",":")),
                                    httponly=True,samesite="strict",secure=request.url.scheme=="https",
                                    max_age=31536000)
            else:
                response.delete_cookie("siw_preferences")
            response.delete_cookie("siw_settings")
            return response
