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

def create_tenant(name: str, raw_api_key: str, plan: str | None = None) -> str:
    if not raw_api_key.startswith("omega_") or len(raw_api_key) < 40:
        raise ValueError("API key must be an OMEGA key with sufficient entropy")
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
