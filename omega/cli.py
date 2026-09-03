import argparse
import getpass
import json
import uvicorn
from sqlalchemy import text, select

from .config import settings
from .db import engine, session_scope
from .admin import create_tenant
from .billing import reconcile_wallet, refund_run, settle_run
from .models import Run, Reservation
from .security import generate_api_key, utcnow

def _reconcile_run(run_id: str, action: str, charge: int | None):
    with session_scope() as db:
        run = db.execute(select(Run).where(Run.id == run_id)).scalar_one_or_none()
        if not run:
            raise SystemExit(f"run not found: {run_id}")
        reservation = db.execute(
            select(Reservation).where(Reservation.run_id == run_id)
        ).scalar_one_or_none()
        if not reservation or reservation.status != "reserved":
            raise SystemExit("run has no open reservation")
        if run.status != "BLOCKED" or run.error_code != "AMBIGUOUS_PROVIDER_STATE":
            raise SystemExit("manual reconciliation is only allowed for AMBIGUOUS_PROVIDER_STATE")

    if action == "refund":
        refund_run(run_id, "operator_refunded_ambiguous_provider_state")
        with session_scope() as db:
            run = db.get(Run, run_id)
            run.status = "FAIL"
            run.error_code = "OPERATOR_REFUNDED_AMBIGUOUS"
            run.finished_at = utcnow()
        print(json.dumps({"run_id": run_id, "action": "refund", "status": "FAIL"}))
        return

    if charge is None or charge < 0:
        raise SystemExit("--charge is required and must be >= 0 for settle")

    with session_scope() as db:
        reservation = db.execute(
            select(Reservation).where(Reservation.run_id == run_id)
        ).scalar_one()
        if charge > reservation.amount:
            raise SystemExit(f"charge exceeds reserved amount ({reservation.amount})")

    settle_run(run_id, charge)
    with session_scope() as db:
        run = db.get(Run, run_id)
        run.status = "PARTIAL"
        run.error_code = "OPERATOR_SETTLED_AMBIGUOUS"
        run.charged_credits = charge
        run.finished_at = utcnow()
    print(json.dumps({
        "run_id": run_id,
        "action": "settle",
        "charged_credits": charge,
        "status": "PARTIAL",
    }))

def _read_new_api_key() -> str:
    generated = generate_api_key()
    prompt = (
        "Enter a pre-generated OMEGA API key, or press Enter to use a securely generated key "
        "that will be shown once by the terminal prompt: "
    )
    supplied = getpass.getpass(prompt)
    if supplied:
        return supplied
    # getpass writes to the controlling terminal, not stdout/stderr logs.
    getpass.getpass(
        f"Generated API key (copy it now; press Enter after saving it): {generated}"
    )
    return generated

def main():
    p = argparse.ArgumentParser(prog="omega")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("serve")

    c = sub.add_parser("create-tenant")
    c.add_argument("--name", required=True)
    c.add_argument("--plan", default="pro")

    sub.add_parser("db-check")

    rw = sub.add_parser("reconcile-wallet")
    rw.add_argument("--tenant-id", required=True)

    rr = sub.add_parser("reconcile-run")
    rr.add_argument("--run-id", required=True)
    rr.add_argument("--action", choices=["refund", "settle"], required=True)
    rr.add_argument("--charge", type=int)

    args = p.parse_args()

    if args.cmd == "serve":
        uvicorn.run("omega.api:app", host=settings.omega_host, port=settings.omega_port)
    elif args.cmd == "create-tenant":
        raw_api_key = _read_new_api_key()
        tenant_id = create_tenant(args.name, raw_api_key, args.plan)
        print(f"tenant_id={tenant_id}")
        print("tenant_created=PASS")
    elif args.cmd == "db-check":
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("database=PASS")
    elif args.cmd == "reconcile-wallet":
        print(json.dumps(reconcile_wallet(args.tenant_id), sort_keys=True))
    elif args.cmd == "reconcile-run":
        _reconcile_run(args.run_id, args.action, args.charge)
