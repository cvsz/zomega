# Disaster Recovery

## Backup evidence

`backup.sh` creates:

- PostgreSQL custom-format dump
- An explicitly supplied `DATABASE_URL` always takes precedence over the local `.env` fallback; the backup script never silently switches to a different database URL
- SHA-256 checksum
- JSON evidence manifest with UTC creation time, size, and digest

The backup directory and evidence files are owner-only. The GitHub workflow keeps the dump on its ephemeral runner and removes the local backup during cleanup; it does not upload database dumps as Actions artifacts.

## Restore verification

`restore-verify.sh` is destructive to its restore target because it invokes `pg_restore --clean --if-exists`. Use only a separately provisioned, disposable PostgreSQL cluster and database.

Before the destructive command, the script requires:

- a valid backup and matching SHA-256 checksum
- explicit `ZOMEGA_RESTORE_CONFIRMATION=DRILL`
- source and target cluster identifiers readable through `pg_control_system()`
- source and target cluster identifiers to differ
- `ZOMEGA_RESTORE_TARGET_MARKER` to be a 32-128 character alphanumeric, underscore, or hyphen token
- the target database comment to equal `ZOMEGA_DISPOSABLE_RESTORE_TARGET_SHA256:<lowercase_sha256_hex>` computed from the supplied marker token

An authorized operator must provision only the lowercase SHA-256 digest of the high-entropy marker token in the comment on the dedicated disposable restore database. PostgreSQL comments are readable by any connected user, so never store the raw token in a comment; keep it only in the approved secret store. Do not mark a source or production application database. Missing or unreadable identity/marker information fails closed before `pg_restore`. A different cluster ID and digest marker are defense-in-depth; they do not replace an isolated target, review, and operator approval.

After restore, the script checks Alembic head `0008`, rejects negative wallet balances, and verifies that wallet reserved balances match open reservations.

## GitHub DR workflow

The manual Disaster Recovery Drill workflow:

- can execute only when dispatched against `main`
- uses the protected `production` GitHub Environment; keep required reviewers enabled
- requires the literal confirmation `DRILL`
- requires separate source and restore database URLs and a raw target-marker token supplied only through the protected environment secret (only its digest is stored in the database comment)
- runs offline safety tests before database operations
- creates the dump only on the ephemeral runner
- does not upload the database dump as an Actions artifact
- deletes the local backup in an `always()` cleanup step
- injects database credentials only into the validation, backup, and restore steps that require them; offline tests, package installation, checkout, and cleanup receive no database URLs

Required environment secrets:

- `DR_SOURCE_DATABASE_URL`
- `DR_RESTORE_DATABASE_URL`
- `DR_RESTORE_TARGET_MARKER`

The target marker digest is a public database label, not a secret; the raw token remains in the protected environment secret. A successful offline CI test is not a production DR pass. A real completion record must include the exact workflow URL, target cluster/database identity, restore start/end timestamps, post-restore validation, observed RPO/RTO, backup retention evidence, and operator approval. No restore should be run until the dedicated target and environment protections are verified.

## Rollback

This change adds preconditions only; it does not change schema or application data. If the workflow cannot verify identity or marker, it exits before `pg_restore`. Do not bypass the guard to recover a failed drill. Fix the target configuration or use the previously approved disposable restore target, then rerun the controlled drill.
