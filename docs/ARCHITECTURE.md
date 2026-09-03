# Production Architecture — OMEGA 2.1

OMEGA uses PostgreSQL as the source of truth, Redis/ARQ for durable job delivery, Stripe Checkout
for prepaid credit purchase, and OpenAI Responses API for AI execution.

## Money path

1. Authenticated tenant selects a server-owned Stripe package.
2. OMEGA creates a Stripe Checkout Session using the configured Price ID.
3. Stripe sends a signed webhook over the raw request body.
4. OMEGA validates the signature and package metadata.
5. PostgreSQL inserts the provider event using conflict-safe idempotency.
6. In the same transaction, the tenant wallet is locked, credited, versioned, and a ledger entry is written.
7. Duplicate provider events return safely without a second credit.

There is no state where a committed payment event can exist without its corresponding wallet credit
for a verified payment.

## Run creation path

A single PostgreSQL transaction performs:

```text
advisory lock for tenant + idempotency key
→ idempotency lookup
→ SELECT wallet FOR UPDATE
→ create Run(PENDING_DISPATCH)
→ move available → reserved credits
→ create Reservation
→ write reserve ledger
→ write IdempotencyRecord
→ write RUN_REQUESTED OutboxEvent
→ COMMIT
```

After commit, the dispatcher enqueues the deterministic Redis job ID. If Redis is unavailable, the
outbox remains pending and is retried by the worker cron dispatcher. No reservation is orphaned
without a durable queue intent.

## Worker path

Each skill has a durable `SkillExecution` checkpoint.

- A completed checkpoint is replayed without another provider call.
- A checkpoint still marked `RUNNING` on retry is treated as ambiguous.
- OMEGA blocks the run instead of risking a duplicate OpenAI call.
- Operators explicitly reconcile that blocked reservation after examining provider evidence.

Before every skill, the worker checks cancellation and remaining budget. It never launches a skill
whose reservation would exceed the caller's maximum spend.

## Billing settlement

Success:

```text
reserved → actual charge + unused refund
```

Failure before ambiguous provider state:

```text
open reservation → full refund
```

Cancellation:

- before execution: full refund
- between completed skills: charge completed work and refund the remainder

## Reconciliation

Periodic worker jobs:

- dispatch pending outbox events
- reap expired non-running reservations
- compare wallet totals, open reservations, and ledger-derived net balances

Database checks prevent negative wallet balances and invalid ledger/reservation amounts.

## Security boundaries

- API keys are stored as HMAC digests.
- Every private route enforces a specific API-key scope.
- Catalog responses use sanitized DTOs and do not expose internal prompts.
- Kubernetes workloads run non-root, drop Linux capabilities, disable privilege escalation, use
  read-only root filesystems, disable service-account token automounting, and use RuntimeDefault seccomp.
- NetworkPolicy defaults to deny and explicitly permits runtime DNS and required outbound ports.
