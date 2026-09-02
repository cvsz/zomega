from fastapi import Header, HTTPException
from sqlalchemy import select
from .db import session_scope
from .models import ApiKey, Tenant
from .security import digest_api_key, utcnow

def authenticate(raw_key: str, required_scope: str | None = None) -> dict:
    digest = digest_api_key(raw_key)
    with session_scope() as db:
        row = db.execute(
            select(ApiKey, Tenant)
            .join(Tenant, Tenant.id == ApiKey.tenant_id)
            .where(ApiKey.key_digest == digest, ApiKey.active.is_(True), Tenant.status == "active")
        ).first()
        if not row:
            raise HTTPException(401, "Invalid API key")
        key, tenant = row
        if key.expires_at and key.expires_at <= utcnow():
            raise HTTPException(401, "API key expired")
        if required_scope and required_scope not in key.scopes and "*" not in key.scopes:
            raise HTTPException(403, f"Missing scope: {required_scope}")
        return {"id": tenant.id, "name": tenant.name, "plan": tenant.plan}

async def require_tenant(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Bearer authorization required")
    return authenticate(authorization[7:].strip())
