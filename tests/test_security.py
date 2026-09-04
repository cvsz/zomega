import os
import unittest
from unittest.mock import patch

ENV = {
    "zomega_PUBLIC_URL": "https://example.invalid",
    "DATABASE_URL": "postgresql+psycopg://zomega:zomega@localhost:5432/zomega",
    "REDIS_URL": "redis://localhost:6379/0",
    "zomega_API_KEY_PEPPER": "test-pepper-test-pepper-test-pepper-test-pepper",
    "zomega_ADMIN_TOKEN": "test-admin",
    "OPENAI_API_KEY": "test",
    "STRIPE_SECRET_KEY": "test",
    "STRIPE_WEBHOOK_SECRET": "test",
    "STRIPE_PRICE_CREDITS_1000": "price_1000",
    "STRIPE_PRICE_CREDITS_5000": "price_5000",
    "STRIPE_PRICE_CREDITS_20000": "price_20000",
}

class SecurityTest(unittest.TestCase):
    @patch.dict(os.environ, ENV, clear=False)
    def test_argon2_api_key_hash_is_salted_and_verifiable(self):
        from zomega.security import (
            generate_api_key,
            hash_api_key_secret,
            parse_api_key,
            verify_api_key_secret,
        )
        raw = generate_api_key()
        locator, secret = parse_api_key(raw)
        first = hash_api_key_secret(secret)
        second = hash_api_key_secret(secret)
        self.assertEqual(len(locator), 24)
        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith("$argon2id$"))
        self.assertTrue(verify_api_key_secret(first, secret))
        self.assertFalse(verify_api_key_secret(first, secret + "x"))

    @patch.dict(os.environ, ENV, clear=False)
    def test_api_key_parser_rejects_legacy_format(self):
        from zomega.security import parse_api_key
        with self.assertRaises(ValueError):
            parse_api_key("zomega_" + "x" * 48)

if __name__ == "__main__":
    unittest.main()
