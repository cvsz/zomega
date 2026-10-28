# Disaster Recovery

## Backup evidence

`backup.sh` creates:

- PostgreSQL custom-format dump
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
- the target database comment to equal `ZOMEGA_DISPOSABLE_RESTORE_TARGET:<token>`, with the exact supplied token

An authorized operator must provision the comment only on the dedicated disposable restore database, using a high-entropy random token also stored in the approved secret store. Do not mark a source or production application database. Missing or unreadable identity/marker information fails closed before `pg_restore`. A different cluster ID and target marker are defense-in-depth; they do not replace an isolated target, review, and operator approval.

After restore, the script checks Alembic head `0008`, rejects negative wallet balances, and verifies that wallet reserved balances match open reservations.

## GitHub DR workflow

The manual Disaster Recovery Drill workflow:

- can execute only when dispatched against `main`
- uses the protected `production` GitHub Environment; keep required reviewers enabled
- requires the literal confirmation `DRILL`
- requires separate source and restore database URLs and a target-marker secret
- runs offline safety tests before database operations
- creates the dump only on the ephemeral runner
- does not upload the database dump as an Actions artifact
- deletes the local backup in an `always()` cleanup step
- injects database credentials only into the validation, backup, and restore steps that require them; offline tests, package installation, checkout, and cleanup receive no database URLs

Required environment secrets:

- `DR_SOURCE_DATABASE_URL`
- `DR_RESTORE_DATABASE_URL`
- `DR_RESTORE_TARGET_MARKER`

A successful offline CI test is not a production DR pass. A real completion record must include the exact workflow URL, target cluster/database identity, restore start/end timestamps, post-restore validation, observed RPO/RTO, backup retention evidence, and operator approval. No restore should be run until the dedicated target and environment protections are verified.

## Rollback

This change adds preconditions only; it does not change schema or application data. If the workflow cannot verify identity or marker, it exits before `pg_restore`. Do not bypass the guard to recover a failed drill. Fix the target configuration or use the previously approved disposable restore target, then rerun the controlled drill.
