from datetime import datetime, timezone
from sqlalchemy import select
from fastapi import HTTPException

from .db import session_scope
from .models import ApiKey
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
    "dashboard:read",
    "subscription:read",
    "registry:read",
    "registry:write",
    "marketplace:read",
    "marketplace:write",
}

ROLE_SCOPES = {
    "reader": {
        "billing:read", "runs:read", "audit:read", "dashboard:read",
        "subscription:read", "registry:read", "marketplace:read",
    },
    "operator": {
        "agents:run", "skills:run", "runs:read", "runs:cancel", "dashboard:read",
    },
    "billing": {
        "billing:read", "billing:write", "subscription:read", "dashboard:read",
    },
    "publisher": {
        "registry:read", "registry:write", "marketplace:read", "marketplace:write",
        "dashboard:read",
    },
    "tenant-admin": set(ALLOWED_SCOPES),
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
            "key_type": row.key_type,
            "role": row.role,
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
    scopes: list[str] | None = None,
    expires_at: datetime | None = None,
    *,
    key_type: str = "api_key",
    role: str | None = None,
) -> dict:
    if key_type not in {"api_key", "service_account"}:
        raise HTTPException(400, "Invalid key_type")
    if role is not None:
        if role not in ROLE_SCOPES:
            raise HTTPException(400, f"Unknown role: {role}")
        role_scopes = ROLE_SCOPES[role]
        requested = set(scopes or role_scopes)
        if not requested.issubset(role_scopes):
            raise HTTPException(400, "Requested scopes exceed role policy")
        normalized = sorted(requested)
    else:
        normalized = sorted(set(scopes or []))

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
        key = ApiKey(
            tenant_id=tenant_id,
            name=name,
            key_type=key_type,
            role=role,
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
        action=f"{key_type}.created",
        target_type=key_type,
        target_id=key_id,
        metadata={
            "name": name,
            "role": role,
            "scopes": normalized,
            "expires_at": expires_at.isoformat() if expires_at else None,
        },
    )
    return {
        "id": key_id,
        "name": name,
        "key_type": key_type,
        "role": role,
        "api_key": raw,
        "scopes": normalized,
        "expires_at": expires_at,
        "warning": "This secret is returned once. Store it securely.",
    }

def create_service_account(
    tenant_id: str,
    actor_key_id: str,
    name: str,
    role: str,
    expires_at: datetime | None = None,
) -> dict:
    return create_api_key(
        tenant_id,
        actor_key_id,
        name,
        scopes=None,
        expires_at=expires_at,
        key_type="service_account",
        role=role,
    )

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
        key_type = key.key_type

    record_audit(
        tenant_id=tenant_id,
        actor_type="api_key",
        actor_id=actor_key_id,
        action=f"{key_type}.revoked",
        target_type=key_type,
        target_id=key_id,
        metadata={"name": name},
    )
    return {"id": key_id, "active": False}
