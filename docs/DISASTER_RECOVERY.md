# Disaster Recovery

## Backup evidence

`backup.sh` creates:

- PostgreSQL custom-format dump
- SHA-256 checksum
- JSON evidence manifest with UTC creation time, size, and digest

The backup directory and evidence files are owner-only.

## Restore verification

`restore-verify.sh` is intentionally destructive to its restore target. Use only a dedicated
disposable restore database.

Verification checks:

- backup checksum
- Alembic schema head `0008`
- no negative wallet balances
- open reservation totals match wallet reserved balances

When `OMEGA_SOURCE_DATABASE_URL` is supplied, the script refuses an identical restore URL.

## GitHub DR workflow

The manual Disaster Recovery Drill workflow:

- requires the literal confirmation `DRILL`
- uses the protected `production` GitHub Environment
- requires separate source and restore DB secrets
- creates the dump only on the ephemeral runner
- does not upload the database dump as an Actions artifact
- deletes the local backup in an `always()` cleanup step

Required secrets:

- `DR_SOURCE_DATABASE_URL`
- `DR_RESTORE_DATABASE_URL`

A real production completion record requires executing this workflow against production backup
credentials and retaining the workflow evidence.
