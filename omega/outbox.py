from datetime import timedelta
from sqlalchemy import select
from arq import create_pool
from arq.connections import RedisSettings
from .config import settings
from .db import session_scope
from .models import OutboxEvent, Run
from .security import utcnow

def redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(settings.redis_url)

async def dispatch_run(run_id: str) -> bool:
    with session_scope() as db:
        event = db.execute(
            select(OutboxEvent)
            .where(
                OutboxEvent.aggregate_type == "run",
                OutboxEvent.aggregate_id == run_id,
                OutboxEvent.event_type == "RUN_REQUESTED",
                OutboxEvent.status == "pending",
            )
            .with_for_update(skip_locked=True)
        ).scalar_one_or_none()
        if not event:
            return False
        payload = dict(event.payload_json)

    try:
        redis = await create_pool(redis_settings())
        try:
            await redis.enqueue_job("execute_run", run_id, _job_id=run_id)
        finally:
            await redis.close()
    except Exception as exc:
        with session_scope() as db:
            event = db.execute(
                select(OutboxEvent).where(
                    OutboxEvent.aggregate_type == "run",
                    OutboxEvent.aggregate_id == run_id,
                    OutboxEvent.event_type == "RUN_REQUESTED",
                ).with_for_update()
            ).scalar_one()
            event.attempts += 1
            event.last_error = str(exc)[:300]
            event.available_at = utcnow() + timedelta(seconds=min(300, 2 ** min(event.attempts, 8)))
        return False

    with session_scope() as db:
        event = db.execute(
            select(OutboxEvent).where(
                OutboxEvent.aggregate_type == "run",
                OutboxEvent.aggregate_id == run_id,
                OutboxEvent.event_type == "RUN_REQUESTED",
            ).with_for_update()
        ).scalar_one()
        event.status = "dispatched"
        event.dispatched_at = utcnow()
        event.last_error = None
        run = db.get(Run, run_id)
        if run and run.status == "PENDING_DISPATCH":
            run.status = "QUEUED"
    return True

async def dispatch_pending(limit: int = 100) -> int:
    with session_scope() as db:
        ids = db.execute(
            select(OutboxEvent.aggregate_id)
            .where(
                OutboxEvent.status == "pending",
                OutboxEvent.available_at <= utcnow(),
                OutboxEvent.event_type == "RUN_REQUESTED",
            )
            .order_by(OutboxEvent.created_at)
            .limit(limit)
        ).scalars().all()
    count = 0
    for run_id in ids:
        if await dispatch_run(run_id):
            count += 1
    return count
