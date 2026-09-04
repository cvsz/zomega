from fastapi import Header, HTTPException
from sqlalchemy import select

from .db import session_scope
from .models import ApiKey, Tenant
from .security import (
    api_key_needs_rehash,
    hash_api_key_secret,
    parse_api_key,
    utcnow,
    verify_api_key_secret,
)

def authenticate(raw_key: str, required_scope: str | None = None) -> dict:
    try:
        locator, secret = parse_api_key(raw_key)
    except ValueError as exc:
        raise HTTPException(401, "Invalid API key") from exc

    with session_scope() as db:
        row = db.execute(
            select(ApiKey, Tenant)
            .join(Tenant, Tenant.id == ApiKey.tenant_id)
            .where(
                ApiKey.key_prefix == locator,
                ApiKey.active.is_(True),
                Tenant.status == "active",
            )
        ).first()
        if not row:
            raise HTTPException(401, "Invalid API key")

        key, tenant = row
        if not verify_api_key_secret(key.key_digest, secret):
            raise HTTPException(401, "Invalid API key")
        if key.expires_at and key.expires_at <= utcnow():
            raise HTTPException(401, "API key expired")
        if required_scope and required_scope not in key.scopes and "*" not in key.scopes:
            raise HTTPException(403, f"Missing scope: {required_scope}")

        if api_key_needs_rehash(key.key_digest):
            key.key_digest = hash_api_key_secret(secret)

        return {
            "id": tenant.id,
            "name": tenant.name,
            "plan": tenant.plan,
            "api_key_id": key.id,
            "scopes": list(key.scopes),
        }

def require_scope(scope: str):
    async def dependency(authorization: str = Header(...)):
        if not authorization.startswith("Bearer "):
            raise HTTPException(401, "Bearer authorization required")
        return authenticate(authorization[7:].strip(), scope)
    return dependency

require_billing_read = require_scope("billing:read")
require_billing_write = require_scope("billing:write")
require_skills_run = require_scope("skills:run")
require_agents_run = require_scope("agents:run")
require_runs_read = require_scope("runs:read")
require_runs_cancel = require_scope("runs:cancel")
require_keys_read = require_scope("keys:read")
require_keys_write = require_scope("keys:write")
require_audit_read = require_scope("audit:read")
