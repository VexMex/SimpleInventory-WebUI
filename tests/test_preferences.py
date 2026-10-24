"""Localization, local defaults and browser-only preferences, without real credentials."""
import ast
import copy
import html
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from webui.web import create_app, AccessPolicy
from webui.localization import EN, currency, number, timestamp
from webui.preferences import InstallationSettings, FALLBACK, cookie_preferences
from test_items import MemoryInventory
from test_web import policy

class LocalizedInventory(MemoryInventory):
    def __init__(self):
        super().__init__()
        self.locale_calls = 0
    async def locale_info(self):
        self.locale_calls += 1
        return "en-GB","Europe/Berlin"

def proof(client):
    page = client.get("/settings")
    return html.unescape(re.search(r'name="proof" value="([^"]+)"',page.text).group(1))

class PreferenceTests(unittest.TestCase):
    def setUp(self):
        self.backend = LocalizedInventory()
        self.configuration = InstallationSettings(dict(FALLBACK))
        self.app = create_app(self.backend,AccessPolicy(),configuration=self.configuration)
    def test_automatic_ha_language_and_cache(self):
        with TestClient(self.app) as client:
            self.assertIn('<html lang="en"', client.get("/").text)
            self.assertIn("Add item",client.get("/items/new").text)
            self.assertEqual(self.backend.locale_calls,1)
            page = client.post("/items/new",data={"proof":"invalid"})
            self.assertEqual(page.status_code,400)
            self.assertIn("Form invalid or expired",page.text)
    def test_browser_preferences_persist_and_do_not_affect_another_browser(self):
        with TestClient(self.app) as first, TestClient(self.app) as second:
            response = first.post("/settings",data={"proof":proof(first),"language":"de","currency":"GBP",
                                                   "theme":"dark","accent":"blue","density":"compact"},
                                  follow_redirects=False)
            self.assertEqual(response.status_code,303)
            self.assertIn("Max-Age=31536000",response.headers["set-cookie"])
            page = first.get("/")
            self.assertIn('<html lang="de" data-theme="dark" data-accent="blue" data-density="compact"',page.text)
            self.assertIn('<html lang="en" data-theme="auto"',second.get("/").text)
            self.assertEqual(self.configuration.display,FALLBACK)
            reset = first.post("/settings",data={"proof":proof(first),"reset":"1"})
            self.assertEqual(reset.status_code,200)
            self.assertNotIn("siw_preferences",first.cookies)
    def test_invalid_csrf_values_and_security_settings_rejected(self):
        with TestClient(self.app) as client:
            self.assertEqual(client.post("/settings",data={"language":"en"}).status_code,400)
            nonce = proof(client)
            for extra in ({"currency":"invalid"},{"enabled":"false"},{"theme":"<script>"},{"language":"fr"}):
                self.assertEqual(client.post("/settings",data={"proof":nonce,**extra}).status_code,400)
            self.assertNotIn("siw_preferences",client.cookies)
            self.assertEqual(client.post("/settings",content="x"*5000,
                             headers={"content-type":"application/x-www-form-urlencoded"}).status_code,413)
    def test_display_cookie_cannot_grant_login_or_local_bypass(self):
        _, rules = policy()
        with TestClient(create_app(self.backend,rules,lambda:[],configuration=self.configuration),
                        client=("203.0.113.7",2000)) as client:
            client.cookies.set("siw_preferences",json.dumps({"enabled":False,"local_bypass":True,"language":"en"}))
            self.assertEqual(client.get("/api/inventory").status_code,401)
            self.assertEqual(client.get("/settings",follow_redirects=False).status_code,303)
    def test_cookie_whitelist_and_invalid_input(self):
        self.assertEqual(cookie_preferences('{"language":"en","enabled":false,"currency":"BAD"}'),{"language":"en"})
        for value in ("not-json", "[]", "x"*600, '{"theme":[]}'):
            self.assertEqual(cookie_preferences(value),{})
    def test_ini_defaults_and_authentication_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"settings.ini"
            path.write_text("[display]\nlanguage=en\ncurrency=USD\ntheme=dark\n[access]\nenabled=true\nlocal_bypass=false\n")
            config = InstallationSettings.read(path)
            self.assertEqual(config.display["currency"],"USD")
            self.assertTrue(config.enabled)
            self.assertFalse(config.local_bypass)
            with patch.dict("os.environ",{},clear=True):
                with self.assertRaises(RuntimeError):
                    AccessPolicy.from_env(config)
            path.write_text("[display]\ncurrency=BAD\n")
            with self.assertRaises(RuntimeError):
                InstallationSettings.read(path)
    def test_money_numbers_and_dates(self):
        self.assertEqual(currency(1234.5,"de","EUR"),"1.234,50 €")
        self.assertEqual(currency(1234.5,"en","USD"),"$1,234.50")
        self.assertEqual(currency(1234.5,"en","GBP"),"£1,234.50")
        self.assertEqual(number(1234.25,"de"),"1.234,25")
        self.assertEqual(number(1234.25,"en"),"1,234.25")
        self.assertEqual(currency(None,"en","EUR"),"—")
        self.assertRegex(timestamp("de","Europe/Berlin"),r"^\d{2}\.\d{2}\.\d{4} ")
        self.assertRegex(timestamp("en","Europe/Berlin"),r"^\d{4}-\d{2}-\d{2} ")
    def test_all_backend_error_messages_have_an_english_translation(self):
        source = Path(__file__).resolve().parents[1]/"webui"/"web.py"
        for call in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
            if isinstance(call,ast.Call) and isinstance(call.func,ast.Name) and call.func.id=="error_page":
                if len(call.args)>1 and isinstance(call.args[1],ast.Constant):
                    self.assertIn(call.args[1].value,EN)

if __name__ == "__main__":
    unittest.main()
