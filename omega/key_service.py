from datetime import datetime, timezone
from sqlalchemy import func, select
from fastapi import HTTPException

from .db import session_scope
from .models import ApiKey, Tenant, TenantQuota
from .security import generate_api_key, hash_api_key_secret, parse_api_key
from .audit import record_audit

ALLOWED_SCOPES = {
    "agents:run",
    "skills:run",
    "billing:read",
    "billing:write",
    "runs:read",
    "runs:cancel",
    "keys:read",
    "keys:write",
    "audit:read",
    "orgs:read",
    "orgs:write",
    "private_skills:read",
    "private_skills:write",
    "marketplace:read",
    "marketplace:write",
    "platform:read",
}

def list_api_keys(tenant_id: str) -> list[dict]:
    with session_scope() as db:
        rows = db.execute(
            select(ApiKey)
            .where(ApiKey.tenant_id == tenant_id)
            .order_by(ApiKey.created_at.desc())
        ).scalars().all()
        return [{
            "id": row.id,
            "name": row.name,
            "prefix": row.key_prefix,
            "scopes": list(row.scopes),
            "active": row.active,
            "expires_at": row.expires_at,
            "created_at": row.created_at,
        } for row in rows]

def create_api_key(
    tenant_id: str,
    actor_key_id: str,
    name: str,
    scopes: list[str],
    expires_at: datetime | None = None,
) -> dict:
    normalized = sorted(set(scopes))
    if not normalized:
        raise HTTPException(400, "At least one scope is required")
    unknown = set(normalized) - ALLOWED_SCOPES
    if unknown:
        raise HTTPException(400, f"Unknown scopes: {sorted(unknown)}")
    if expires_at is not None and expires_at <= datetime.now(timezone.utc):
        raise HTTPException(400, "expires_at must be in the future")

    raw = generate_api_key()
    prefix, secret = parse_api_key(raw)
    with session_scope() as db:
        tenant = db.get(Tenant, tenant_id)
        if not tenant:
            raise HTTPException(404, "Tenant not found")
        quota = db.execute(
            select(TenantQuota).where(TenantQuota.tenant_id == tenant_id).with_for_update()
        ).scalar_one_or_none()
        if quota is None:
            from .platform import ensure_tenant_controls
            quota, _ = ensure_tenant_controls(db, tenant_id, tenant.plan)
            quota = db.execute(
                select(TenantQuota).where(TenantQuota.tenant_id == tenant_id).with_for_update()
            ).scalar_one()
        active_count = db.execute(
            select(func.count(ApiKey.id)).where(
                ApiKey.tenant_id == tenant_id,
                ApiKey.active.is_(True),
            )
        ).scalar_one()
        if int(active_count) >= quota.max_api_keys:
            raise HTTPException(
                429,
                detail={"code": "API_KEY_LIMIT", "limit": quota.max_api_keys, "active": int(active_count)},
            )
        key = ApiKey(
            tenant_id=tenant_id,
            name=name,
            key_prefix=prefix,
            key_digest=hash_api_key_secret(secret),
            scopes=normalized,
            active=True,
            expires_at=expires_at,
        )
        db.add(key)
        db.flush()
        key_id = key.id

    record_audit(
        tenant_id=tenant_id,
        actor_type="api_key",
        actor_id=actor_key_id,
        action="api_key.created",
        target_type="api_key",
        target_id=key_id,
        metadata={"name": name, "scopes": normalized, "expires_at": expires_at.isoformat() if expires_at else None},
    )
    return {
        "id": key_id,
        "name": name,
        "api_key": raw,
        "scopes": normalized,
        "expires_at": expires_at,
        "warning": "This API key is returned once. Store it securely.",
    }

def revoke_api_key(tenant_id: str, actor_key_id: str, key_id: str) -> dict:
    if key_id == actor_key_id:
        raise HTTPException(409, "Refusing to revoke the currently authenticated API key")
    with session_scope() as db:
        key = db.execute(
            select(ApiKey)
            .where(ApiKey.id == key_id, ApiKey.tenant_id == tenant_id)
            .with_for_update()
        ).scalar_one_or_none()
        if not key:
            raise HTTPException(404, "API key not found")
        key.active = False
        name = key.name

    record_audit(
        tenant_id=tenant_id,
        actor_type="api_key",
        actor_id=actor_key_id,
        action="api_key.revoked",
        target_type="api_key",
        target_id=key_id,
        metadata={"name": name},
    )
    return {"id": key_id, "active": False}
