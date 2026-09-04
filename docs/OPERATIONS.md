# Operations — OMEGA 3.0

## Continuous controls

The worker periodically:

- retries pending outbox dispatch
- reaps stale non-running reservations
- reconciles wallet invariants
- prunes tenant audit events according to configured retention

CI verifies deterministic migrations, 2.2→3.0 upgrade compatibility, PostgreSQL/Redis commercial
integration, API smoke behavior, CodeQL, dependency/SAST/container/IaC security, and SBOM output.

## Daily

- inspect FAIL/BLOCKED/PARTIAL runs
- inspect ambiguous provider states before settlement/refund
- review wallet reconciliation alerts
- compare Stripe paid events to OMEGA payment events
- inspect outbox retries
- review tenant quota denials and marketplace purchases
- review audit-retention and service-account activity

## Before release

1. back up PostgreSQL
2. run CI/security gates
3. apply migrations in staging
4. test paid event idempotency, quota admission, and marketplace settlement
5. deploy immutable attested image to staging
6. verify API/worker health and reconciliation
7. approve protected production environment
8. deploy Helm with `--atomic --wait`

## Disaster recovery

Execute the gated DR drill against a dedicated restore database and retain workflow evidence.
Never point the restore secret at the source database.
