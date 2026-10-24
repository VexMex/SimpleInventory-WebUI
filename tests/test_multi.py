"""Multiple inventories: discovery, isolated forms and no inventory administration."""
import copy
import unittest
from contextlib import asynccontextmanager
from types import SimpleNamespace
from fastapi.testclient import TestClient
from webui.web import AccessPolicy, InventoryClient, create_app
from test_items import form
from test_setup_ha import setup_ha

class MultipleInventory(InventoryClient):
    def __init__(self):
        self.names = {"z":"Zebra", "a":"Alpha"}
        self.rows = {
            "a":[{"name":"Shared name","quantity":1,"category":"Alpha group","unit":"kg"}],
            "z":[{"name":"Shared name","quantity":9,"category":"Zebra group","unit":"pcs"}]}
        self.mutations = []
    @asynccontextmanager
    async def connection(self):
        async def request(ws, number, command, **kwargs):
            if command == "get_states":
                return [{"attributes":{"inventory_id":key,"friendly_name":name,"total_items":len(self.rows[key])}}
                        for key,name in self.names.items()]
            if command == "simple_inventory/list_items":
                return {"items":copy.deepcopy(self.rows[kwargs["inventory_id"]])}
            if command != "call_service":
                raise AssertionError("Unexpected command")
            self.mutations.append(copy.deepcopy(kwargs))
            data = kwargs["service_data"]
            items = self.rows[data["inventory_id"]]
            if "old_name" in data:
                row = next(row for row in items if row["name"] == data["old_name"])
                row.update({key:value for key,value in data.items() if key not in {"inventory_id","old_name"}})
            else:
                items.append({key:value for key,value in data.items() if key != "inventory_id"})
        helper = SimpleNamespace(request=request, inventories_from_states=setup_ha.inventories_from_states)
        yield helper, None, {}

class MultiTests(unittest.TestCase):
    def setUp(self):
        self.backend = MultipleInventory()
        self.client = TestClient(create_app(self.backend, AccessPolicy()))
        self.client.__enter__()
    def tearDown(self):
        self.client.__exit__(None,None,None)

    def test_alphabetic_default_and_explicit_selection(self):
        data = self.client.get("/api/inventory").json()
        self.assertEqual(data["id"], "a")
        self.assertEqual([row["id"] for row in data["inventories"]], ["a","z"])
        self.assertEqual(self.client.get("/api/inventory?inventory=z").json()["items"][0]["quantity"], 9)
        page = self.client.get("/?inventory=z")
        self.assertIn('value="z" selected', page.text)
        self.assertIn('/items/new?inventory=z', page.text)

    def test_choices_and_cancellation_stay_in_selected_inventory(self):
        page = self.client.get("/items/new?inventory=z")
        self.assertIn('<option value="Zebra group">', page.text)
        self.assertNotIn('<option value="Alpha group">', page.text)
        self.assertIn('href="/?inventory=z"', page.text)
        self.assertIn("Inventar: <strong>Zebra</strong>", page.text)

    def test_signed_form_stays_in_original_inventory_across_tabs(self):
        values = form(self.client, "/items/edit?inventory=z&item=Shared%20name")
        values.update(name="Changed", quantity="10")
        self.client.get("/?inventory=a")
        result = self.client.post("/items/edit?inventory=a", data=values, follow_redirects=False)
        self.assertEqual(result.status_code, 303)
        self.assertEqual(result.headers["location"], "/?inventory=z&saved=1")
        self.assertEqual(self.backend.rows["a"][0]["quantity"], 1)
        self.assertEqual(self.backend.rows["z"][0]["quantity"], 10)
        self.assertEqual(self.backend.mutations[0]["service_data"]["inventory_id"], "z")

    def test_unknown_or_removed_inventory_never_falls_back(self):
        self.assertEqual(self.client.get("/?inventory=unknown").status_code, 404)
        self.assertEqual(self.client.get("/api/inventory?inventory=unknown").status_code, 404)
        self.assertEqual(self.client.get("/items/new?inventory=unknown").status_code, 404)
        values = form(self.client, "/items/new?inventory=z")
        del self.backend.names["z"]
        self.assertEqual(self.client.post("/items/new", data=values).status_code, 404)
        self.assertEqual(self.backend.mutations, [])

    def test_no_inventory_has_clear_message_and_no_add_link(self):
        self.backend.names.clear()
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Keine Inventare verfügbar", page.text)
        self.assertNotIn('href="/items/new', page.text)
        self.assertEqual(self.client.get("/items/new").status_code, 404)

if __name__ == "__main__":
    unittest.main()
