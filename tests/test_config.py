import os
import unittest
from unittest.mock import patch
from cryptography.fernet import Fernet
from app.config import load_config

class TestConfig(unittest.TestCase):
    def setUp(self):
        self.env = {
            'BOT_TOKEN': '123456:TEST_TOKEN',
            'ADMIN_IDS': '123456789',
            'VPNUI_BASE_URL': 'https://panel.example.com:2053',
            'VPNUI_USERNAME': 'admin',
            'VPNUI_PASSWORD': 'not-a-real-password',
            'VPN_PUBLIC_HOST': 'vpn.example.com',
            'APP_ENCRYPTION_KEY': Fernet.generate_key().decode(),
            'VPNUI_VERIFY_TLS': 'false',
            'DRY_RUN': 'true',
        }

    def test_release_uses_live_provisioning_and_enforces_tls(self):
        with patch.dict(os.environ, self.env, clear=True):
            cfg = load_config()
        self.assertFalse(cfg.dry_run)
        self.assertTrue(cfg.verify_tls)
        self.assertEqual(cfg.public_host, 'vpn.example.com')

    def test_public_vpn_host_is_required(self):
        env = dict(self.env)
        env.pop('VPN_PUBLIC_HOST')
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(RuntimeError, 'VPN_PUBLIC_HOST'):
                load_config()

if __name__ == '__main__':
    unittest.main()
