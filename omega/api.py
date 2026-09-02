import hashlib
from fastapi import FastAPI, Depends, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from sqlalchemy import select

from .auth import require_tenant, authenticate
from .billing import get_wallet, credit_wallet
from .catalog import load_agents, load_skills
from .config import settings
from .db import session_scope
from .models import WalletLedger, Run, PaymentEvent, Tenant
from .providers.stripe_provider import create_checkout, construct_event
from .rate_limit import enforce
from .run_service import create_skill_run, create_agent_run

app = FastAPI(title="OMEGA Production API", version="2.0.0")
RUNS = Counter("omega_runs_created_total", "OMEGA runs created", ["kind"])

class RunBody(BaseModel):
    input: dict = {}
    max_spend_credits: int | None = Field(default=None, ge=1)

class CheckoutBody(BaseModel):
    credits: int = Field(ge=100, le=1_000_000)

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
    return {"agents": list(load_agents().values()), "skills": list(load_skills().values())}

@app.get("/v1/agents")
def agents():
    return list(load_agents().values())

@app.get("/v1/skills")
def skills():
    return list(load_skills().values())

@app.get("/v1/billing/balance")
def balance(tenant=Depends(require_tenant)):
    return get_wallet(tenant["id"])

@app.get("/v1/billing/ledger")
def ledger(tenant=Depends(require_tenant)):
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

@app.post("/v1/checkout")
def checkout(body: CheckoutBody, tenant=Depends(require_tenant)):
    enforce(tenant["id"])
    return create_checkout(tenant["id"], body.credits)

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

    with session_scope() as db:
        if db.execute(select(PaymentEvent).where(PaymentEvent.provider_event_id == event_id)).scalar_one_or_none():
            return {"received": True, "duplicate": True}

        tenant_id = None
        credits = 0
        status = "ignored"

        if event_type in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
            metadata = obj.get("metadata") or {}
            tenant_id = metadata.get("tenant_id")
            credits = int(metadata.get("credits") or 0)
            if obj.get("payment_status") == "paid" and tenant_id and credits > 0:
                status = "verified"

        db.add(PaymentEvent(
            provider="stripe", provider_event_id=event_id, event_type=event_type,
            tenant_id=tenant_id, credits=credits, payload_hash=payload_hash, status=status,
        ))

    if status == "verified":
        credit_wallet(tenant_id, credits, "stripe_event", event_id, {"event_type": event_type})

    return {"received": True}

@app.post("/v1/skills/{skill_id}/runs", status_code=202)
async def run_skill(
    skill_id: str, body: RunBody, tenant=Depends(require_tenant),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    enforce(tenant["id"])
    RUNS.labels("skill").inc()
    return await create_skill_run(tenant, skill_id, body.input, idempotency_key)

@app.post("/v1/agents/{agent_id}/runs", status_code=202)
async def run_agent(
    agent_id: str, body: RunBody, tenant=Depends(require_tenant),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    enforce(tenant["id"])
    RUNS.labels("agent").inc()
    return await create_agent_run(tenant, agent_id, body.input, body.max_spend_credits, idempotency_key)

@app.get("/v1/runs/{run_id}")
def get_run(run_id: str, tenant=Depends(require_tenant)):
    with session_scope() as db:
        r = db.execute(select(Run).where(Run.id == run_id, Run.tenant_id == tenant["id"])).scalar_one_or_none()
        if not r:
            raise HTTPException(404, "Run not found")
        return {
            "id": r.id, "status": r.status, "agent_id": r.agent_id,
            "skill_id": r.skill_id, "result": r.result_json,
            "charged_credits": r.charged_credits, "error_code": r.error_code,
            "created_at": r.created_at, "started_at": r.started_at, "finished_at": r.finished_at,
        }
