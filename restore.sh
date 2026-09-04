#!/usr/bin/env bash
set -Eeuo pipefail
: "${DATABASE_URL:?DATABASE_URL required}"
SRC="${1:?Usage: restore.sh backups/file.dump}"
pg_restore --clean --if-exists --no-owner --dbname="$DATABASE_URL" "$SRC"
alembic upgrade head
python3 -m zomega db-check
