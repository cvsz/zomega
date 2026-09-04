from sqlalchemy import select

from .db import session_scope
from .models import Tenant, Wallet, ApiKey
from .security import hash_api_key_secret, parse_api_key
from .config import settings

DEFAULT_SCOPES = [
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
]

def _validated_parts(raw_api_key: str) -> tuple[str, str]:
    return parse_api_key(raw_api_key)

def create_tenant(name: str, raw_api_key: str, plan: str | None = None) -> str:
    locator, secret = _validated_parts(raw_api_key)
    with session_scope() as db:
        tenant = Tenant(name=name, plan=plan or settings.zomega_default_plan, status="active")
        db.add(tenant)
        db.flush()
        db.add(Wallet(tenant_id=tenant.id, available_credits=0, reserved_credits=0))
        db.add(ApiKey(
            tenant_id=tenant.id,
            name="primary",
            key_prefix=locator,
            key_digest=hash_api_key_secret(secret),
            scopes=DEFAULT_SCOPES,
            active=True,
        ))
        return tenant.id

def rotate_api_key(tenant_id: str, raw_api_key: str) -> None:
    locator, secret = _validated_parts(raw_api_key)
    with session_scope() as db:
        tenant = db.get(Tenant, tenant_id)
        if not tenant:
            raise ValueError("Tenant not found")
        keys = db.execute(
            select(ApiKey).where(ApiKey.tenant_id == tenant_id)
        ).scalars().all()
        for key in keys:
            key.active = False
        db.add(ApiKey(
            tenant_id=tenant_id,
            name="primary-rotated",
            key_prefix=locator,
            key_digest=hash_api_key_secret(secret),
            scopes=DEFAULT_SCOPES,
            active=True,
        ))
