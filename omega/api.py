from datetime import datetime
import hashlib
from fastapi import FastAPI, Depends, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from sqlalchemy import select

from .auth import (
    require_billing_read, require_billing_write, require_skills_run,
    require_agents_run, require_runs_read, require_runs_cancel,
    require_keys_read, require_keys_write, require_audit_read,
    require_orgs_read, require_orgs_write,
    require_private_skills_read, require_private_skills_write,
    require_marketplace_read, require_marketplace_write,
    require_platform_read, require_admin,
)
from .billing import get_wallet, process_verified_payment, refund_run, reconcile_wallet
from .catalog import public_catalog, public_skill, public_agent, load_agents, load_skills
from .db import session_scope
from .models import WalletLedger, Run, Tenant
from .providers.stripe_provider import (
    create_checkout, construct_event, public_credit_packages, credit_packages,
)
from .rate_limit import enforce
from .run_service import create_skill_run, create_agent_run
from .security import utcnow
from .key_service import list_api_keys, create_api_key, revoke_api_key
from .audit import list_audit_events
from .platform import get_control_plane, admin_set_plan, PLAN_CATALOG
from .org_service import (
    create_organization, list_organizations, add_member, list_members,
    create_service_account, disable_service_account,
)
from .private_skills import register_private_skill, list_private_skills, set_private_skill_status
from .marketplace import (
    create_listing, set_listing_status, list_marketplace,
    purchase_listing, list_licenses, marketplace_balance,
)

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

class AdminPlanBody(BaseModel):
    plan: str
    subscription_status: str = "active"
    monthly_credit_cap: int | None = Field(default=None, ge=1)
    max_api_keys: int | None = Field(default=None, ge=1)
    max_concurrent_runs: int | None = Field(default=None, ge=1)

class OrganizationCreateBody(BaseModel):
    name: str = Field(min_length=1, max_length=200)

class OrganizationMemberBody(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    role: str

class ServiceAccountCreateBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    role: str
    organization_id: str | None = None

class PrivateSkillCreateBody(BaseModel):
    slug: str
    version: str
    manifest: dict

class StatusBody(BaseModel):
    status: str

class MarketplaceListingBody(BaseModel):
    private_skill_id: str
    price_credits: int = Field(ge=1)
    revenue_share_bps: int = Field(default=8000, ge=0, le=10000)

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
        signed_credits = int(metadata.get("credits") or 0) if str(metadata.get("credits") or "").isdigit() else 0
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


@app.get("/v1/platform")
def platform_status(tenant=Depends(require_platform_read)):
    return get_control_plane(tenant["id"])

@app.get("/v1/plans")
def plans():
    return PLAN_CATALOG

@app.put("/v1/admin/tenants/{tenant_id}/plan")
def admin_plan_update(tenant_id: str, body: AdminPlanBody, _admin=Depends(require_admin)):
    return admin_set_plan(
        tenant_id=tenant_id,
        plan=body.plan,
        subscription_status=body.subscription_status,
        monthly_credit_cap=body.monthly_credit_cap,
        max_api_keys=body.max_api_keys,
        max_concurrent_runs=body.max_concurrent_runs,
    )

@app.get("/v1/organizations")
def organizations_list(tenant=Depends(require_orgs_read)):
    return list_organizations(tenant["id"])

@app.post("/v1/organizations", status_code=201)
def organizations_create(body: OrganizationCreateBody, tenant=Depends(require_orgs_write)):
    return create_organization(tenant["id"], tenant["api_key_id"], body.name)

@app.get("/v1/organizations/{organization_id}/members")
def organization_members_list(organization_id: str, tenant=Depends(require_orgs_read)):
    return list_members(tenant["id"], organization_id)

@app.post("/v1/organizations/{organization_id}/members", status_code=201)
def organization_members_create(
    organization_id: str,
    body: OrganizationMemberBody,
    tenant=Depends(require_orgs_write),
):
    return add_member(
        tenant["id"],
        tenant["api_key_id"],
        organization_id,
        body.subject,
        body.role,
    )

@app.post("/v1/service-accounts", status_code=201)
def service_accounts_create(body: ServiceAccountCreateBody, tenant=Depends(require_orgs_write)):
    return create_service_account(
        tenant_id=tenant["id"],
        actor_key_id=tenant["api_key_id"],
        org_id=body.organization_id,
        name=body.name,
        role=body.role,
    )

@app.delete("/v1/service-accounts/{service_account_id}")
def service_accounts_disable(service_account_id: str, tenant=Depends(require_orgs_write)):
    return disable_service_account(
        tenant["id"],
        tenant["api_key_id"],
        service_account_id,
    )

@app.get("/v1/private-skills")
def private_skills_list(tenant=Depends(require_private_skills_read)):
    return list_private_skills(tenant["id"])

@app.post("/v1/private-skills", status_code=201)
def private_skills_create(body: PrivateSkillCreateBody, tenant=Depends(require_private_skills_write)):
    return register_private_skill(
        tenant_id=tenant["id"],
        actor_key_id=tenant["api_key_id"],
        slug=body.slug,
        version=body.version,
        manifest=body.manifest,
    )

@app.put("/v1/private-skills/{skill_id}/status")
def private_skills_status(
    skill_id: str,
    body: StatusBody,
    tenant=Depends(require_private_skills_write),
):
    return set_private_skill_status(
        tenant["id"],
        tenant["api_key_id"],
        skill_id,
        body.status,
    )

@app.get("/v1/marketplace")
def marketplace_public():
    return list_marketplace()

@app.post("/v1/marketplace/listings", status_code=201)
def marketplace_listing_create(
    body: MarketplaceListingBody,
    tenant=Depends(require_marketplace_write),
):
    return create_listing(
        tenant["id"],
        tenant["api_key_id"],
        body.private_skill_id,
        body.price_credits,
        body.revenue_share_bps,
    )

@app.put("/v1/marketplace/listings/{listing_id}/status")
def marketplace_listing_status(
    listing_id: str,
    body: StatusBody,
    tenant=Depends(require_marketplace_write),
):
    return set_listing_status(
        tenant["id"],
        tenant["api_key_id"],
        listing_id,
        body.status,
    )

@app.post("/v1/marketplace/listings/{listing_id}/purchase", status_code=201)
def marketplace_purchase(listing_id: str, tenant=Depends(require_marketplace_write)):
    return purchase_listing(tenant["id"], tenant["api_key_id"], listing_id)

@app.get("/v1/marketplace/licenses")
def marketplace_licenses(tenant=Depends(require_marketplace_read)):
    return list_licenses(tenant["id"])

@app.get("/v1/marketplace/balance")
def marketplace_publisher_balance(tenant=Depends(require_marketplace_read)):
    return marketplace_balance(tenant["id"])
