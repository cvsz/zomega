#!/usr/bin/env bash
set -Eeuo pipefail

: "${ZOMEGA_BACKUP_FILE:?ZOMEGA_BACKUP_FILE required}"
: "${ZOMEGA_SOURCE_DATABASE_URL:?ZOMEGA_SOURCE_DATABASE_URL required; refusing restore without source identity verification}"
: "${ZOMEGA_RESTORE_VERIFY_DATABASE_URL:?ZOMEGA_RESTORE_VERIFY_DATABASE_URL required}"
: "${ZOMEGA_RESTORE_TARGET_MARKER:?ZOMEGA_RESTORE_TARGET_MARKER required; refusing restore without a pre-marked disposable target}"

if [[ ! "${ZOMEGA_RESTORE_TARGET_MARKER}" =~ ^[A-Za-z0-9_-]{32,128}$ ]]; then
  echo "ZOMEGA_RESTORE_TARGET_MARKER must be a 32-128 character token." >&2
  exit 2
fi

if [[ "${ZOMEGA_RESTORE_CONFIRMATION:-}" != "DRILL" ]]; then
  echo "Refusing restore verification without ZOMEGA_RESTORE_CONFIRMATION=DRILL" >&2
  exit 2
fi

test -f "$ZOMEGA_BACKUP_FILE"
test -f "$ZOMEGA_BACKUP_FILE.sha256"
sha256sum --check "$ZOMEGA_BACKUP_FILE.sha256"

SOURCE_URL="${ZOMEGA_SOURCE_DATABASE_URL/postgresql+psycopg:/postgresql:}"
RESTORE_URL="${ZOMEGA_RESTORE_VERIFY_DATABASE_URL/postgresql+psycopg:/postgresql:}"

database_cluster_identity() {
  local url="$1"
  local identity
  if ! identity="$(psql "$url" -X -qAt -v ON_ERROR_STOP=1 -c \
    "SELECT system_identifier::text FROM pg_control_system()")"; then
    echo "Unable to verify PostgreSQL cluster identity; refusing destructive restore." >&2
    return 1
  fi
  if [[ ! "$identity" =~ ^[0-9]+$ ]]; then
    echo "PostgreSQL cluster identity was empty or invalid; refusing destructive restore." >&2
    return 1
  fi
  printf '%s' "$identity"
}

verify_disposable_target_marker() {
  local url="$1"
  local marker
  if ! marker="$(psql "$url" -X -qAt -v ON_ERROR_STOP=1 -c \
    "SELECT COALESCE(shobj_description(oid, 'pg_database'), '') FROM pg_database WHERE datname = current_database()")"; then
    echo "Unable to verify disposable restore target marker; refusing destructive restore." >&2
    return 1
  fi
  if [[ "$marker" != "ZOMEGA_DISPOSABLE_RESTORE_TARGET:${ZOMEGA_RESTORE_TARGET_MARKER}" ]]; then
    echo "Restore target is not marked as the approved disposable database; refusing destructive restore." >&2
    return 1
  fi
}

SOURCE_CLUSTER_ID="$(database_cluster_identity "$SOURCE_URL")"
TARGET_CLUSTER_ID="$(database_cluster_identity "$RESTORE_URL")"
if [[ "$SOURCE_CLUSTER_ID" == "$TARGET_CLUSTER_ID" ]]; then
  echo "Refusing restore into the source PostgreSQL cluster; target must be a separate cluster." >&2
  exit 2
fi

verify_disposable_target_marker "$RESTORE_URL"

pg_restore --dbname="$RESTORE_URL" --clean --if-exists --no-owner --no-acl "$ZOMEGA_BACKUP_FILE"

HEAD="$(psql "$RESTORE_URL" -X -qAt -v ON_ERROR_STOP=1 -c 'SELECT version_num FROM alembic_version LIMIT 1')"
test "$HEAD" = "0008"

NEGATIVE_WALLETS="$(psql "$RESTORE_URL" -X -qAt -v ON_ERROR_STOP=1 -c 'SELECT count(*) FROM wallets WHERE available_credits < 0 OR reserved_credits < 0')"
test "$NEGATIVE_WALLETS" = "0"

RESERVATION_MISMATCH="$(psql "$RESTORE_URL" -X -qAt -v ON_ERROR_STOP=1 -c "
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
