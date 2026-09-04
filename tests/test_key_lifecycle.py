import os
import unittest
from unittest.mock import patch

ENV = {
    "OMEGA_PUBLIC_URL": "https://example.invalid",
    "DATABASE_URL": "postgresql+psycopg://omega:omega@localhost:5432/omega",
    "REDIS_URL": "redis://localhost:6379/0",
    "OMEGA_API_KEY_PEPPER": "test-pepper-test-pepper-test-pepper-test-pepper",
    "OMEGA_ADMIN_TOKEN": "test-admin",
    "OPENAI_API_KEY": "test",
    "STRIPE_SECRET_KEY": "test",
    "STRIPE_WEBHOOK_SECRET": "test",
    "STRIPE_PRICE_CREDITS_1000": "price_1000",
    "STRIPE_PRICE_CREDITS_5000": "price_5000",
    "STRIPE_PRICE_CREDITS_20000": "price_20000",
}

class KeyLifecycleContractTest(unittest.TestCase):
    @patch.dict(os.environ, ENV, clear=False)
    def test_control_plane_scopes_exist(self):
        from omega.key_service import ALLOWED_SCOPES
        self.assertIn("keys:read", ALLOWED_SCOPES)
        self.assertIn("keys:write", ALLOWED_SCOPES)
        self.assertIn("audit:read", ALLOWED_SCOPES)

if __name__ == "__main__":
    unittest.main()
