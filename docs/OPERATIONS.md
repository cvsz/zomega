# Operations — OMEGA 2.1

## Continuous automated controls

The worker periodically:

- retries pending outbox dispatch
- reaps expired reservations that never started
- reconciles active tenant wallet invariants

CI verifies deterministic migrations, PostgreSQL/Redis integration, duplicate payment handling,
idempotent reservations, catalog secrecy, and the run state machine.

## Daily

- inspect `FAIL`, `BLOCKED`, and `PARTIAL` runs
- investigate `AMBIGUOUS_PROVIDER_STATE` before manual settlement/refund
- review wallet reconciliation alerts
- compare Stripe paid events to OMEGA payment events
- inspect outbox retry counts
- inspect worker/API error rate and latency

## Before release

1. Back up PostgreSQL.
2. Run CI and security gates.
3. Apply migrations in staging.
4. Exercise paid-event idempotency and run reservation.
5. Deploy the immutable image to staging.
6. Verify API/worker health and reconciliation.
7. Approve the protected production environment.
8. Deploy with Helm `--atomic --wait`.

## After release

- verify `/health/ready`
- verify worker outbox dispatch
- inspect billing settlement and reservation age
- confirm no wallet reconciliation failures
- confirm deployed image tag/digest
