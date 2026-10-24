"""Synthetic credentials only; tests never read production configuration."""
import asyncio
import contextlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
from websockets.asyncio.server import serve

spec = importlib.util.spec_from_file_location("setup_ha", Path(__file__).resolve().parents[1] / "scripts" / "setup_ha.py")
setup_ha = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup_ha)

def values():
    return dict(HA_URL="https://example.invalid", HA_TOKEN=secrets.token_hex(32),
                HA_ALLOW_HTTP="false")

@unittest.skipUnless(os.geteuid() == 0, "File ownership checks require LXC root")
class ConfigurationTests(unittest.TestCase):
    def test_roundtrip_and_permissions(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "private" / "app.env"
            original = values()
            setup_ha.save_config(original, path)
            self.assertEqual(setup_ha.load_config(path), original)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)

    def test_reject_readable_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "app.env"
            setup_ha.save_config(values(), path)
            path.chmod(0o644)
            with self.assertRaises(setup_ha.SetupError):
                setup_ha.load_config(path)

    def test_reject_symlink(self):
        with tempfile.TemporaryDirectory() as folder:
            real = Path(folder) / "real.env"
            link = Path(folder) / "link.env"
            setup_ha.save_config(values(), real)
            link.symlink_to(real)
            with self.assertRaises(setup_ha.SetupError):
                setup_ha.load_config(link)
            with self.assertRaises(setup_ha.SetupError):
                setup_ha.save_config(values(), link)

    def test_failed_validation_preserves_existing(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "app.env"
            original = values()
            setup_ha.save_config(original, path)
            invalid = dict(original, HA_TOKEN="invalid")
            with self.assertRaises(setup_ha.SetupError):
                setup_ha.save_config(invalid, path)
            self.assertEqual(setup_ha.load_config(path), original)

    def test_reject_url_credentials_and_parameters(self):
        for address in (setup_ha.urlunsplit(("https", ":".join(("person","example")) + "@example.invalid", "", "", "")), "https://example.invalid/?a=b",
                        "https://example.invalid/#fragment", "https://example.invalid/\n",
                        "file:///etc/passwd"):
            with self.subTest(address=address), self.assertRaises(setup_ha.SetupError):
                setup_ha.normalize_url(address)

    def test_legacy_inventory_setting_is_ignored(self):
        original = values()
        self.assertEqual(setup_ha.validate(dict(original, SIW_INVENTORY_ID="old_inventory")), original)

    def test_discovery_sorts_deduplicates_and_ignores_other_sensors(self):
        rows = [
            {"attributes":{"inventory_id":"z","total_items":1,"friendly_name":"Zebra"}},
            {"attributes":{"inventory_id":"a","total_items":0,"friendly_name":"Alpha"}},
            {"attributes":{"inventory_id":"other","friendly_name":"Not an inventory"}},
            {"attributes":{"inventory_id":"a","total_items":0,"friendly_name":"Alpha"}},
        ]
        self.assertEqual(setup_ha.inventories_from_states(rows), [("a","Alpha"),("z","Zebra")])

    def test_require_explicit_http_choice(self):
        with self.assertRaises(setup_ha.SetupError):
            setup_ha.validate(dict(values(), HA_URL="http://example.invalid"))

class WebsocketTests(unittest.IsolatedAsyncioTestCase):
    async def test_discover_and_read_saved_credentials_after_reload(self):
        credential = secrets.token_hex(32)
        commands = []
        async def handler(ws):
            await ws.send(json.dumps({"type":"auth_required"}))
            auth = json.loads(await ws.recv())
            self.assertEqual(auth["access_token"], credential)
            await ws.send(json.dumps({"type":"auth_ok"}))
            msg = json.loads(await ws.recv())
            commands.append(msg["type"])
            if msg["type"] == "get_states":
                result = [{"entity_id":"sensor.test_inventory","attributes":{
                    "inventory_id":"test_inventory","total_items":1,"friendly_name":"Test\u001bInventory"}}]
            else:
                self.assertEqual(msg["type"], "simple_inventory/list_items")
                result = {"items":[{"name":"test"}]}
            await ws.send(json.dumps({"id":msg["id"],"type":"result","success":True,"result":result}))
        async with serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            address = f"http://127.0.0.1:{port}"
            self.assertEqual(await setup_ha.query(address, credential),
                             [("test_inventory","Test?Inventory")])
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "app.env"
                setup_ha.save_config(dict(values(), HA_URL=address, HA_TOKEN=credential,
                                         HA_ALLOW_HTTP="true"), path)
                self.assertEqual(await setup_ha.check_saved(path), 1)
                # Another fresh connection loads disk settings again, without prompting.
                self.assertEqual(await setup_ha.check_saved(path), 1)
        self.assertEqual(commands, ["get_states","get_states","simple_inventory/list_items","get_states","simple_inventory/list_items"])

    async def test_auth_rejection_does_not_leak_credentials(self):
        credential = secrets.token_hex(32)
        async def handler(ws):
            await ws.send(json.dumps({"type":"auth_required"}))
            await ws.recv()
            await ws.send(json.dumps({"type":"auth_invalid","message":credential}))
        async with serve(handler,"127.0.0.1",0) as server:
            address = f"http://127.0.0.1:{server.sockets[0].getsockname()[1]}"
            with self.assertRaises(setup_ha.SetupError) as caught:
                await setup_ha.query(address,credential)
            self.assertNotIn(credential,str(caught.exception))

    async def test_missing_api_does_not_leak_remote_payload(self):
        credential = secrets.token_hex(32)
        async def handler(ws):
            await ws.send(json.dumps({"type":"auth_required"}))
            await ws.recv()
            await ws.send(json.dumps({"type":"auth_ok"}))
            msg = json.loads(await ws.recv())
            await ws.send(json.dumps({"id":msg["id"],"type":"result","success":False,
                                      "error":{"message":credential}}))
        async with serve(handler,"127.0.0.1",0) as server:
            address=f"http://127.0.0.1:{server.sockets[0].getsockname()[1]}"
            with self.assertRaises(setup_ha.SetupError) as caught:
                await setup_ha.query(address,credential,"test_inventory")
            self.assertNotIn(credential,str(caught.exception))

if __name__ == "__main__":
    unittest.main()
