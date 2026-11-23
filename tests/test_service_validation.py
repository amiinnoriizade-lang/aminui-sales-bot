import unittest
from app.service import create_panel_account
from app.vpnui import VPNUIError

class NeverCalledPanel:
    async def get_inbound(self, inbound):
        raise AssertionError("panel must not be contacted for invalid input")

class TestServiceValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_unknown_protocol_before_panel_request(self):
        with self.assertRaises(VPNUIError):
            await create_panel_account(NeverCalledPanel(), object(), "unknown", 1, "user1", 1, 1, 1)

    async def test_rejects_invalid_volume_before_panel_request(self):
        with self.assertRaises(VPNUIError):
            await create_panel_account(NeverCalledPanel(), object(), "vless", 1, "user1", 1, -1, 1)

    async def test_rejects_invalid_telegram_id_before_panel_request(self):
        with self.assertRaises(VPNUIError):
            await create_panel_account(NeverCalledPanel(), object(), "vless", 1, "user1", 0, 1, 1)
