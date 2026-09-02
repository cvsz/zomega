import argparse
import uvicorn
from sqlalchemy import text
from .config import settings
from .db import engine
from .admin import create_tenant

def main():
    p = argparse.ArgumentParser(prog="omega")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("serve")
    c = sub.add_parser("create-tenant")
    c.add_argument("--name", required=True)
    c.add_argument("--plan", default="pro")
    sub.add_parser("db-check")

    args = p.parse_args()
    if args.cmd == "serve":
        uvicorn.run("omega.api:app", host=settings.omega_host, port=settings.omega_port)
    elif args.cmd == "create-tenant":
        tenant_id, api_key = create_tenant(args.name, args.plan)
        print(f"tenant_id={tenant_id}")
        print(f"api_key={api_key}")
        print("Store this API key securely; it will not be shown again.")
    elif args.cmd == "db-check":
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("database=PASS")
