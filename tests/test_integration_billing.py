import asyncio
import os
import uuid
import unittest

from sqlalchemy import select, func

@unittest.skipUnless(os.getenv("OMEGA_INTEGRATION") == "1", "integration services not enabled")
class BillingIntegrationTest(unittest.TestCase):
    def setUp(self):
        from omega.db import session_scope
        from omega.models import Tenant, Wallet
        self.tenant_id = str(uuid.uuid4())
        with session_scope() as db:
            db.add(Tenant(
                id=self.tenant_id,
                name="Integration Tenant",
                plan="pro",
                status="active",
            ))
            db.add(Wallet(
                tenant_id=self.tenant_id,
                available_credits=0,
                reserved_credits=0,
                version=0,
            ))

    def test_verified_payment_is_atomic_and_idempotent(self):
        from omega.billing import process_verified_payment, get_wallet
        from omega.db import session_scope
        from omega.models import WalletLedger, PaymentEvent

        event_id = "evt_" + uuid.uuid4().hex
        first = process_verified_payment(
            provider="stripe",
            provider_event_id=event_id,
            event_type="checkout.session.completed",
            tenant_id=self.tenant_id,
            credits=1000,
            payload_hash="a" * 64,
            status="verified",
        )
        second = process_verified_payment(
            provider="stripe",
            provider_event_id=event_id,
            event_type="checkout.session.completed",
            tenant_id=self.tenant_id,
            credits=1000,
            payload_hash="a" * 64,
            status="verified",
        )

        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(get_wallet(self.tenant_id)["available_credits"], 1000)

        with session_scope() as db:
            event_count = db.execute(
                select(func.count(PaymentEvent.id)).where(
                    PaymentEvent.provider_event_id == event_id
                )
            ).scalar_one()
            credit_count = db.execute(
                select(func.count(WalletLedger.id)).where(
                    WalletLedger.tenant_id == self.tenant_id,
                    WalletLedger.kind == "credit",
                    WalletLedger.reference_id == event_id,
                )
            ).scalar_one()
        self.assertEqual(event_count, 1)
        self.assertEqual(credit_count, 1)

    def test_idempotent_run_reserves_once(self):
        from omega.billing import process_verified_payment, get_wallet
        from omega.run_service import create_skill_run
        from omega.catalog import load_skills
        from omega.db import session_scope
        from omega.models import Reservation, IdempotencyRecord

        payment_id = "evt_" + uuid.uuid4().hex
        process_verified_payment(
            provider="stripe",
            provider_event_id=payment_id,
            event_type="checkout.session.completed",
            tenant_id=self.tenant_id,
            credits=1000,
            payload_hash="b" * 64,
            status="verified",
        )

        skill_id = "repository-intelligence"
        reservation = int(load_skills()[skill_id]["billing"]["reservation"])
        tenant = {"id": self.tenant_id, "plan": "pro"}
        idem = "idem-" + uuid.uuid4().hex

        first = asyncio.run(create_skill_run(
            tenant,
            skill_id,
            {"repository": "cvsz/zomega"},
            idem,
        ))
        second = asyncio.run(create_skill_run(
            tenant,
            skill_id,
            {"repository": "cvsz/zomega"},
            idem,
        ))

        self.assertEqual(first["run_id"], second["run_id"])
        self.assertTrue(second["replayed"])
        wallet = get_wallet(self.tenant_id)
        self.assertEqual(wallet["available_credits"], 1000 - reservation)
        self.assertEqual(wallet["reserved_credits"], reservation)

        with session_scope() as db:
            reservation_count = db.execute(
                select(func.count(Reservation.id)).where(
                    Reservation.tenant_id == self.tenant_id
                )
            ).scalar_one()
            idem_count = db.execute(
                select(func.count(IdempotencyRecord.id)).where(
                    IdempotencyRecord.tenant_id == self.tenant_id,
                    IdempotencyRecord.key == idem,
                )
            ).scalar_one()
        self.assertEqual(reservation_count, 1)
        self.assertEqual(idem_count, 1)

if __name__ == "__main__":
    unittest.main()
