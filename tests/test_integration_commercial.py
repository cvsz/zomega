import asyncio
import base64
import os
import uuid
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi import HTTPException

@unittest.skipUnless(os.getenv("OMEGA_INTEGRATION") == "1", "integration services not enabled")
class CommercialIntegrationTest(unittest.TestCase):
    def _tenant(self, name: str, credits: int) -> tuple[str, str]:
        from omega.admin import DEFAULT_SCOPES
        from omega.db import session_scope
        from omega.models import Tenant, Wallet, ApiKey, WalletLedger
        from omega.security import generate_api_key, parse_api_key, hash_api_key_secret

        tenant_id = str(uuid.uuid4())
        raw = generate_api_key()
        prefix, secret = parse_api_key(raw)
        with session_scope() as db:
            db.add(Tenant(id=tenant_id, name=name, plan="pro", status="active"))
            db.flush()
            db.add(Wallet(
                tenant_id=tenant_id,
                available_credits=credits,
                reserved_credits=0,
                version=0,
            ))
            if credits:
                db.add(WalletLedger(
                    tenant_id=tenant_id,
                    kind="credit",
                    amount=credits,
                    reference_type="test_seed",
                    reference_id=str(uuid.uuid4()),
                    metadata_json={},
                ))
            key = ApiKey(
                tenant_id=tenant_id,
                name="primary",
                key_prefix=prefix,
                key_digest=hash_api_key_secret(secret),
                scopes=DEFAULT_SCOPES,
                active=True,
            )
            db.add(key)
            db.flush()
            return tenant_id, key.id

    def test_quota_subscription_and_dashboard(self):
        from omega.catalog import load_skills
        from omega.commercial import set_control, set_subscription, dashboard_summary
        from omega.run_service import create_skill_run

        tenant_id, _ = self._tenant("Quota Tenant", 5000)
        skill_id = "repository-intelligence"
        skill = load_skills()[skill_id]

        set_control(
            tenant_id,
            monthly_credit_limit=5000,
            monthly_run_limit=1,
            allowed_agents=[skill["agent"]],
            allowed_skills=[skill_id],
            audit_retention_days=90,
        )
        set_subscription(tenant_id, plan="pro", status="active")

        first = asyncio.run(create_skill_run(
            {"id": tenant_id, "plan": "pro"},
            skill_id,
            {"repository": "cvsz/zomega"},
            "quota-first",
        ))
        self.assertIn(first["status"], {"QUEUED", "PENDING_DISPATCH"})

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(create_skill_run(
                {"id": tenant_id, "plan": "pro"},
                skill_id,
                {"repository": "cvsz/zomega"},
                "quota-second",
            ))
        self.assertEqual(ctx.exception.status_code, 429)

        dashboard = dashboard_summary(tenant_id)
        self.assertEqual(dashboard["usage"]["runs"], 1)
        self.assertEqual(dashboard["subscription"]["plan"], "pro")
        self.assertEqual(dashboard["control"]["monthly_run_limit"], 1)

    def test_signed_registry_marketplace_purchase_and_reconciliation(self):
        from omega.billing import reconcile_wallet
        from omega.db import session_scope
        from omega.models import PrivateSkillGrant, MarketplaceLedger
        from omega.registry import (
            canonical_manifest, create_or_update_publisher, publish_skill, list_granted_skills,
            verify_skill_version
        )
        from omega.marketplace import (
            create_listing, purchase_listing, publisher_earnings
        )

        publisher_tenant, publisher_key = self._tenant("Publisher", 0)
        buyer_tenant, buyer_key = self._tenant("Buyer", 2500)

        private_key = Ed25519PrivateKey.generate()
        public_pem = private_key.public_key().public_bytes(
            Encoding.PEM,
            PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")
        publisher = create_or_update_publisher(
            publisher_tenant,
            publisher_key,
            "ZeaZ Publisher",
            public_pem,
        )
        self.assertEqual(publisher["status"], "active")

        manifest = {
            "id": "private-repo-audit",
            "version": "1.0.0",
            "artifact": "oci://registry.example/private-repo-audit@sha256:abc",
            "permissions": ["repository:read"],
        }
        signature = base64.b64encode(
            private_key.sign(canonical_manifest(manifest))
        ).decode("ascii")
        skill = publish_skill(
            publisher_tenant,
            publisher_key,
            skill_id="private-repo-audit",
            version="1.0.0",
            manifest=manifest,
            signature_b64=signature,
        )

        verification = verify_skill_version(skill["id"])
        self.assertTrue(verification["valid"])

        listing = create_listing(
            publisher_tenant,
            publisher_key,
            skill["id"],
            1000,
            8000,
        )
        purchase = purchase_listing(
            buyer_tenant,
            buyer_key,
            listing["id"],
            "purchase-1",
        )
        replay = purchase_listing(
            buyer_tenant,
            buyer_key,
            listing["id"],
            "purchase-1",
        )
        self.assertFalse(purchase["replayed"])
        self.assertTrue(replay["replayed"])
        self.assertEqual(purchase["publisher_credits"], 800)
        self.assertEqual(purchase["platform_credits"], 200)

        grants = list_granted_skills(buyer_tenant)
        self.assertEqual(len(grants), 1)
        self.assertEqual(grants[0]["skill_id"], "private-repo-audit")

        reconciliation = reconcile_wallet(buyer_tenant)
        self.assertTrue(reconciliation["ok"])
        self.assertEqual(reconciliation["available_credits"], 1500)

        earnings = publisher_earnings(publisher_tenant)
        self.assertEqual(earnings["publisher_credits"], 800)
        self.assertEqual(earnings["sales"], 1)
        publisher_reconciliation = reconcile_wallet(publisher_tenant)
        self.assertTrue(publisher_reconciliation["ok"])
        self.assertEqual(publisher_reconciliation["available_credits"], 800)

        with session_scope() as db:
            self.assertEqual(
                len(db.query(PrivateSkillGrant).filter_by(tenant_id=buyer_tenant).all()),
                1,
            )
            self.assertEqual(
                len(db.query(MarketplaceLedger).filter_by(buyer_tenant_id=buyer_tenant).all()),
                1,
            )

if __name__ == "__main__":
    unittest.main()
