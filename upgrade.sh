#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
mkdir -p backups
STAMP="$(date +%Y%m%d%H%M%S)"
[ -f .omega/omega.db ] && cp .omega/omega.db "backups/omega-${STAMP}.db"
. .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python3 -m compileall -q omega
echo "Upgrade complete; backup=$STAMP"
