from datetime import timedelta
from sqlalchemy import select
from fastapi import HTTPException
from .db import session_scope
from .models import Wallet, WalletLedger, Reservation, Run
from .security import utcnow

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

def credit_wallet(tenant_id: str, credits: int, reference_type: str, reference_id: str, metadata: dict | None = None):
    if credits <= 0:
        raise ValueError("Credit amount must be positive")
    with session_scope() as db:
        wallet = db.execute(
            select(Wallet).where(Wallet.tenant_id == tenant_id).with_for_update()
        ).scalar_one()
        wallet.available_credits += credits
        wallet.version += 1
        db.add(WalletLedger(
            tenant_id=tenant_id, kind="credit", amount=credits,
            reference_type=reference_type, reference_id=reference_id,
            metadata_json=metadata or {},
        ))

def reserve_run(tenant_id: str, run_id: str, amount: int) -> str:
    if amount <= 0:
        raise ValueError("Reservation amount must be positive")
    with session_scope() as db:
        wallet = db.execute(
            select(Wallet).where(Wallet.tenant_id == tenant_id).with_for_update()
        ).scalar_one()
        if wallet.available_credits < amount:
            raise HTTPException(
                402,
                detail={"code": "INSUFFICIENT_CREDITS", "required": amount, "available": wallet.available_credits},
            )
        wallet.available_credits -= amount
        wallet.reserved_credits += amount
        wallet.version += 1
        r = Reservation(
            tenant_id=tenant_id, run_id=run_id, amount=amount,
            status="reserved", expires_at=utcnow() + timedelta(hours=2),
        )
        db.add(r)
        db.flush()
        db.add(WalletLedger(
            tenant_id=tenant_id, kind="reserve", amount=-amount,
            reference_type="reservation", reference_id=r.id,
            metadata_json={"run_id": run_id},
        ))
        return r.id

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

        db.add(WalletLedger(
            tenant_id=reservation.tenant_id, kind="charge", amount=-actual_charge,
            reference_type="run", reference_id=run_id,
            metadata_json={},
        ))
        if refund:
            db.add(WalletLedger(
                tenant_id=reservation.tenant_id, kind="refund", amount=refund,
                reference_type="reservation", reference_id=reservation.id,
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
            tenant_id=reservation.tenant_id, kind="refund", amount=reservation.amount,
            reference_type="reservation", reference_id=reservation.id,
            metadata_json={"reason": reason},
        ))
