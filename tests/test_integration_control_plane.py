import os
import uuid
import unittest

from sqlalchemy import select

@unittest.skipUnless(os.getenv("zomega_INTEGRATION") == "1", "integration services not enabled")
class ControlPlaneIntegrationTest(unittest.TestCase):
    def setUp(self):
        from zomega.admin import DEFAULT_SCOPES
        from zomega.db import session_scope
        from zomega.models import Tenant, Wallet, ApiKey
        from zomega.security import generate_api_key, hash_api_key_secret, parse_api_key

        self.tenant_id = str(uuid.uuid4())
        self.primary_raw = generate_api_key()
        prefix, secret = parse_api_key(self.primary_raw)

        with session_scope() as db:
            db.add(Tenant(
                id=self.tenant_id,
                name="Control Plane Tenant",
                plan="pro",
                status="active",
            ))
            db.flush()
            db.add(Wallet(
                tenant_id=self.tenant_id,
                available_credits=0,
                reserved_credits=0,
                version=0,
            ))
            primary = ApiKey(
                tenant_id=self.tenant_id,
                name="primary",
                key_prefix=prefix,
                key_digest=hash_api_key_secret(secret),
                scopes=DEFAULT_SCOPES,
                active=True,
            )
            db.add(primary)
            db.flush()
            self.primary_id = primary.id

    def test_key_create_auth_audit_and_revoke(self):
        from zomega.auth import authenticate
        from zomega.audit import list_audit_events
        from zomega.key_service import create_api_key, create_service_account, list_api_keys, revoke_api_key

        created = create_api_key(
            tenant_id=self.tenant_id,
            actor_key_id=self.primary_id,
            name="worker",
            scopes=["runs:read", "skills:run"],
        )
        self.assertTrue(created["api_key"].startswith("zomega_"))

        tenant = authenticate(created["api_key"], "skills:run")
        self.assertEqual(tenant["id"], self.tenant_id)

        keys = list_api_keys(self.tenant_id)
        self.assertEqual(len(keys), 2)
        self.assertNotIn("api_key", keys[0])

        events = list_audit_events(self.tenant_id)
        self.assertEqual(events[0]["action"], "api_key.created")
        self.assertNotIn("api_key", events[0]["metadata"])

        revoked = revoke_api_key(self.tenant_id, self.primary_id, created["id"])
        self.assertFalse(revoked["active"])

        with self.assertRaises(Exception):
            authenticate(created["api_key"], "skills:run")

        events = list_audit_events(self.tenant_id)
        self.assertEqual(events[0]["action"], "api_key.revoked")

        service = create_service_account(
            self.tenant_id,
            self.primary_id,
            "automation-worker",
            "operator",
        )
        self.assertEqual(service["key_type"], "service_account")
        self.assertEqual(service["role"], "operator")
        service_tenant = authenticate(service["api_key"], "skills:run")
        self.assertEqual(service_tenant["role"], "operator")
        self.assertEqual(service_tenant["key_type"], "service_account")

        with self.assertRaises(Exception):
            create_api_key(
                self.tenant_id,
                self.primary_id,
                "bad-billing-operator",
                scopes=["billing:write"],
                key_type="service_account",
                role="operator",
            )

if __name__ == "__main__":
    unittest.main()
