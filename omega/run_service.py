import hashlib
import json
from datetime import timedelta
from fastapi import HTTPException
from sqlalchemy import select, text
from .config import settings
from .db import session_scope
from .models import (
    Run, IdempotencyRecord, Wallet, Reservation, WalletLedger, OutboxEvent
)
from .catalog import load_skills, load_agents
from .pricing import skill_reservation
from .security import utcnow
from .outbox import dispatch_run

def calculate_agent_reservation(agent_id: str) -> int:
    agents = load_agents()
    skills = load_skills()
    agent = agents.get(agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    total = sum(skill_reservation(skills[s]) for s in agent.get("default_workflow", []))
    return min(total, settings.omega_max_run_credits)

async def create_skill_run(tenant: dict, skill_id: str, payload: dict, idempotency_key: str | None):
    skills = load_skills()
    skill = skills.get(skill_id)
    if not skill or not skill.get("enabled", True):
        raise HTTPException(404, "Skill not found")
    if tenant["plan"] not in skill.get("entitlement", {}).get("plans", []):
        raise HTTPException(403, "Skill not included in tenant plan")
    reservation = skill_reservation(skill)
    return await _create_run(
        tenant=tenant,
        agent_id=skill["agent"],
        skill_id=skill_id,
        payload=payload,
        reservation=reservation,
        idempotency_key=idempotency_key,
    )

async def create_agent_run(
    tenant: dict,
    agent_id: str,
    payload: dict,
    max_spend: int | None,
    idempotency_key: str | None,
):
    reservation = calculate_agent_reservation(agent_id)
    if max_spend is not None:
        reservation = min(reservation, max_spend)
    if reservation <= 0:
        raise HTTPException(400, "Invalid max spend")
    return await _create_run(
        tenant=tenant,
        agent_id=agent_id,
        skill_id=None,
        payload=payload,
        reservation=reservation,
        idempotency_key=idempotency_key,
    )

async def _create_run(tenant, agent_id, skill_id, payload, reservation, idempotency_key):
    canonical = json.dumps(
        {
            "agent_id": agent_id,
            "skill_id": skill_id,
            "payload": payload,
            "reservation": reservation,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    req_hash = hashlib.sha256(canonical.encode()).hexdigest()

    with session_scope() as db:
        if idempotency_key:
            # Serialize same tenant+idempotency key across concurrent API nodes.
            db.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
                {"lock_key": f"{tenant['id']}:{idempotency_key}"},
            )
            existing = db.execute(
                select(IdempotencyRecord).where(
                    IdempotencyRecord.tenant_id == tenant["id"],
                    IdempotencyRecord.key == idempotency_key,
                )
            ).scalar_one_or_none()
            if existing:
                if existing.request_hash != req_hash:
                    raise HTTPException(409, "Idempotency key reused with different request")
                run = db.get(Run, existing.run_id)
                return {
                    "run_id": run.id,
                    "status": run.status,
                    "replayed": True,
                    "reserved_credits": run.max_spend_credits,
                }

        wallet = db.execute(
            select(Wallet).where(Wallet.tenant_id == tenant["id"]).with_for_update()
        ).scalar_one_or_none()
        if not wallet:
            raise HTTPException(404, "Wallet not found")
        if wallet.available_credits < reservation:
            raise HTTPException(
                402,
                detail={
                    "code": "INSUFFICIENT_CREDITS",
                    "required": reservation,
                    "available": wallet.available_credits,
                },
            )

        run = Run(
            tenant_id=tenant["id"],
            agent_id=agent_id,
            skill_id=skill_id,
            status="PENDING_DISPATCH",
            input_json=payload,
            max_spend_credits=reservation,
        )
        db.add(run)
        db.flush()

        wallet.available_credits -= reservation
        wallet.reserved_credits += reservation
        wallet.version += 1

        reserve = Reservation(
            tenant_id=tenant["id"],
            run_id=run.id,
            amount=reservation,
            status="reserved",
            expires_at=utcnow() + timedelta(hours=2),
        )
        db.add(reserve)
        db.flush()

        db.add(WalletLedger(
            tenant_id=tenant["id"],
            kind="reserve",
            amount=-reservation,
            reference_type="reservation",
            reference_id=reserve.id,
            metadata_json={"run_id": run.id},
        ))

        if idempotency_key:
            db.add(IdempotencyRecord(
                tenant_id=tenant["id"],
                key=idempotency_key,
                request_hash=req_hash,
                run_id=run.id,
            ))

        db.add(OutboxEvent(
            aggregate_type="run",
            aggregate_id=run.id,
            event_type="RUN_REQUESTED",
            payload_json={"run_id": run.id},
            status="pending",
            available_at=utcnow(),
        ))
        run_id = run.id

    dispatched = await dispatch_run(run_id)
    return {
        "run_id": run_id,
        "status": "QUEUED" if dispatched else "PENDING_DISPATCH",
        "reserved_credits": reservation,
        "replayed": False,
    }
