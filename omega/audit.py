from sqlalchemy import select

from .db import session_scope
from .models import AuditEvent

def record_audit(
    tenant_id: str,
    actor_type: str,
    actor_id: str,
    action: str,
    target_type: str,
    target_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    with session_scope() as db:
        db.add(AuditEvent(
            tenant_id=tenant_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            metadata_json=metadata or {},
        ))

def list_audit_events(tenant_id: str, limit: int = 100) -> list[dict]:
    with session_scope() as db:
        rows = db.execute(
            select(AuditEvent)
            .where(AuditEvent.tenant_id == tenant_id)
            .order_by(AuditEvent.created_at.desc())
            .limit(min(max(limit, 1), 500))
        ).scalars().all()
        return [{
            "id": row.id,
            "actor_type": row.actor_type,
            "actor_id": row.actor_id,
            "action": row.action,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "metadata": row.metadata_json,
            "created_at": row.created_at,
        } for row in rows]
