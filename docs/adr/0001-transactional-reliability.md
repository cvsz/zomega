# ADR-0001: Transactional Reliability for Paid Agent Execution

- Status: Accepted
- Date: 2026-09-04
- Decision owners: OMEGA maintainers

## Context

OMEGA performs real-money prepaid billing before asynchronous AI execution. The previous sequence
committed payment events separately from wallet credits and committed run reservations before Redis
enqueue. Those boundaries allowed paid-but-uncredited events and reserved-but-undelivered runs.

Worker retries also needed a deterministic rule for the case where an upstream AI call may have
succeeded immediately before a process crash.

## Decision

OMEGA 2.1 adopts PostgreSQL as the authoritative transaction boundary.

### Payment

A verified provider event is inserted idempotently and the wallet credit + ledger record are written
inside the same database transaction.

### Run creation

Run, wallet reservation, reserve ledger, idempotency record, and RUN_REQUESTED outbox event commit
atomically. Redis is a delivery mechanism, not the source of truth.

### Dispatch

A dispatcher reads pending outbox events and enqueues a deterministic ARQ job ID. Failure to reach
Redis leaves the outbox event pending for retry.

### Execution retries

Each skill creates a durable SkillExecution checkpoint before calling the provider. Completed
checkpoints can be replayed without another provider request. A retry that encounters an unresolved
RUNNING checkpoint marks the run BLOCKED rather than risking duplicate billable execution.

### Financial reconciliation

Wallets, open reservations, and ledger-derived net balances are reconciled periodically. Ambiguous
provider states require explicit operator settlement/refund.

## Consequences

Positive:
- payment fulfillment is atomic
- reservations always have durable queue intent
- Redis outages are recoverable without client resubmission
- automatic retries cannot blindly duplicate an ambiguous provider call
- budget and cancellation semantics are explicit and auditable

Trade-offs:
- blocked ambiguous runs require operator investigation
- PostgreSQL availability is required for billing and run admission
- schema migration and reconciliation become critical operational controls

## Rejected alternatives

- Treating Redis enqueue as part of the billing source of truth: Redis cannot participate in the
  PostgreSQL money transaction.
- Auto-refunding ambiguous provider calls: upstream billable work may already have completed.
- Blind automatic re-execution: risks duplicate cost and duplicate side effects.
