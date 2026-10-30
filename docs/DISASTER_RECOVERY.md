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

## Restore verification containment

Restore verification is disabled until the target-identity guard and production Environment
protections are independently verified:

- `restore-verify.sh` exits with status 64 before invoking `pg_restore`.
- `make restore-verify` exits with status 64 without calling the script.
- The manual DR workflow exits before injecting database credentials or connecting to source/target databases.

The previous Main implementation only compared database URL strings. Different URLs can still
identify the same PostgreSQL cluster, so URL inequality is not a safe destructive-restore boundary.
Do not dispatch the DR workflow or run a restore script with production credentials.

PR #27 contains a reviewed target-identity hardening candidate, but it must be reconciled against
current Main, re-run through exact-head CI, and independently reviewed again. Re-enablement also
requires verified production Environment required reviewers, a dedicated disposable target, backup
integrity, rollback instructions, and retained evidence.

## GitHub DR workflow

The current manual Disaster Recovery Drill workflow is intentionally blocked. It must not receive
database secrets or connect to any database until the above controls are proven by API read-back
and a fresh independent review.

A production completion record requires an operator-approved drill, measured RTO/RPO, verified
restore/failover outcome, and evidence retention. Offline tests and disposable CI drills are not
production DR evidence.
