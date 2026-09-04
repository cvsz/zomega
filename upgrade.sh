#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
mkdir -p backups
STAMP="$(date +%Y%m%d%H%M%S)"
[ -f .zomega/zomega.db ] && cp .zomega/zomega.db "backups/zomega-${STAMP}.db"
. .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python3 -m compileall -q zomega
echo "Upgrade complete; backup=$STAMP"
