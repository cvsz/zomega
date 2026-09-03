import os
import unittest
from unittest.mock import patch

class SecurityTest(unittest.TestCase):
    @patch.dict(os.environ, {
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
    }, clear=False)
    def test_api_key_digest_is_deterministic_and_not_plaintext(self):
        from omega.security import digest_api_key
        raw = "omega_" + "x" * 48
        first = digest_api_key(raw)
        second = digest_api_key(raw)
        self.assertEqual(first, second)
        self.assertNotEqual(first, raw)
        self.assertEqual(len(first), 128)

if __name__ == "__main__":
    unittest.main()
