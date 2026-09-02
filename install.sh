#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
command -v python3 >/dev/null || { echo "python3 required"; exit 1; }
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m compileall -q omega
echo "Dependencies installed."
echo "Configure .env, ensure PostgreSQL and Redis are reachable, then run:"
echo "  alembic upgrade head"
echo "  omega db-check"
echo "  omega serve"
echo "  arq omega.jobs.WorkerSettings"
