#!/usr/bin/env bash
set -Eeuo pipefail
: "${DATABASE_URL:?DATABASE_URL required}"
mkdir -p backups
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
pg_dump "$DATABASE_URL" --format=custom --file="backups/omega-${STAMP}.dump"
echo "backups/omega-${STAMP}.dump"
