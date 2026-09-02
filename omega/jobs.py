from sqlalchemy import select
from .db import session_scope
from .models import Run, UsageEvent
from .catalog import load_skills, load_agents
from .providers.openai_provider import execute as openai_execute
from .pricing import skill_charge
from .billing import settle_run, refund_run
from .evidence import record
from .security import utcnow

async def _execute_one(skill: dict, payload: dict):
    result = await openai_execute(skill["prompt"], payload)
    charge = skill_charge(skill, result.input_tokens, result.output_tokens)
    return result, charge

async def execute_run(ctx, run_id: str):
    with session_scope() as db:
        run = db.execute(select(Run).where(Run.id == run_id).with_for_update()).scalar_one()
        if run.status != "QUEUED":
            return
        run.status = "RUNNING"
        run.started_at = utcnow()
        tenant_id = run.tenant_id
        agent_id = run.agent_id
        skill_id = run.skill_id
        payload = run.input_json

    record(run_id, "run.started", {"agent_id": agent_id, "skill_id": skill_id})
    try:
        skills = load_skills()
        outputs = []
        total_charge = 0
        total_in = 0
        total_out = 0

        if skill_id:
            sequence = [skill_id]
        else:
            agent = load_agents()[agent_id]
            sequence = list(agent.get("default_workflow", []))

        for sid in sequence:
            skill = skills[sid]
            result, charge = await _execute_one(skill, payload)
            if total_charge + charge > _max_spend(run_id):
                raise RuntimeError("MAX_SPEND_EXCEEDED")
            total_charge += charge
            total_in += result.input_tokens
            total_out += result.output_tokens
            outputs.append({
                "skill_id": sid,
                "output": result.output,
                "provider_response_id": result.provider_response_id,
                "charged_credits": charge,
            })
            record(run_id, "skill.completed", {
                "skill_id": sid,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "charged_credits": charge,
            })

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
    except Exception as exc:
        refund_run(run_id, str(exc)[:120])
        with session_scope() as db:
            run = db.get(Run, run_id)
            run.status = "FAIL"
            run.error_code = str(exc)[:80]
            run.finished_at = utcnow()
        record(run_id, "run.failed", {"error_code": str(exc)[:80]})
        raise

def _max_spend(run_id: str) -> int:
    with session_scope() as db:
        return int(db.get(Run, run_id).max_spend_credits)

async def startup(ctx):
    return

async def shutdown(ctx):
    return

class WorkerSettings:
    functions = [execute_run]
    on_startup = startup
    on_shutdown = shutdown
