# ADR-0002: Commercial Admission, Signed Registry, and Marketplace Settlement

- Status: Accepted
- Date: 2026-09-04

## Decision

zomega uses PostgreSQL as the transaction boundary for commercial admission and marketplace
settlement.

Tenant run/spend limits are checked while holding a tenant-month advisory transaction lock.
Marketplace purchases lock buyer and publisher wallets in deterministic tenant-ID order and commit
financial ledgers plus entitlement in one transaction.

Private skill authenticity uses Ed25519 signatures over canonical JSON. Every stored version retains
the signer public key snapshot so later publisher key rotation does not destroy historical
verification capability.

## Consequences

- concurrent API replicas cannot independently oversubscribe tenant quotas
- marketplace retries are idempotent
- marketplace revenue share becomes spendable tenant credit for publishers
- platform revenue remains explicit accounting
- publisher private keys never enter zomega
- multi-region correctness still depends on the PostgreSQL topology selected by operators
