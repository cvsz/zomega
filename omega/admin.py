from sqlalchemy import select

from .db import session_scope
from .models import Tenant, Wallet, ApiKey
from .security import digest_api_key
from .config import settings

DEFAULT_SCOPES = [
    "agents:run",
    "skills:run",
    "billing:read",
    "billing:write",
    "runs:read",
    "runs:cancel",
]

def _validate_raw_api_key(raw_api_key: str) -> None:
    if not raw_api_key.startswith("omega_") or len(raw_api_key) < 40:
        raise ValueError("API key must be an OMEGA key with sufficient entropy")

def create_tenant(name: str, raw_api_key: str, plan: str | None = None) -> str:
    _validate_raw_api_key(raw_api_key)
    with session_scope() as db:
        tenant = Tenant(name=name, plan=plan or settings.omega_default_plan, status="active")
        db.add(tenant)
        db.flush()
        db.add(Wallet(tenant_id=tenant.id, available_credits=0, reserved_credits=0))
        db.add(ApiKey(
            tenant_id=tenant.id,
            name="primary",
            key_digest=digest_api_key(raw_api_key),
            scopes=DEFAULT_SCOPES,
            active=True,
        ))
        return tenant.id

def rotate_api_key(tenant_id: str, raw_api_key: str) -> None:
    _validate_raw_api_key(raw_api_key)
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
            key_digest=digest_api_key(raw_api_key),
            scopes=DEFAULT_SCOPES,
            active=True,
        ))
