# Disaster Recovery

## Backup evidence

`backup.sh` creates:

- PostgreSQL custom-format dump
- SHA-256 checksum
- JSON evidence manifest with UTC creation time, size, and digest

The backup directory and evidence files are owner-only.

## Direct restore containment

The unguarded direct restore path is disabled:

- `restore.sh` exits with status 64 and never invokes `pg_restore`.
- `make restore` exits with status 64 and does not call `restore.sh`.

Do not restore directly through a shell script or Make target. Production recovery requires a
separately reviewed, environment-protected operator workflow with explicit authorization,
source/target cluster-identity validation, a dedicated restore target, backup integrity checks,
rollback instructions, and retained evidence. That production recovery workflow is not verified
by this repository change.

## Restore verification

`restore-verify.sh` is intentionally destructive to its restore target. Use only a dedicated
disposable PostgreSQL cluster/database. It is a validation drill, not a production recovery path.

The current Main script checks the backup checksum, schema head, wallet balances, and reservation
consistency. URL inequality alone does not prove separate PostgreSQL cluster identity. Do not use
the current Main verification script with production credentials or assume it proves a safe target.

The separate hardening candidate in PR #27 adds cluster-identity and target-marker checks. Those
controls are not effective on Main until that PR is independently reviewed, all exact-head checks
pass, and it is merged through the repository's protected release process.

## GitHub DR workflow

The manual Disaster Recovery Drill workflow must be restricted to the protected `production`
environment, require explicit operator confirmation and independent reviewers, use separate
source and disposable restore credentials, and avoid uploading database dumps as workflow
artifacts.

A production completion record requires an operator-approved drill, measured RTO/RPO, verified
restore/failover outcome, and evidence retention. Offline tests and disposable CI drills are not
production DR evidence.
