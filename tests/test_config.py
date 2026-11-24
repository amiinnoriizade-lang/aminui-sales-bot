import os
import unittest
from cryptography.fernet import Fernet
from app.config import load_config

class TestConfig(unittest.TestCase):
    def test_legacy_dry_run_does_not_disable_provisioning(self):
        keys = {
            "BOT_TOKEN": "123456:TEST_TOKEN",
            "ADMIN_IDS": "123456789",
            "VPNUI_BASE_URL": "https://panel.example.com:2053",
            "VPNUI_USERNAME": "admin",
            "VPNUI_PASSWORD": "not-a-real-password",
            "APP_ENCRYPTION_KEY": Fernet.generate_key().decode(),
            "DRY_RUN": "true",
        }
        old = {key: os.environ.get(key) for key in keys}
        try:
            os.environ.update(keys)
            cfg = load_config()
            self.assertFalse(cfg.dry_run)
            self.assertTrue(cfg.verify_tls)
        finally:
            for key, value in old.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

if __name__ == "__main__":
    unittest.main()
