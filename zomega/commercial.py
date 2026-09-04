from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session
from fastapi import HTTPException

from .db import session_scope
from .models import (
    Tenant, TenantControl, Subscription, Run, Reservation, UsageEvent, Wallet, WalletLedger, AuditEvent
)
from .audit import record_audit

def _month_start() -> datetime:
    now = datetime.now(timezone.utc)
    return datetime(now.year, now.month, 1, tzinfo=timezone.utc)

def get_control(tenant_id: str) -> dict:
    with session_scope() as db:
        row = db.get(TenantControl, tenant_id)
        if not row:
            row = TenantControl(tenant_id=tenant_id)
            db.add(row)
            db.flush()
        return {
            "tenant_id": tenant_id,
            "monthly_credit_limit": row.monthly_credit_limit,
            "monthly_run_limit": row.monthly_run_limit,
            "allowed_agents": list(row.allowed_agents or []),
            "allowed_skills": list(row.allowed_skills or []),
            "audit_retention_days": row.audit_retention_days,
            "version": row.version,
        }

def set_control(
    tenant_id: str,
    *,
    monthly_credit_limit: int | None,
    monthly_run_limit: int | None,
    allowed_agents: list[str],
    allowed_skills: list[str],
    audit_retention_days: int,
) -> dict:
    if monthly_credit_limit is not None and monthly_credit_limit <= 0:
        raise HTTPException(400, "monthly_credit_limit must be positive")
    if monthly_run_limit is not None and monthly_run_limit <= 0:
        raise HTTPException(400, "monthly_run_limit must be positive")
    if audit_retention_days < 30:
        raise HTTPException(400, "audit_retention_days must be at least 30")
    with session_scope() as db:
        tenant = db.get(Tenant, tenant_id)
        if not tenant:
            raise HTTPException(404, "Tenant not found")
        row = db.get(TenantControl, tenant_id)
        if not row:
            row = TenantControl(tenant_id=tenant_id)
            db.add(row)
        row.monthly_credit_limit = monthly_credit_limit
        row.monthly_run_limit = monthly_run_limit
        row.allowed_agents = sorted(set(allowed_agents))
        row.allowed_skills = sorted(set(allowed_skills))
        row.audit_retention_days = audit_retention_days
        row.version = int(row.version or 0) + 1
    return get_control(tenant_id)

def set_subscription(
    tenant_id: str,
    *,
    plan: str,
    status: str,
    provider: str = "manual",
    provider_subscription_id: str | None = None,
    current_period_start: datetime | None = None,
    current_period_end: datetime | None = None,
) -> dict:
    if status not in {"active", "trialing", "past_due", "paused", "cancelled"}:
        raise HTTPException(400, "Invalid subscription status")
    with session_scope() as db:
        tenant = db.get(Tenant, tenant_id)
        if not tenant:
            raise HTTPException(404, "Tenant not found")
        row = db.execute(
            select(Subscription).where(Subscription.tenant_id == tenant_id)
        ).scalar_one_or_none()
        if not row:
            row = Subscription(tenant_id=tenant_id, plan=plan, status=status, provider=provider)
            db.add(row)
        row.plan = plan
        row.status = status
        row.provider = provider
        row.provider_subscription_id = provider_subscription_id
        row.current_period_start = current_period_start
        row.current_period_end = current_period_end
        tenant.plan = plan
        tenant.status = "active" if status in {"active", "trialing"} else "suspended"
        db.flush()
        subscription_id = row.id
    return {"id": subscription_id, "tenant_id": tenant_id, "plan": plan, "status": status, "provider": provider}

def get_subscription(tenant_id: str) -> dict | None:
    with session_scope() as db:
        row = db.execute(select(Subscription).where(Subscription.tenant_id == tenant_id)).scalar_one_or_none()
        if not row:
            return None
        return {
            "id": row.id,
            "tenant_id": row.tenant_id,
            "provider": row.provider,
            "plan": row.plan,
            "status": row.status,
            "current_period_start": row.current_period_start,
            "current_period_end": row.current_period_end,
        }

def enforce_tenant_admission(
    db: Session,
    *,
    tenant_id: str,
    reservation: int,
    agent_id: str,
    skill_id: str | None,
) -> None:
    month = _month_start()
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:k))"),
        {"k": f"quota:{tenant_id}:{month:%Y-%m}"},
    )
    control = db.get(TenantControl, tenant_id)
    if not control:
        return
    if control.allowed_agents and agent_id not in control.allowed_agents:
        raise HTTPException(403, "Agent not permitted by tenant policy")
    if skill_id and control.allowed_skills and skill_id not in control.allowed_skills:
        raise HTTPException(403, "Skill not permitted by tenant policy")

    if control.monthly_run_limit is not None:
        run_count = db.execute(
            select(func.count(Run.id)).where(
                Run.tenant_id == tenant_id,
                Run.created_at >= month,
            )
        ).scalar_one()
        if int(run_count) >= int(control.monthly_run_limit):
            raise HTTPException(429, detail={"code": "MONTHLY_RUN_LIMIT_EXCEEDED"})

    if control.monthly_credit_limit is not None:
        spent = db.execute(
            select(func.coalesce(func.sum(-WalletLedger.amount), 0)).where(
                WalletLedger.tenant_id == tenant_id,
                WalletLedger.created_at >= month,
                WalletLedger.kind.in_(["charge", "marketplace_charge"]),
            )
        ).scalar_one()
        open_reserved = db.execute(
            select(func.coalesce(func.sum(Reservation.amount), 0)).where(
                Reservation.tenant_id == tenant_id,
                Reservation.status == "reserved",
                Reservation.created_at >= month,
            )
        ).scalar_one()
        projected = int(spent) + int(open_reserved) + reservation
        if projected > int(control.monthly_credit_limit):
            raise HTTPException(
                402,
                detail={
                    "code": "MONTHLY_CREDIT_LIMIT_EXCEEDED",
                    "limit": int(control.monthly_credit_limit),
                    "projected": projected,
                },
            )

def dashboard_summary(tenant_id: str) -> dict:
    month = _month_start()
    with session_scope() as db:
        wallet = db.get(Wallet, tenant_id)
        run_count = db.execute(
            select(func.count(Run.id)).where(Run.tenant_id == tenant_id, Run.created_at >= month)
        ).scalar_one()
        charged = db.execute(
            select(func.coalesce(func.sum(Run.charged_credits), 0)).where(
                Run.tenant_id == tenant_id, Run.created_at >= month
            )
        ).scalar_one()
        audit_count = db.execute(
            select(func.count(AuditEvent.id)).where(AuditEvent.tenant_id == tenant_id, AuditEvent.created_at >= month)
        ).scalar_one()
        input_tokens = db.execute(
            select(func.coalesce(func.sum(UsageEvent.quantity), 0))
            .join(Run, Run.id == UsageEvent.run_id)
            .where(Run.tenant_id == tenant_id, UsageEvent.metric == "input_tokens", Run.created_at >= month)
        ).scalar_one()
        output_tokens = db.execute(
            select(func.coalesce(func.sum(UsageEvent.quantity), 0))
            .join(Run, Run.id == UsageEvent.run_id)
            .where(Run.tenant_id == tenant_id, UsageEvent.metric == "output_tokens", Run.created_at >= month)
        ).scalar_one()
    return {
        "month": month.date().isoformat(),
        "wallet": {
            "available_credits": wallet.available_credits if wallet else 0,
            "reserved_credits": wallet.reserved_credits if wallet else 0,
        },
        "usage": {
            "runs": int(run_count),
            "charged_credits": int(charged),
            "input_tokens": int(input_tokens),
            "output_tokens": int(output_tokens),
            "audit_events": int(audit_count),
        },
        "control": get_control(tenant_id),
        "subscription": get_subscription(tenant_id),
    }

def prune_audit_events() -> int:
    with session_scope() as db:
        controls = db.execute(select(TenantControl)).scalars().all()
        deleted = 0
        now = datetime.now(timezone.utc)
        for control in controls:
            cutoff = now.timestamp() - (int(control.audit_retention_days) * 86400)
            cutoff_dt = datetime.fromtimestamp(cutoff, tz=timezone.utc)
            rows = db.execute(
                select(AuditEvent).where(
                    AuditEvent.tenant_id == control.tenant_id,
                    AuditEvent.created_at < cutoff_dt,
                )
            ).scalars().all()
            for row in rows:
                db.delete(row)
                deleted += 1
        return deleted
