# Production Architecture — OMEGA 3.0

OMEGA uses PostgreSQL as the source of truth, Redis/ARQ for job delivery, Stripe Checkout for
prepaid credit purchase, and OpenAI Responses API for AI execution.

## Identity and authorization

OMEGA API keys have the form:

```text
omega_<public-locator>_<secret>
```

The locator supports indexed lookup. Only an Argon2id hash of secret + server pepper is stored.
Tenant routes enforce scopes, and service accounts may use predefined RBAC role presets whose scope
sets cannot be escalated beyond the selected role.

Platform-level plan/quota mutation uses a separate `X-OMEGA-Admin-Token` validated with
constant-time comparison.

## Money path

1. tenant selects a server-owned Stripe package
2. Stripe Checkout is created from configured Price IDs
3. Stripe sends a signed webhook
4. OMEGA validates signature and package metadata
5. provider event insertion, wallet credit, and financial ledger commit atomically
6. duplicate provider events are idempotent

Marketplace purchases similarly commit buyer debit, publisher revenue-share credit, marketplace
accounting, and private-skill grant in one PostgreSQL transaction.

## Run admission path

```text
tenant/month quota advisory lock
→ entitlement and allowlist checks
→ idempotency lock/lookup
→ wallet FOR UPDATE
→ create Run(PENDING_DISPATCH)
→ available → reserved
→ Reservation + ledger
→ IdempotencyRecord
→ RUN_REQUESTED OutboxEvent
→ COMMIT
```

Monthly limits include settled execution spend, marketplace purchases, open reservations, and the
candidate reservation.

## Durable execution

Each skill execution has a durable checkpoint. Completed checkpoints are replayed without another
provider request. A retry that encounters an unresolved RUNNING checkpoint becomes
`BLOCKED / AMBIGUOUS_PROVIDER_STATE` instead of risking duplicate billable execution.

## Signed private registry

Publishers register Ed25519 public keys. Private-skill manifests are canonicalized JSON and verified
against an Ed25519 signature. Each stored version retains:

- manifest content
- SHA-256 content-integrity digest
- signature
- signer public-key snapshot

Historical versions remain verifiable after publisher key rotation.

## Reconciliation

Workers periodically:

- dispatch pending outbox events
- reap expired reservations
- reconcile wallet/ledger/reservation invariants
- prune audit records according to tenant retention policy

Wallet reconciliation includes Stripe credits, run charges, marketplace buyer charges, and
publisher marketplace earnings.

## Application HA / DR

API and worker deployments use topology spread and PodDisruptionBudgets. Backup tooling creates
checksummed PostgreSQL dump evidence; restore verification checks schema head and financial
invariants against a dedicated restore database.

Database replication, Redis HA, cross-region traffic steering, DNS failover, and external backup
storage remain infrastructure/operator responsibilities.
