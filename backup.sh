#!/usr/bin/env bash
set -Eeuo pipefail

: "${DATABASE_URL:?DATABASE_URL required}"
BACKUP_DIR="${BACKUP_DIR:-backups}"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

PG_URL="${DATABASE_URL/postgresql+psycopg:/postgresql:}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DUMP="$BACKUP_DIR/zomega-$STAMP.dump"
CHECKSUM="$DUMP.sha256"
MANIFEST="$DUMP.json"

pg_dump "$PG_URL" --format=custom --no-owner --no-acl --file="$DUMP"
chmod 600 "$DUMP"
sha256sum "$DUMP" > "$CHECKSUM"
chmod 600 "$CHECKSUM"

python3 - "$DUMP" "$CHECKSUM" "$MANIFEST" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone

dump, checksum, manifest = sys.argv[1:]
sha256 = open(checksum, encoding="utf-8").read().split()[0]
payload = {
    "schema": "zomega.backup-evidence.v1",
    "created_at": datetime.now(timezone.utc).isoformat(),
    "dump": os.path.basename(dump),
    "bytes": os.path.getsize(dump),
    "sha256": sha256,
}
with open(manifest, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
    handle.write("\n")
os.chmod(manifest, 0o600)
PY

printf '%s\n' "$MANIFEST"
