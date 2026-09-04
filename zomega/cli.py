import argparse
import getpass
import json
import os
from pathlib import Path

import uvicorn
from sqlalchemy import text, select

from .admin import create_tenant, rotate_api_key
from .billing import reconcile_wallet, refund_run, settle_run
from .models import Run, Reservation
from .security import generate_api_key, utcnow

def _reconcile_run(run_id: str, action: str, charge: int | None):
    from .db import session_scope
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

def _read_api_key_twice() -> str:
    first = getpass.getpass("Enter new zomega API key: ")
    second = getpass.getpass("Confirm new zomega API key: ")
    if not first or first != second:
        raise SystemExit("API key confirmation failed")
    return first

def _write_new_api_key(path: str) -> None:
    target = Path(path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(target, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(generate_api_key())
            handle.write("\n")
    except Exception:
        try:
            target.unlink(missing_ok=True)
        finally:
            raise
    print(f"api_key_file={target}")
    print("api_key_generated=PASS")

def main():
    p = argparse.ArgumentParser(prog="zomega")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("serve")

    g = sub.add_parser("generate-api-key")
    g.add_argument("--output", required=True)

    c = sub.add_parser("create-tenant")
    c.add_argument("--name", required=True)
    c.add_argument("--plan", default="pro")

    rk = sub.add_parser("rotate-api-key")
    rk.add_argument("--tenant-id", required=True)

    sub.add_parser("db-check")

    rw = sub.add_parser("reconcile-wallet")
    rw.add_argument("--tenant-id", required=True)

    rr = sub.add_parser("reconcile-run")
    rr.add_argument("--run-id", required=True)
    rr.add_argument("--action", choices=["refund", "settle"], required=True)
    rr.add_argument("--charge", type=int)

    args = p.parse_args()

    if args.cmd == "serve":
        from .config import settings
        uvicorn.run("zomega.api:app", host=settings.zomega_host, port=settings.zomega_port)
    elif args.cmd == "generate-api-key":
        _write_new_api_key(args.output)
    elif args.cmd == "create-tenant":
        raw_api_key = _read_api_key_twice()
        tenant_id = create_tenant(args.name, raw_api_key, args.plan)
        print(f"tenant_id={tenant_id}")
        print("tenant_created=PASS")
    elif args.cmd == "rotate-api-key":
        raw_api_key = _read_api_key_twice()
        rotate_api_key(args.tenant_id, raw_api_key)
        print(f"tenant_id={args.tenant_id}")
        print("api_key_rotated=PASS")
    elif args.cmd == "db-check":
        from .db import engine
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("database=PASS")
    elif args.cmd == "reconcile-wallet":
        print(json.dumps(reconcile_wallet(args.tenant_id), sort_keys=True))
    elif args.cmd == "reconcile-run":
        _reconcile_run(args.run_id, args.action, args.charge)
