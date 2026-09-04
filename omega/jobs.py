from arq import cron
from sqlalchemy import select
from .db import session_scope
from .models import Run, UsageEvent, SkillExecution, Reservation, Tenant
from .catalog import load_skills, load_agents
from .providers.openai_provider import execute as openai_execute
from .pricing import skill_charge, skill_reservation
from .billing import settle_run, refund_run, reconcile_wallet
from .evidence import record
from .security import utcnow
from .outbox import dispatch_pending
from .platform import aggregate_usage

class AmbiguousProviderState(RuntimeError):
    pass

def _run_snapshot(run_id: str) -> dict:
    with session_scope() as db:
        run = db.get(Run, run_id)
        return {
            "status": run.status,
            "cancel_requested": run.cancel_requested,
            "max_spend": int(run.max_spend_credits),
        }

def _prepare_execution(run_id: str, sid: str, sequence_no: int) -> SkillExecution:
    with session_scope() as db:
        existing = db.execute(
            select(SkillExecution).where(
                SkillExecution.run_id == run_id,
                SkillExecution.sequence_no == sequence_no,
            )
        ).scalar_one_or_none()
        if existing:
            if existing.status == "PASS":
                return existing
            if existing.status == "RUNNING":
                raise AmbiguousProviderState(
                    f"skill {sid} has ambiguous provider state; refusing automatic re-execution"
                )
            return existing
        execution = SkillExecution(
            run_id=run_id,
            skill_id=sid,
            sequence_no=sequence_no,
            status="RUNNING",
            started_at=utcnow(),
        )
        db.add(execution)
        db.flush()
        return execution

async def _execute_one(run_id: str, sid: str, sequence_no: int, skill: dict, payload: dict):
    checkpoint = _prepare_execution(run_id, sid, sequence_no)
    if checkpoint.status == "PASS":
        return {
            "skill_id": sid,
            "output": (checkpoint.output_json or {}).get("output"),
            "provider_response_id": checkpoint.provider_response_id,
            "charged_credits": checkpoint.charged_credits,
            "input_tokens": checkpoint.input_tokens,
            "output_tokens": checkpoint.output_tokens,
            "replayed_checkpoint": True,
        }

    result = await openai_execute(skill["prompt"], payload)
    charge = skill_charge(skill, result.input_tokens, result.output_tokens)

    with session_scope() as db:
        execution = db.execute(
            select(SkillExecution).where(
                SkillExecution.run_id == run_id,
                SkillExecution.sequence_no == sequence_no,
            ).with_for_update()
        ).scalar_one()
        execution.status = "PASS"
        execution.provider_response_id = result.provider_response_id
        execution.input_tokens = result.input_tokens
        execution.output_tokens = result.output_tokens
        execution.charged_credits = charge
        execution.output_json = {"output": result.output}
        execution.finished_at = utcnow()

    return {
        "skill_id": sid,
        "output": result.output,
        "provider_response_id": result.provider_response_id,
        "charged_credits": charge,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "replayed_checkpoint": False,
    }

def _finalize_cancelled(run_id: str, total_charge: int, outputs: list[dict]):
    settle_run(run_id, total_charge)
    with session_scope() as db:
        run = db.get(Run, run_id)
        run.status = "CANCELLED"
        run.cancel_requested = True
        run.charged_credits = total_charge
        run.result_json = {"steps": outputs, "reason": "cancel_requested"}
        run.finished_at = utcnow()
    record(run_id, "run.cancelled", {"charged_credits": total_charge})

async def execute_run(ctx, run_id: str):
    with session_scope() as db:
        run = db.execute(
            select(Run).where(Run.id == run_id).with_for_update()
        ).scalar_one()
        if run.status not in {"QUEUED", "RUNNING"}:
            return
        if run.status == "RUNNING":
            active = db.execute(
                select(SkillExecution).where(
                    SkillExecution.run_id == run_id,
                    SkillExecution.status == "RUNNING",
                )
            ).scalar_one_or_none()
            if active:
                run.status = "BLOCKED"
                run.error_code = "AMBIGUOUS_PROVIDER_STATE"
                record(run_id, "run.blocked", {"reason": run.error_code})
                return
        run.status = "RUNNING"
        if run.started_at is None:
            run.started_at = utcnow()
        agent_id = run.agent_id
        skill_id = run.skill_id
        payload = run.input_json
        max_spend = int(run.max_spend_credits)

    record(run_id, "run.started", {"agent_id": agent_id, "skill_id": skill_id})

    try:
        skills = load_skills()
        outputs = []
        total_charge = 0
        total_in = 0
        total_out = 0

        sequence = [skill_id] if skill_id else list(load_agents()[agent_id].get("default_workflow", []))

        for sequence_no, sid in enumerate(sequence, start=1):
            if _run_snapshot(run_id)["cancel_requested"]:
                _finalize_cancelled(run_id, total_charge, outputs)
                return

            skill = skills[sid]
            remaining = max_spend - total_charge
            required = skill_reservation(skill)
            if required > remaining:
                settle_run(run_id, total_charge)
                with session_scope() as db:
                    run = db.get(Run, run_id)
                    run.status = "PARTIAL"
                    run.error_code = "BUDGET_EXHAUSTED"
                    run.charged_credits = total_charge
                    run.result_json = {"steps": outputs, "reason": "budget_exhausted"}
                    run.finished_at = utcnow()
                record(run_id, "run.partial", {
                    "reason": "budget_exhausted",
                    "charged_credits": total_charge,
                    "next_skill": sid,
                })
                return

            step = await _execute_one(run_id, sid, sequence_no, skill, payload)
            charge = int(step["charged_credits"])
            if charge > remaining:
                raise RuntimeError("SKILL_CHARGE_EXCEEDED_RESERVED_BUDGET")
            total_charge += charge
            total_in += int(step["input_tokens"])
            total_out += int(step["output_tokens"])
            outputs.append({
                "skill_id": sid,
                "output": step["output"],
                "provider_response_id": step["provider_response_id"],
                "charged_credits": charge,
            })
            record(run_id, "skill.completed", {
                "skill_id": sid,
                "input_tokens": step["input_tokens"],
                "output_tokens": step["output_tokens"],
                "charged_credits": charge,
                "replayed_checkpoint": step["replayed_checkpoint"],
            })

        if _run_snapshot(run_id)["cancel_requested"]:
            _finalize_cancelled(run_id, total_charge, outputs)
            return

        settle_run(run_id, total_charge)
        with session_scope() as db:
            run = db.get(Run, run_id)
            run.status = "PASS"
            run.result_json = {"steps": outputs}
            run.charged_credits = total_charge
            run.finished_at = utcnow()
            db.add(UsageEvent(run_id=run_id, metric="input_tokens", quantity=total_in, metadata_json={}))
            db.add(UsageEvent(run_id=run_id, metric="output_tokens", quantity=total_out, metadata_json={}))
        record(run_id, "run.completed", {"charged_credits": total_charge})

    except AmbiguousProviderState as exc:
        with session_scope() as db:
            run = db.get(Run, run_id)
            run.status = "BLOCKED"
            run.error_code = "AMBIGUOUS_PROVIDER_STATE"
        record(run_id, "run.blocked", {"reason": str(exc)[:300]})
        return
    except Exception as exc:
        refund_run(run_id, str(exc)[:120])
        with session_scope() as db:
            run = db.get(Run, run_id)
            run.status = "FAIL"
            run.error_code = str(exc)[:80]
            run.finished_at = utcnow()
        record(run_id, "run.failed", {"error_code": str(exc)[:80]})
        raise

async def outbox_dispatcher(ctx):
    await dispatch_pending(limit=100)

async def reservation_reaper(ctx):
    now = utcnow()
    with session_scope() as db:
        run_ids = db.execute(
            select(Reservation.run_id)
            .join(Run, Run.id == Reservation.run_id)
            .where(
                Reservation.status == "reserved",
                Reservation.expires_at < now,
                Run.status.in_(["PENDING_DISPATCH", "QUEUED", "FAIL", "CANCELLED"]),
            )
            .limit(200)
        ).scalars().all()
    for run_id in run_ids:
        refund_run(run_id, "reservation_expired")
        with session_scope() as db:
            run = db.get(Run, run_id)
            if run and run.status in {"PENDING_DISPATCH", "QUEUED"}:
                run.status = "FAIL"
                run.error_code = "RESERVATION_EXPIRED"
                run.finished_at = utcnow()
        record(run_id, "reservation.reaped", {})

async def usage_aggregator(ctx):
    aggregate_usage(limit=500)

async def wallet_reconciler(ctx):
    with session_scope() as db:
        tenant_ids = db.execute(
            select(Tenant.id).where(Tenant.status == "active").limit(1000)
        ).scalars().all()
    for tenant_id in tenant_ids:
        result = reconcile_wallet(tenant_id)
        if not result["ok"]:
            print({"event": "wallet.reconciliation_failed", "tenant_id": tenant_id, "result": result})

async def startup(ctx):
    return

async def shutdown(ctx):
    return

class WorkerSettings:
    functions = [execute_run, outbox_dispatcher, reservation_reaper, usage_aggregator, wallet_reconciler]
    cron_jobs = [
        cron(outbox_dispatcher, second={0, 15, 30, 45}),
        cron(reservation_reaper, minute={0, 10, 20, 30, 40, 50}),
        cron(usage_aggregator, minute={2, 12, 22, 32, 42, 52}),
        cron(wallet_reconciler, hour={0, 6, 12, 18}, minute=5),
    ]
    on_startup = startup
    on_shutdown = shutdown
