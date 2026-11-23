import asyncio
import unittest
import httpx
from app.service import create_panel_account
from app.vpnui import VPNUIClient

class FakePanel:
    def __init__(self):
        self.created = None
    async def get_inbound(self, iid):
        return {'id': iid, 'protocol': 'openvpn', 'enable': True, 'settings': {'tcpEnable': True, 'udpEnable': True}}
    async def add_client(self, iid, client):
        self.created = (iid, client)
        return {'success': True}

class TestOpenVPN(unittest.TestCase):
    def test_account_creation_uses_unique_username_and_password_identity(self):
        async def run():
            panel = FakePanel()
            made = await create_panel_account(panel, None, 'openvpn', 30, 'alice_01', 12345, 5, 1)
            self.assertEqual(panel.created[0], 30)
            client = panel.created[1]
            self.assertEqual(client['id'], 'alice_01')
            self.assertEqual(client['email'], 'alice_01')
            self.assertEqual(client['password'], made['credential'])
            self.assertEqual(made['identity'], client['password'])
            self.assertEqual(client['totalGB'], 5 * 1024**3)
            self.assertTrue(client['enable'])
        asyncio.run(run())


    def test_disabled_transport_is_rejected_before_panel_write(self):
        class DisabledPanel(FakePanel):
            async def get_inbound(self, iid):
                return {'id': iid, 'protocol': 'openvpn', 'enable': True, 'settings': {'tcpEnable': False, 'udpEnable': True}}
        async def run():
            with self.assertRaises(Exception):
                await create_panel_account(DisabledPanel(), None, 'openvpn', 30, 'alice_02', 12345, 1, 1, transport='tcp')
        asyncio.run(run())

    def test_openvpn_renewal_uses_password_identity(self):
        from app.service import renew_panel_account
        class RenewPanel:
            def __init__(self):
                self.client={'id':'alice_03','password':'pw-123','email':'alice_03','enable':True,'expiryTime':0,'totalGB':1}
                self.updated=None
            async def get_inbound(self, iid): return {'settings':{'clients':[self.client]}}
            async def update_client(self, iid, identity, client):
                self.updated=(iid,identity,dict(client)); return {'success':True}
        async def run():
            panel=RenewPanel()
            account={'inbound_id':30,'protocol':'openvpn','panel_identity':'pw-123','expiry_ms':0}
            await renew_panel_account(panel,account,1,3)
            self.assertEqual(panel.updated[1],'pw-123')
            self.assertEqual(panel.updated[2]['totalGB'],3*1024**3)
        asyncio.run(run())

    def test_existing_usernames_skips_inbounds_with_null_clients(self):
        class UsernamePanel(VPNUIClient):
            async def list_inbounds(self):
                return [{'id': 30}, {'id': 31}]
            async def get_inbound(self, iid):
                if iid == 30:
                    return {'settings': {'clients': None}}
                return {'settings': {'clients': [{'email': 'Known_User'}]}}
        async def run():
            panel = UsernamePanel('https://panel.invalid', 'a', 'b')
            try:
                names = await panel.existing_usernames([30])
                self.assertEqual(names, {'known_user'})
            finally:
                await panel.close()
        asyncio.run(run())

    def test_profile_is_downloaded_from_selected_inbound_transport(self):
        calls = []
        profile = b'client\ndev tun\nproto tcp\nremote example.invalid 443\nauth-user-pass\n'
        def handler(request):
            calls.append((request.method, request.url.path))
            if request.url.path.endswith('/login'):
                return httpx.Response(200, json={'success': True, 'obj': {}})
            return httpx.Response(200, content=profile, headers={'content-type':'application/x-openvpn-profile'})
        async def run():
            client = VPNUIClient('https://panel.invalid/basepath', 'admin', 'secret', dry_run=False)
            await client.http.aclose()
            client.http = httpx.AsyncClient(transport=httpx.MockTransport(handler), headers={'X-Requested-With':'XMLHttpRequest'})
            try:
                result = await client.download_openvpn_profile(30, 'tcp')
                self.assertEqual(result, profile)
                self.assertIn('/basepath/panel/api/inbounds/30/ovpn/tcp', calls[-1][1])
            finally:
                await client.close()
        asyncio.run(run())

if __name__ == '__main__':
    unittest.main()
