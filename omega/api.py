import hashlib
from fastapi import FastAPI, Depends, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from sqlalchemy import select

from .auth import (
    require_billing_read, require_billing_write, require_skills_run,
    require_agents_run, require_runs_read, require_runs_cancel,
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

app = FastAPI(title="OMEGA Production API", version="2.1.0")
RUNS = Counter("omega_runs_created_total", "OMEGA runs created", ["kind"])

class RunBody(BaseModel):
    input: dict = Field(default_factory=dict)
    max_spend_credits: int | None = Field(default=None, ge=1)

class CheckoutBody(BaseModel):
    package_id: str

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
