import hashlib, json
from sqlalchemy import select
from arq import create_pool
from arq.connections import RedisSettings
from fastapi import HTTPException
from .config import settings
from .db import session_scope
from .models import Run, IdempotencyRecord
from .catalog import load_skills, load_agents
from .billing import reserve_run
from .pricing import skill_reservation

def _redis_settings():
    return RedisSettings.from_dsn(settings.redis_url)

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
    return await _create_run(tenant, "skill", skill["agent"], skill_id, payload, reservation, idempotency_key)

async def create_agent_run(tenant: dict, agent_id: str, payload: dict, max_spend: int | None, idempotency_key: str | None):
    reservation = calculate_agent_reservation(agent_id)
    if max_spend is not None:
        reservation = min(reservation, max_spend)
    if reservation <= 0:
        raise HTTPException(400, "Invalid max spend")
    return await _create_run(tenant, "agent", agent_id, None, payload, reservation, idempotency_key)

async def _create_run(tenant, kind, agent_id, skill_id, payload, reservation, idempotency_key):
    req_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    with session_scope() as db:
        if idempotency_key:
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
                return {"run_id": run.id, "status": run.status, "replayed": True}

        run = Run(
            tenant_id=tenant["id"],
            agent_id=agent_id,
            skill_id=skill_id,
            status="PENDING",
            input_json=payload,
            max_spend_credits=reservation,
        )
        db.add(run)
        db.flush()
        if idempotency_key:
            db.add(IdempotencyRecord(
                tenant_id=tenant["id"], key=idempotency_key,
                request_hash=req_hash, run_id=run.id,
            ))
        run_id = run.id

    reserve_run(tenant["id"], run_id, reservation)

    with session_scope() as db:
        run = db.get(Run, run_id)
        run.status = "QUEUED"

    redis = await create_pool(_redis_settings())
    await redis.enqueue_job("execute_run", run_id, _job_id=run_id)
    await redis.close()

    return {"run_id": run_id, "status": "QUEUED", "reserved_credits": reservation}
