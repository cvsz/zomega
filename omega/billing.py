from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from fastapi import HTTPException
from .db import session_scope
from .models import Wallet, WalletLedger, Reservation, PaymentEvent

def get_wallet(tenant_id: str) -> dict:
    with session_scope() as db:
        wallet = db.get(Wallet, tenant_id)
        if not wallet:
            raise HTTPException(404, "Wallet not found")
        return {
            "tenant_id": wallet.tenant_id,
            "available_credits": wallet.available_credits,
            "reserved_credits": wallet.reserved_credits,
        }

def process_verified_payment(
    *,
    provider: str,
    provider_event_id: str,
    event_type: str,
    tenant_id: str | None,
    credits: int,
    payload_hash: str,
    status: str,
) -> dict:
    """Idempotently record a provider event and credit the wallet in one transaction."""
    with session_scope() as db:
        inserted = db.execute(
            pg_insert(PaymentEvent)
            .values(
                provider=provider,
                provider_event_id=provider_event_id,
                event_type=event_type,
                tenant_id=tenant_id,
                credits=credits,
                payload_hash=payload_hash,
                status=status,
            )
            .on_conflict_do_nothing(index_elements=["provider_event_id"])
            .returning(PaymentEvent.id)
        ).scalar_one_or_none()

        if inserted is None:
            existing = db.execute(
                select(PaymentEvent).where(PaymentEvent.provider_event_id == provider_event_id)
            ).scalar_one()
            return {"received": True, "duplicate": True, "status": existing.status}

        if status == "verified":
            if not tenant_id or credits <= 0:
                raise ValueError("verified payment requires tenant_id and positive credits")
            wallet = db.execute(
                select(Wallet).where(Wallet.tenant_id == tenant_id).with_for_update()
            ).scalar_one_or_none()
            if not wallet:
                raise HTTPException(404, "Wallet not found")
            wallet.available_credits += credits
            wallet.version += 1
            db.add(WalletLedger(
                tenant_id=tenant_id,
                kind="credit",
                amount=credits,
                reference_type="payment_event",
                reference_id=provider_event_id,
                metadata_json={"provider": provider, "event_type": event_type},
            ))
        return {"received": True, "duplicate": False, "status": status}

def settle_run(run_id: str, actual_charge: int):
    with session_scope() as db:
        reservation = db.execute(
            select(Reservation).where(Reservation.run_id == run_id).with_for_update()
        ).scalar_one()
        if reservation.status != "reserved":
            raise RuntimeError("Reservation is not open")
        if actual_charge < 0 or actual_charge > reservation.amount:
            raise RuntimeError("Charge exceeds reserved amount")

        wallet = db.execute(
            select(Wallet).where(Wallet.tenant_id == reservation.tenant_id).with_for_update()
        ).scalar_one()
        refund = reservation.amount - actual_charge
        wallet.reserved_credits -= reservation.amount
        wallet.available_credits += refund
        wallet.version += 1
        reservation.status = "settled"
        reservation.settled_amount = actual_charge

        if actual_charge:
            db.add(WalletLedger(
                tenant_id=reservation.tenant_id,
                kind="charge",
                amount=-actual_charge,
                reference_type="run",
                reference_id=run_id,
                metadata_json={},
            ))
        if refund:
            db.add(WalletLedger(
                tenant_id=reservation.tenant_id,
                kind="refund",
                amount=refund,
                reference_type="reservation",
                reference_id=reservation.id,
                metadata_json={"reason": "unused_reservation"},
            ))

def refund_run(run_id: str, reason: str):
    with session_scope() as db:
        reservation = db.execute(
            select(Reservation).where(Reservation.run_id == run_id).with_for_update()
        ).scalar_one_or_none()
        if not reservation or reservation.status != "reserved":
            return
        wallet = db.execute(
            select(Wallet).where(Wallet.tenant_id == reservation.tenant_id).with_for_update()
        ).scalar_one()
        wallet.reserved_credits -= reservation.amount
        wallet.available_credits += reservation.amount
        wallet.version += 1
        reservation.status = "refunded"
        db.add(WalletLedger(
            tenant_id=reservation.tenant_id,
            kind="refund",
            amount=reservation.amount,
            reference_type="reservation",
            reference_id=reservation.id,
            metadata_json={"reason": reason[:200]},
        ))

def reconcile_wallet(tenant_id: str) -> dict:
    with session_scope() as db:
        wallet = db.execute(
            select(Wallet).where(Wallet.tenant_id == tenant_id).with_for_update()
        ).scalar_one()
        open_reserved = db.execute(
            select(func.coalesce(func.sum(Reservation.amount), 0)).where(
                Reservation.tenant_id == tenant_id,
                Reservation.status == "reserved",
            )
        ).scalar_one()
        ledger_net = db.execute(
            select(func.coalesce(func.sum(WalletLedger.amount), 0)).where(
                WalletLedger.tenant_id == tenant_id,
                WalletLedger.kind.in_(["credit", "charge"]),
            )
        ).scalar_one()
        observed_total = wallet.available_credits + wallet.reserved_credits
        ok = (
            wallet.available_credits >= 0
            and wallet.reserved_credits >= 0
            and wallet.reserved_credits == int(open_reserved)
            and observed_total == int(ledger_net)
        )
        return {
            "tenant_id": tenant_id,
            "ok": ok,
            "available_credits": wallet.available_credits,
            "reserved_credits": wallet.reserved_credits,
            "open_reserved": int(open_reserved),
            "ledger_net": int(ledger_net),
            "observed_total": observed_total,
        }
