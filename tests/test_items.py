"""Item forms and HA service adapter; synthetic data only."""
import copy
import html
import re
import sys
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from fastapi.testclient import TestClient
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from webui.web import (AccessPolicy, InventoryClient, InventoryUnavailable, WriteConflict,
                      WriteUncertain, create_app, exact_item, fingerprint, validate_fields)
from test_web import policy

class MemoryInventory:
    def __init__(self):
        self.items = [{"name":"Bolt", "quantity":2, "unit":"pcs", "category":"Hardware", "location":"Shelf"}]
        self.writes = 0
        self.failure = None
    async def read(self):
        return {"name":"Inventory", "items":copy.deepcopy(self.items)}
    async def write(self, fields, old_name=None, expected=None):
        self.writes += 1
        if self.failure:
            raise self.failure()
        if old_name is not None:
            current = exact_item(self.items, old_name)
            if fingerprint(current) != expected:
                raise WriteConflict()
            self.items.remove(current)
        self.items.append(copy.deepcopy(fields))

def form(client, path="/items/new"):
    page = client.get(path)
    assert page.status_code == 200
    proof = html.unescape(re.search(r'name="proof" value="([^"]+)"', page.text).group(1))
    return {"proof":proof, "name":"Nut", "quantity":"3,5", "unit":"pcs", "category":"Hardware", "location":"Shelf"}

class ItemTests(unittest.TestCase):
    def setUp(self):
        self.backend = MemoryInventory()
        self.client = TestClient(create_app(self.backend, AccessPolicy()))
        self.client.__enter__()
    def tearDown(self):
        self.client.__exit__(None, None, None)

    def test_add_and_replay(self):
        values = form(self.client)
        response = self.client.post("/items/new", data=values, follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(self.backend.items[-1]["quantity"], 3.5)
        self.assertEqual(self.client.post("/items/new", data=values).status_code, 409)
        self.assertEqual(self.backend.writes, 1)
        self.assertIn("Artikel gespeichert.", self.client.get(response.headers["location"]).text)

    def test_edit_prefills_and_renames(self):
        values = form(self.client, "/items/edit?item=Bolt")
        values.update(name="Long Bolt", quantity="0")
        self.assertEqual(self.client.post("/items/edit", data=values, follow_redirects=False).status_code, 303)
        self.assertEqual(self.backend.items[0]["name"], "Long Bolt")
        self.assertEqual(self.backend.items[0]["quantity"], 0)

    def test_stale_edit_cannot_overwrite(self):
        values = form(self.client, "/items/edit?item=Bolt")
        self.backend.items[0]["quantity"] = 9
        self.assertEqual(self.client.post("/items/edit", data=values).status_code, 409)
        self.assertEqual(self.backend.items[0]["quantity"], 9)

    def test_csrf_and_action_tampering(self):
        values = form(self.client)
        self.assertEqual(self.client.post("/items/edit", data=values).status_code, 400)
        self.client.cookies.clear()
        self.assertEqual(self.client.post("/items/new", data=values).status_code, 400)
        values["proof"] = "invalid"
        self.assertEqual(self.client.post("/items/new", data=values).status_code, 400)
        self.assertEqual(self.backend.writes, 0)

    def test_invalid_values_do_not_write(self):
        values = form(self.client)
        for amount in ("-1", "NaN", "inf", "1e2", "", "1000000001", "1.1234567"):
            values["quantity"] = amount
            self.assertEqual(self.client.post("/items/new", data=values).status_code, 422)
        values.update(quantity="1", name=" ")
        self.assertEqual(self.client.post("/items/new", data=values).status_code, 422)
        self.assertEqual(self.backend.writes, 0)

    def test_unknown_fields_and_oversized_body(self):
        values = form(self.client)
        values["inventory_id"] = "other"
        self.assertEqual(self.client.post("/items/new", data=values).status_code, 400)
        self.assertEqual(self.client.post("/items/new", content="x"*17000,
                         headers={"content-type":"application/x-www-form-urlencoded"}).status_code, 413)

    def test_uncertain_write_is_not_retried(self):
        self.backend.failure = WriteUncertain
        values = form(self.client)
        self.assertEqual(self.client.post("/items/new", data=values).status_code, 502)
        self.assertEqual(self.client.post("/items/new", data=values).status_code, 409)
        self.assertEqual(self.backend.writes, 1)

    def test_backend_unavailable(self):
        self.backend.failure = InventoryUnavailable
        self.assertEqual(self.client.post("/items/new", data=form(self.client)).status_code, 503)

    def test_edit_html_escapes_content(self):
        self.backend.items[0]["name"] = '<script>"Bolt"</script>'
        page = self.client.get("/items/edit", params={"item":self.backend.items[0]["name"]})
        self.assertEqual(page.status_code, 200)
        self.assertNotIn("<script>", page.text)
        self.assertIn("&lt;script&gt;", page.text)

    def test_choices_collect_multiple_values_and_escape_html(self):
        self.backend.items += [
            {"name":"Washer", "categories":["Hardware", "Metal"], "locations":["Shelf", "Box"]},
            {"name":"Pin", "category":"Metal, Small", "location":'Box, <img src=x>'},
        ]
        for path in ("/items/new", "/items/edit?item=Bolt"):
            page = self.client.get(path)
            self.assertEqual(page.status_code, 200)
            category = re.search(r'<datalist id="category-options">(.*?)</datalist>', page.text, re.S).group(1)
            locations = re.search(r'<datalist id="location-options">(.*?)</datalist>', page.text, re.S).group(1)
            self.assertEqual(category.count('value="Hardware"'), 1)
            self.assertIn('value="Metal"', category)
            self.assertIn('value="Small"', category)
            self.assertIn('value="Box"', locations)
            self.assertIn("&lt;img src=x&gt;", locations)
            self.assertNotIn("<img src=x>", page.text)

    def test_new_values_save_and_become_choices(self):
        values = form(self.client)
        values.update(category="New group", location="New room")
        response = self.client.post("/items/new", data=values, follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        page = self.client.get("/items/new")
        self.assertIn('<option value="New group">', page.text)
        self.assertIn('<option value="New room">', page.text)
        values = form(self.client)
        values.update(name="Unassigned item", category="", location="")
        self.assertEqual(self.client.post("/items/new", data=values, follow_redirects=False).status_code, 303)

    def test_optional_auth_covers_writes(self):
        _, settings = policy()
        with TestClient(create_app(self.backend, settings, lambda:[]),
                        client=("203.0.113.7", 1000)) as client:
            self.assertEqual(client.get("/items/new", follow_redirects=False).status_code, 303)
            self.assertEqual(client.post("/items/new", data={}, follow_redirects=False).status_code, 303)
        self.assertEqual(self.backend.writes, 0)

class Adapter(InventoryClient):
    def __init__(self, items, ignore=False, fail=False):
        self.items = copy.deepcopy(items)
        self.calls = []
        self.ignore = ignore
        self.fail = fail
    @asynccontextmanager
    async def connection(self):
        async def request(ws, number, command, **kwargs):
            if command == "simple_inventory/list_items":
                return {"items":copy.deepcopy(self.items)}
            self.calls.append(kwargs)
            if self.fail:
                raise OSError("private details")
            if not self.ignore:
                data = kwargs["service_data"]
                if "old_name" in data:
                    row = exact_item(self.items, data["old_name"])
                    row.update({key:value for key,value in data.items() if key not in {"inventory_id","old_name"}})
                else:
                    self.items.append({key:value for key,value in data.items() if key != "inventory_id"})
        yield SimpleNamespace(request=request), None, {"SIW_INVENTORY_ID":"configured"}

class AdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_add_service_uses_configured_inventory(self):
        client = Adapter([])
        fields = validate_fields({"name":"Nut", "quantity":"2", "unit":"pcs"})
        await client.write(fields)
        self.assertEqual(client.calls[0]["service"], "add_item")
        self.assertEqual(client.calls[0]["domain"], "simple_inventory")
        self.assertEqual(client.calls[0]["service_data"]["inventory_id"], "configured")

    async def test_update_preserves_extra_metadata(self):
        original = {"name":"Bolt","quantity":2,"unit":"","category":"","location":"",
                    "barcode":"example-barcode","description":"Keep this"}
        client = Adapter([original])
        await client.write({"name":"Long Bolt","quantity":"4"}, "Bolt", fingerprint(original))
        self.assertEqual(client.calls[0]["service"], "update_item")
        self.assertEqual(client.items[0]["description"], "Keep this")
        self.assertEqual(client.items[0]["barcode"], "example-barcode")
        self.assertNotIn("barcode", client.calls[0]["service_data"])

    async def test_duplicates_and_aliases_rejected_before_dispatch(self):
        for row in ({"name":"Nut"}, {"name":"Other","aliases":["Nut"]}):
            client = Adapter([row])
            with self.assertRaises(WriteConflict):
                await client.write({"name":"nut","quantity":"1"})
            self.assertEqual(client.calls, [])

    async def test_stale_adapter_rejected_before_dispatch(self):
        row = {"name":"Bolt","quantity":2}
        client = Adapter([row])
        with self.assertRaises(WriteConflict):
            await client.write({"name":"Bolt","quantity":"4"}, "Bolt", "stale")
        self.assertEqual(client.calls, [])

    async def test_silent_failure_and_transport_failure_are_uncertain(self):
        for client in (Adapter([], ignore=True), Adapter([], fail=True)):
            with self.assertRaises(WriteUncertain):
                await client.write({"name":"Nut","quantity":"1"})
            self.assertEqual(len(client.calls), 1)

if __name__ == "__main__":
    unittest.main()
