from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from .audit import record_audit
from .db import session_scope
from .models import (
    Reservation,
    Run,
    SubscriptionState,
    Tenant,
    TenantQuota,
    TenantUsageMonthly,
    UsageEvent,
)

PLAN_CATALOG = {
    "starter": {"monthly_credit_cap": 25000, "max_api_keys": 5, "max_concurrent_runs": 3},
    "pro": {"monthly_credit_cap": 100000, "max_api_keys": 20, "max_concurrent_runs": 10},
    "enterprise": {"monthly_credit_cap": 1000000, "max_api_keys": 100, "max_concurrent_runs": 50},
}

TERMINAL = {"PASS", "PARTIAL", "FAIL", "BLOCKED", "CANCELLED"}
ACTIVE = {"PENDING_DISPATCH", "QUEUED", "RUNNING", "CANCEL_REQUESTED"}

def _period_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")

def _month_start() -> datetime:
    now = datetime.now(timezone.utc)
    return datetime(now.year, now.month, 1, tzinfo=timezone.utc)

def ensure_tenant_controls(db: Session, tenant_id: str, plan: str) -> tuple[TenantQuota, SubscriptionState]:
    defaults = PLAN_CATALOG.get(plan, PLAN_CATALOG["pro"])
    quota = db.get(TenantQuota, tenant_id)
    if quota is None:
        quota = TenantQuota(tenant_id=tenant_id, **defaults)
        db.add(quota)
        db.flush()
    subscription = db.get(SubscriptionState, tenant_id)
    if subscription is None:
        subscription = SubscriptionState(
            tenant_id=tenant_id,
            provider="stripe",
            status="active",
            plan=plan,
        )
        db.add(subscription)
        db.flush()
    return quota, subscription

def enforce_run_admission(db: Session, tenant_id: str, requested_reservation: int) -> None:
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")

    quota, subscription = ensure_tenant_controls(db, tenant_id, tenant.plan)
    quota = db.execute(
        select(TenantQuota).where(TenantQuota.tenant_id == tenant_id).with_for_update()
    ).scalar_one()
    subscription = db.execute(
        select(SubscriptionState)
        .where(SubscriptionState.tenant_id == tenant_id)
        .with_for_update()
    ).scalar_one()

    if subscription.status not in {"active", "trialing"}:
        raise HTTPException(403, detail={"code": "SUBSCRIPTION_INACTIVE", "status": subscription.status})

    active_runs = db.execute(
        select(func.count(Run.id)).where(
            Run.tenant_id == tenant_id,
            Run.status.in_(ACTIVE),
        )
    ).scalar_one()
    if int(active_runs) >= quota.max_concurrent_runs:
        raise HTTPException(
            429,
            detail={
                "code": "CONCURRENT_RUN_LIMIT",
                "limit": quota.max_concurrent_runs,
                "active": int(active_runs),
            },
        )

    charged = db.execute(
        select(func.coalesce(func.sum(Run.charged_credits), 0)).where(
            Run.tenant_id == tenant_id,
            Run.finished_at >= _month_start(),
            Run.status.in_(TERMINAL),
        )
    ).scalar_one()
    open_reserved = db.execute(
        select(func.coalesce(func.sum(Reservation.amount), 0)).where(
            Reservation.tenant_id == tenant_id,
            Reservation.status == "reserved",
        )
    ).scalar_one()
    projected = int(charged) + int(open_reserved) + requested_reservation
    if projected > quota.monthly_credit_cap:
        raise HTTPException(
            402,
            detail={
                "code": "MONTHLY_CREDIT_CAP",
                "limit": quota.monthly_credit_cap,
                "projected": projected,
            },
        )

def get_control_plane(tenant_id: str) -> dict:
    with session_scope() as db:
        tenant = db.get(Tenant, tenant_id)
        if not tenant:
            raise HTTPException(404, "Tenant not found")
        quota, subscription = ensure_tenant_controls(db, tenant_id, tenant.plan)
        usage = db.get(TenantUsageMonthly, {"tenant_id": tenant_id, "period": _period_now()})
        return {
            "tenant": {"id": tenant.id, "name": tenant.name, "plan": tenant.plan, "status": tenant.status},
            "subscription": {
                "provider": subscription.provider,
                "status": subscription.status,
                "plan": subscription.plan,
                "current_period_end": subscription.current_period_end,
            },
            "quota": {
                "monthly_credit_cap": quota.monthly_credit_cap,
                "max_api_keys": quota.max_api_keys,
                "max_concurrent_runs": quota.max_concurrent_runs,
            },
            "usage": {
                "period": _period_now(),
                "runs": usage.runs if usage else 0,
                "charged_credits": usage.charged_credits if usage else 0,
                "input_tokens": usage.input_tokens if usage else 0,
                "output_tokens": usage.output_tokens if usage else 0,
            },
        }

def admin_set_plan(
    tenant_id: str,
    plan: str,
    subscription_status: str = "active",
    monthly_credit_cap: int | None = None,
    max_api_keys: int | None = None,
    max_concurrent_runs: int | None = None,
) -> dict:
    if plan not in PLAN_CATALOG:
        raise HTTPException(400, "Unknown plan")
    if subscription_status not in {"active", "trialing", "past_due", "paused", "cancelled"}:
        raise HTTPException(400, "Unknown subscription status")
    defaults = PLAN_CATALOG[plan]

    with session_scope() as db:
        tenant = db.execute(
            select(Tenant).where(Tenant.id == tenant_id).with_for_update()
        ).scalar_one_or_none()
        if not tenant:
            raise HTTPException(404, "Tenant not found")
        quota, subscription = ensure_tenant_controls(db, tenant_id, tenant.plan)
        tenant.plan = plan
        subscription.plan = plan
        subscription.status = subscription_status
        quota.monthly_credit_cap = monthly_credit_cap or defaults["monthly_credit_cap"]
        quota.max_api_keys = max_api_keys or defaults["max_api_keys"]
        quota.max_concurrent_runs = max_concurrent_runs or defaults["max_concurrent_runs"]

    record_audit(
        tenant_id=tenant_id,
        actor_type="admin",
        actor_id="omega-admin",
        action="tenant.plan_updated",
        target_type="tenant",
        target_id=tenant_id,
        metadata={
            "plan": plan,
            "subscription_status": subscription_status,
            "monthly_credit_cap": monthly_credit_cap or defaults["monthly_credit_cap"],
            "max_api_keys": max_api_keys or defaults["max_api_keys"],
            "max_concurrent_runs": max_concurrent_runs or defaults["max_concurrent_runs"],
        },
    )
    return get_control_plane(tenant_id)

def aggregate_usage(limit: int = 500) -> int:
    period = _period_now()
    processed = 0
    with session_scope() as db:
        run_ids = db.execute(
            select(Run.id)
            .where(Run.status.in_(TERMINAL), Run.usage_accounted.is_(False))
            .order_by(Run.finished_at.asc().nulls_last())
            .limit(limit)
        ).scalars().all()

    for run_id in run_ids:
        with session_scope() as db:
            run = db.execute(
                select(Run).where(Run.id == run_id).with_for_update()
            ).scalar_one_or_none()
            if not run or run.usage_accounted:
                continue
            tokens = dict(db.execute(
                select(UsageEvent.metric, func.coalesce(func.sum(UsageEvent.quantity), 0))
                .where(UsageEvent.run_id == run_id)
                .group_by(UsageEvent.metric)
            ).all())
            db.execute(
                pg_insert(TenantUsageMonthly)
                .values(
                    tenant_id=run.tenant_id,
                    period=period,
                    runs=1,
                    charged_credits=int(run.charged_credits),
                    input_tokens=int(tokens.get("input_tokens", 0)),
                    output_tokens=int(tokens.get("output_tokens", 0)),
                )
                .on_conflict_do_update(
                    index_elements=["tenant_id", "period"],
                    set_={
                        "runs": TenantUsageMonthly.runs + 1,
                        "charged_credits": TenantUsageMonthly.charged_credits + int(run.charged_credits),
                        "input_tokens": TenantUsageMonthly.input_tokens + int(tokens.get("input_tokens", 0)),
                        "output_tokens": TenantUsageMonthly.output_tokens + int(tokens.get("output_tokens", 0)),
                        "updated_at": func.now(),
                    },
                )
            )
            run.usage_accounted = True
            processed += 1
    return processed
