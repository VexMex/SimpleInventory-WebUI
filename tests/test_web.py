"""Read-only UI and optional access policy; no real credentials used."""
import hashlib
import ipaddress
import json
from pathlib import Path
import secrets
import sys
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from webui.web import create_app,AccessPolicy,networks_from_addresses,InventoryUnavailable

class FakeInventory:
    def __init__(self,items=None):
        self.items=items if items is not None else [{"name":"Test article","quantity":2,"unit":"Stueck",
                                                    "categories":["Hardware"],"locations":["Shelf"]}]
        self.calls=0
    async def read(self, inventory_id=None):
        self.calls+=1
        return {"id":"configured","name":"Test inventory","inventories":[{"id":"configured","name":"Test inventory"}],"items":self.items}

def policy():
    phrase=secrets.token_hex(12)
    salt=secrets.token_hex(16)
    digest=hashlib.pbkdf2_hmac("sha256",phrase.encode(),bytes.fromhex(salt),600000).hex()
    return phrase,AccessPolicy(True,True,"$".join(("pbkdf2_sha256","600000",salt,digest)),secrets.token_hex(32))

class WebTests(unittest.TestCase):
    def test_read_only_html_and_json(self):
        backend=FakeInventory()
        with TestClient(create_app(backend,AccessPolicy(),lambda:[])) as client:
            page=client.get("/")
            self.assertEqual(page.status_code,200)
            self.assertIn("Test article",page.text)
            self.assertIn("Test inventory",page.text)
            self.assertEqual(client.get("/api/inventory").json()["items"][0]["quantity"],2)
            self.assertEqual(client.post("/api/inventory",json={"quantity":5}).status_code,405)
            self.assertEqual(page.headers["cache-control"],"no-store")

    def test_html_escapes_inventory_content(self):
        with TestClient(create_app(FakeInventory([{"name":"<script>alert(1)</script>"}]),AccessPolicy())) as client:
            page=client.get("/")
            self.assertIn("&lt;script&gt;",page.text)
            self.assertNotIn("<script>",page.text)

    def test_empty_inventory(self):
        with TestClient(create_app(FakeInventory([]),AccessPolicy())) as client:
            self.assertIn("Dieses Inventar ist leer.",client.get("/").text)

    def test_unavailable_backend_does_not_show_exception(self):
        class Broken:
            async def read(self, inventory_id=None): raise InventoryUnavailable("private diagnostic")
        with TestClient(create_app(Broken(),AccessPolicy())) as client:
            self.assertEqual(client.get("/").status_code,503)
            self.assertNotIn("private diagnostic",client.get("/").text)
            self.assertEqual(client.get("/api/inventory").status_code,503)

    def test_disabled_auth_allows_peer_without_password(self):
        with TestClient(create_app(FakeInventory(),AccessPolicy(),lambda:[])) as client:
            self.assertEqual(client.get("/").status_code,200)

    def test_local_subnet_bypass_is_dynamic(self):
        _,p=policy()
        networks=[ipaddress.ip_network("192.168.10.0/24")]
        app=create_app(FakeInventory(),p,lambda:networks)
        with TestClient(app,client=("192.168.10.20",1000)) as client:
            self.assertEqual(client.get("/").status_code,200)
            networks[:]=[ipaddress.ip_network("192.168.20.0/24")]
            self.assertEqual(client.get("/",follow_redirects=False).status_code,303)

    def test_forwarded_header_does_not_grant_bypass(self):
        _,p=policy()
        app=create_app(FakeInventory(),p,lambda:[ipaddress.ip_network("192.168.10.0/24")])
        with TestClient(app,client=("203.0.113.7",1000)) as client:
            self.assertEqual(client.get("/api/inventory",headers={"X-Forwarded-For":"192.168.10.20"}).status_code,401)

    def test_password_session_without_username(self):
        phrase,p=policy()
        with TestClient(create_app(FakeInventory(),p,lambda:[])) as client:
            client.get("/login")
            nonce=client.cookies["siw_login"]
            answer=client.post("/login",data={"csrf":nonce,"password":phrase},follow_redirects=False)
            self.assertEqual(answer.status_code,303)
            self.assertIn("siw_session",client.cookies)
            self.assertEqual(client.get("/").status_code,200)

    def test_bad_password_and_csrf(self):
        _,p=policy()
        with TestClient(create_app(FakeInventory(),p,lambda:[])) as client:
            self.assertEqual(client.post("/login",data={"password":"invalid"}).status_code,400)
            client.get("/login"); nonce=client.cookies["siw_login"]
            self.assertEqual(client.post("/login",data={"csrf":nonce,"password":"invalid"}).status_code,401)
            self.assertEqual(client.get("/api/inventory").status_code,401)

    def test_oversized_login_is_rejected(self):
        _,p=policy()
        with TestClient(create_app(FakeInventory(),p,lambda:[])) as client:
            self.assertEqual(client.post("/login",content="x"*9000).status_code,413)

    def test_rate_limit(self):
        _,p=policy()
        with TestClient(create_app(FakeInventory(),p,lambda:[])) as client:
            client.get("/login"); nonce=client.cookies["siw_login"]
            for _ in range(5):
                self.assertEqual(client.post("/login",data={"csrf":nonce,"password":"invalid"}).status_code,401)
            self.assertEqual(client.post("/login",data={"csrf":nonce,"password":"invalid"}).status_code,429)

    def test_incomplete_auth_fails_closed(self):
        with patch.dict("os.environ",{"SIW_AUTH_ENABLED":"true","SIW_PASSWORD_HASH":"","SIW_SESSION_SECRET":""},clear=True):
            with self.assertRaises(RuntimeError): AccessPolicy.from_env()

    def test_networks_use_real_netmask_and_ignore_public(self):
        data=[{"flags":["UP"],"addr_info":[
            {"family":"inet","scope":"global","local":"192.168.88.35","prefixlen":23},
            {"family":"inet","scope":"global","local":"203.0.113.5","prefixlen":24}]}]
        self.assertEqual([str(net) for net in networks_from_addresses(data)],["192.168.88.0/23"])

if __name__=="__main__":
    unittest.main()
