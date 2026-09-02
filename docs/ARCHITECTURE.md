# Production Architecture

OMEGA uses PostgreSQL as the source of truth, Redis for distributed rate limiting and ARQ jobs,
Stripe for prepaid credit purchase, and OpenAI Responses API for AI execution.

## Money path

1. Tenant requests Checkout Session.
2. Stripe hosts payment UI.
3. Stripe signs webhook event.
4. OMEGA verifies signature against raw request body.
5. OMEGA idempotently records the Stripe event.
6. Only successful paid Checkout events credit the wallet ledger.

## Execution path

1. API key is HMAC-digested and resolved to an active tenant.
2. Rate limit and entitlement checks run.
3. A PostgreSQL transaction locks the tenant wallet.
4. Credits are moved from available to reserved.
5. Run status changes to QUEUED.
6. ARQ stores the job in Redis.
7. Worker loads the Agent/Skill definition and executes via OpenAI.
8. Usage evidence is recorded.
9. Actual internal credit charge is settled.
10. Unused reserved credits are returned.
11. Failure returns the full open reservation and records failure evidence.

## Concurrency

Wallet mutations use PostgreSQL `SELECT ... FOR UPDATE`. This prevents concurrent API nodes from
double-spending the same available balance.
