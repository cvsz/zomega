from datetime import datetime
import hashlib

from fastapi import FastAPI, Depends, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from sqlalchemy import select

from .auth import (
    require_billing_read, require_billing_write, require_skills_run,
    require_agents_run, require_runs_read, require_runs_cancel,
    require_keys_read, require_keys_write, require_audit_read,
    require_dashboard_read, require_subscription_read,
    require_registry_read, require_registry_write,
    require_marketplace_read, require_marketplace_write,
    require_admin,
)
from .billing import get_wallet, process_verified_payment, refund_run, reconcile_wallet
from .catalog import public_catalog, public_skill, public_agent, load_agents, load_skills
from .commercial import (
    dashboard_summary, get_control, set_control, get_subscription, set_subscription
)
from .db import session_scope
from .models import WalletLedger, Run, Tenant
from .providers.stripe_provider import (
    create_checkout, construct_event, public_credit_packages, credit_packages,
)
from .rate_limit import enforce
from .run_service import create_skill_run, create_agent_run
from .security import utcnow
from .key_service import list_api_keys, create_api_key, revoke_api_key
from .audit import list_audit_events, export_audit_ndjson, record_audit
from .registry import create_or_update_publisher, publish_skill, list_granted_skills
from .marketplace import create_listing, list_listings, purchase_listing, publisher_earnings

app = FastAPI(title="OMEGA Production API", version="3.0.0")
RUNS = Counter("omega_runs_created_total", "OMEGA runs created", ["kind"])

class RunBody(BaseModel):
    input: dict = Field(default_factory=dict)
    max_spend_credits: int | None = Field(default=None, ge=1)

class CheckoutBody(BaseModel):
    package_id: str

class ApiKeyCreateBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scopes: list[str]
    expires_at: datetime | None = None

class TenantControlBody(BaseModel):
    monthly_credit_limit: int | None = Field(default=None, ge=1)
    monthly_run_limit: int | None = Field(default=None, ge=1)
    allowed_agents: list[str] = Field(default_factory=list)
    allowed_skills: list[str] = Field(default_factory=list)
    audit_retention_days: int = Field(default=365, ge=30)

class SubscriptionBody(BaseModel):
    plan: str = Field(min_length=1, max_length=40)
    status: str
    provider: str = Field(default="manual", min_length=1, max_length=30)
    provider_subscription_id: str | None = Field(default=None, max_length=150)
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None

class PublisherBody(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    ed25519_public_key_pem: str = Field(min_length=32, max_length=4096)

class PrivateSkillPublishBody(BaseModel):
    skill_id: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=80)
    manifest: dict
    signature_b64: str = Field(min_length=1, max_length=512)

class MarketplaceListingBody(BaseModel):
    skill_version_id: str = Field(min_length=36, max_length=36)
    price_credits: int = Field(ge=1)
    publisher_share_bps: int = Field(default=8000, ge=0, le=10000)

@app.get("/health/live")
def live():
    return {"status": "ok"}

@app.get("/health/ready")
def ready():
    try:
        with session_scope() as db:
            db.execute(select(Tenant.id).limit(1))
        from .rate_limit import redis
        redis.ping()
        return {"status": "ready", "database": "ok", "redis": "ok"}
    except Exception as exc:
        raise HTTPException(503, "Dependency unavailable") from exc

@app.get("/metrics")
def metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/v1/catalog")
def catalog():
    return public_catalog()

@app.get("/v1/agents")
def agents():
    return [public_agent(a) for a in load_agents().values()]

@app.get("/v1/skills")
def skills():
    return [public_skill(s) for s in load_skills().values()]

@app.get("/v1/billing/packages")
def billing_packages():
    return public_credit_packages()

@app.get("/v1/billing/balance")
def balance(tenant=Depends(require_billing_read)):
    return get_wallet(tenant["id"])

@app.get("/v1/billing/ledger")
def ledger(tenant=Depends(require_billing_read)):
    with session_scope() as db:
        rows = db.execute(
            select(WalletLedger)
            .where(WalletLedger.tenant_id == tenant["id"])
            .order_by(WalletLedger.created_at.desc())
            .limit(200)
        ).scalars().all()
        return [{
            "id": r.id, "kind": r.kind, "amount": r.amount,
            "reference_type": r.reference_type, "reference_id": r.reference_id,
            "metadata": r.metadata_json, "created_at": r.created_at,
        } for r in rows]

@app.get("/v1/billing/reconciliation")
def billing_reconciliation(tenant=Depends(require_billing_read)):
    return reconcile_wallet(tenant["id"])

@app.post("/v1/checkout")
def checkout(body: CheckoutBody, tenant=Depends(require_billing_write)):
    enforce(tenant["id"])
    return create_checkout(tenant["id"], body.package_id)

@app.post("/v1/payment-webhooks/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    if not signature:
        raise HTTPException(400, "Missing Stripe-Signature")
    try:
        event = construct_event(payload, signature)
    except Exception as exc:
        raise HTTPException(400, "Invalid Stripe webhook") from exc

    event_id = event["id"]
    event_type = event["type"]
    obj = event["data"]["object"]
    payload_hash = hashlib.sha256(payload).hexdigest()

    tenant_id = None
    credits = 0
    status = "ignored"
    if event_type in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
        metadata = obj.get("metadata") or {}
        tenant_id = metadata.get("tenant_id")
        package_id = metadata.get("package_id")
        package = credit_packages().get(package_id)
        signed_credits = (
            int(metadata.get("credits") or 0)
            if str(metadata.get("credits") or "").isdigit()
            else 0
        )
        if (
            obj.get("payment_status") == "paid"
            and tenant_id
            and package
            and signed_credits == package["credits"]
        ):
            credits = package["credits"]
            status = "verified"

    return process_verified_payment(
        provider="stripe",
        provider_event_id=event_id,
        event_type=event_type,
        tenant_id=tenant_id,
        credits=credits,
        payload_hash=payload_hash,
        status=status,
    )

@app.post("/v1/skills/{skill_id}/runs", status_code=202)
async def run_skill(
    skill_id: str,
    body: RunBody,
    tenant=Depends(require_skills_run),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    enforce(tenant["id"])
    RUNS.labels("skill").inc()
    return await create_skill_run(tenant, skill_id, body.input, idempotency_key)

@app.post("/v1/agents/{agent_id}/runs", status_code=202)
async def run_agent(
    agent_id: str,
    body: RunBody,
    tenant=Depends(require_agents_run),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    enforce(tenant["id"])
    RUNS.labels("agent").inc()
    return await create_agent_run(
        tenant, agent_id, body.input, body.max_spend_credits, idempotency_key
    )

@app.get("/v1/runs/{run_id}")
def get_run(run_id: str, tenant=Depends(require_runs_read)):
    with session_scope() as db:
        r = db.execute(
            select(Run).where(Run.id == run_id, Run.tenant_id == tenant["id"])
        ).scalar_one_or_none()
        if not r:
            raise HTTPException(404, "Run not found")
        return {
            "id": r.id, "status": r.status, "agent_id": r.agent_id,
            "skill_id": r.skill_id, "result": r.result_json,
            "charged_credits": r.charged_credits,
            "max_spend_credits": r.max_spend_credits,
            "error_code": r.error_code, "cancel_requested": r.cancel_requested,
            "created_at": r.created_at, "started_at": r.started_at, "finished_at": r.finished_at,
        }

@app.post("/v1/runs/{run_id}/cancel", status_code=202)
def cancel_run(run_id: str, tenant=Depends(require_runs_cancel)):
    immediate_refund = False
    with session_scope() as db:
        r = db.execute(
            select(Run)
            .where(Run.id == run_id, Run.tenant_id == tenant["id"])
            .with_for_update()
        ).scalar_one_or_none()
        if not r:
            raise HTTPException(404, "Run not found")
        if r.status in {"PASS", "FAIL", "PARTIAL", "CANCELLED", "BLOCKED"}:
            return {"run_id": r.id, "status": r.status, "cancel_requested": r.cancel_requested}
        if r.status in {"PENDING_DISPATCH", "QUEUED"}:
            r.status = "CANCELLED"
            r.cancel_requested = True
            r.finished_at = utcnow()
            immediate_refund = True
        else:
            r.cancel_requested = True
            r.status = "CANCEL_REQUESTED"

    if immediate_refund:
        refund_run(run_id, "cancelled_before_execution")
        return {"run_id": run_id, "status": "CANCELLED", "cancel_requested": True}
    return {"run_id": run_id, "status": "CANCEL_REQUESTED", "cancel_requested": True}

@app.get("/v1/api-keys")
def api_keys_list(tenant=Depends(require_keys_read)):
    return list_api_keys(tenant["id"])

@app.post("/v1/api-keys", status_code=201)
def api_keys_create(body: ApiKeyCreateBody, tenant=Depends(require_keys_write)):
    return create_api_key(
        tenant_id=tenant["id"],
        actor_key_id=tenant["api_key_id"],
        name=body.name,
        scopes=body.scopes,
        expires_at=body.expires_at,
    )

@app.delete("/v1/api-keys/{key_id}")
def api_keys_revoke(key_id: str, tenant=Depends(require_keys_write)):
    return revoke_api_key(
        tenant_id=tenant["id"],
        actor_key_id=tenant["api_key_id"],
        key_id=key_id,
    )

@app.get("/v1/audit")
def audit_events(limit: int = 100, tenant=Depends(require_audit_read)):
    return list_audit_events(tenant["id"], limit=limit)

@app.get("/v1/audit/export")
def audit_export(limit: int = 10000, tenant=Depends(require_audit_read)):
    return StreamingResponse(
        export_audit_ndjson(tenant["id"], limit=limit),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": "attachment; filename=omega-audit.ndjson"},
    )

@app.get("/v1/dashboard")
def dashboard(tenant=Depends(require_dashboard_read)):
    return dashboard_summary(tenant["id"])

@app.get("/v1/usage")
def usage(tenant=Depends(require_dashboard_read)):
    return dashboard_summary(tenant["id"])["usage"]

@app.get("/v1/subscription")
def subscription(tenant=Depends(require_subscription_read)):
    return get_subscription(tenant["id"])

@app.post("/v1/publisher")
def publisher_upsert(body: PublisherBody, tenant=Depends(require_registry_write)):
    return create_or_update_publisher(
        tenant["id"], tenant["api_key_id"], body.name, body.ed25519_public_key_pem
    )

@app.post("/v1/private-skills", status_code=201)
def private_skill_publish(
    body: PrivateSkillPublishBody,
    tenant=Depends(require_registry_write),
):
    return publish_skill(
        tenant["id"],
        tenant["api_key_id"],
        skill_id=body.skill_id,
        version=body.version,
        manifest=body.manifest,
        signature_b64=body.signature_b64,
    )

@app.get("/v1/private-skills/grants")
def private_skill_grants(tenant=Depends(require_registry_read)):
    return list_granted_skills(tenant["id"])

@app.get("/v1/marketplace")
def marketplace_list(tenant=Depends(require_marketplace_read)):
    return list_listings()

@app.post("/v1/marketplace/listings", status_code=201)
def marketplace_listing_create(
    body: MarketplaceListingBody,
    tenant=Depends(require_marketplace_write),
):
    return create_listing(
        tenant["id"],
        tenant["api_key_id"],
        body.skill_version_id,
        body.price_credits,
        body.publisher_share_bps,
    )

@app.post("/v1/marketplace/{listing_id}/purchase", status_code=201)
def marketplace_purchase(
    listing_id: str,
    tenant=Depends(require_marketplace_write),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    return purchase_listing(
        tenant["id"], tenant["api_key_id"], listing_id, idempotency_key
    )

@app.get("/v1/marketplace/earnings")
def marketplace_earnings(tenant=Depends(require_marketplace_read)):
    return publisher_earnings(tenant["id"])

@app.get("/v1/admin/tenants")
def admin_tenants(admin=Depends(require_admin)):
    with session_scope() as db:
        rows = db.execute(select(Tenant).order_by(Tenant.created_at.desc()).limit(1000)).scalars().all()
        return [{
            "id": row.id,
            "name": row.name,
            "plan": row.plan,
            "status": row.status,
            "created_at": row.created_at,
        } for row in rows]

@app.get("/v1/admin/tenants/{tenant_id}/control")
def admin_get_control(tenant_id: str, admin=Depends(require_admin)):
    return get_control(tenant_id)

@app.put("/v1/admin/tenants/{tenant_id}/control")
def admin_set_control(
    tenant_id: str,
    body: TenantControlBody,
    admin=Depends(require_admin),
):
    result = set_control(
        tenant_id,
        monthly_credit_limit=body.monthly_credit_limit,
        monthly_run_limit=body.monthly_run_limit,
        allowed_agents=body.allowed_agents,
        allowed_skills=body.allowed_skills,
        audit_retention_days=body.audit_retention_days,
    )
    record_audit(
        tenant_id, admin["actor_type"], admin["actor_id"],
        "tenant.control_updated", "tenant_control", tenant_id,
        {
            "monthly_credit_limit": body.monthly_credit_limit,
            "monthly_run_limit": body.monthly_run_limit,
            "audit_retention_days": body.audit_retention_days,
        },
    )
    return result

@app.put("/v1/admin/tenants/{tenant_id}/subscription")
def admin_set_subscription(
    tenant_id: str,
    body: SubscriptionBody,
    admin=Depends(require_admin),
):
    result = set_subscription(
        tenant_id,
        plan=body.plan,
        status=body.status,
        provider=body.provider,
        provider_subscription_id=body.provider_subscription_id,
        current_period_start=body.current_period_start,
        current_period_end=body.current_period_end,
    )
    record_audit(
        tenant_id, admin["actor_type"], admin["actor_id"],
        "subscription.updated", "subscription", result["id"],
        {"plan": body.plan, "status": body.status, "provider": body.provider},
    )
    return result
