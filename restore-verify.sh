#!/usr/bin/env bash
set -Eeuo pipefail

: "${ZOMEGA_BACKUP_FILE:?ZOMEGA_BACKUP_FILE required}"
: "${ZOMEGA_RESTORE_VERIFY_DATABASE_URL:?ZOMEGA_RESTORE_VERIFY_DATABASE_URL required}"

test -f "$ZOMEGA_BACKUP_FILE"
test -f "$ZOMEGA_BACKUP_FILE.sha256"
sha256sum --check "$ZOMEGA_BACKUP_FILE.sha256"

RESTORE_URL="${ZOMEGA_RESTORE_VERIFY_DATABASE_URL/postgresql+psycopg:/postgresql:}"
if [[ -n "${ZOMEGA_SOURCE_DATABASE_URL:-}" ]]; then
  SOURCE_URL="${ZOMEGA_SOURCE_DATABASE_URL/postgresql+psycopg:/postgresql:}"
  if [[ "$SOURCE_URL" == "$RESTORE_URL" ]]; then
    echo "Refusing to restore into source database" >&2
    exit 2
  fi
fi

pg_restore   --dbname="$RESTORE_URL"   --clean   --if-exists   --no-owner   --no-acl   "$ZOMEGA_BACKUP_FILE"

HEAD="$(psql "$RESTORE_URL" -Atc 'SELECT version_num FROM alembic_version LIMIT 1')"
test "$HEAD" = "0008"

NEGATIVE_WALLETS="$(psql "$RESTORE_URL" -Atc 'SELECT count(*) FROM wallets WHERE available_credits < 0 OR reserved_credits < 0')"
test "$NEGATIVE_WALLETS" = "0"

RESERVATION_MISMATCH="$(psql "$RESTORE_URL" -Atc "
SELECT count(*)
FROM wallets w
LEFT JOIN (
  SELECT tenant_id, COALESCE(SUM(amount), 0) AS open_reserved
  FROM reservations
  WHERE status = 'reserved'
  GROUP BY tenant_id
) r ON r.tenant_id = w.tenant_id
WHERE w.reserved_credits <> COALESCE(r.open_reserved, 0)
")"
test "$RESERVATION_MISMATCH" = "0"

printf '%s\n' '{"schema":"zomega.restore-verification.v1","status":"PASS","alembic_head":"0008"}'
