# OMEGA Production 2.1

OMEGA is a paid-before-use, multi-tenant Agents + Skills API with 12 specialized Agents and 100 billable Skills.

OMEGA 2.1 hardens the real-money and durable-execution path with atomic Stripe fulfillment,
PostgreSQL wallet locks, a transactional outbox, retry-safe skill checkpoints, budget-aware agent
execution, route-level API-key scopes, cancellation, reservation reaping, wallet reconciliation,
and production CI/CD gates.

## Paid-before-use invariant

```text
API key
→ tenant + scope + entitlement
→ rate limit
→ transactional run + wallet reservation + ledger + outbox
→ Redis dispatch
→ worker checkpoint
→ OpenAI Responses API
→ meter
→ settle / refund
→ evidence
```

No billable run is dispatched unless its credit reservation committed successfully.

## Required services

- PostgreSQL
- Redis
- Stripe account with three server-owned Price IDs
- OpenAI API key
- HTTPS public URL

## Boot

```bash
cp .env.example .env
# configure all required values
docker compose up --build -d
docker compose exec api alembic upgrade head
docker compose exec api omega create-tenant --name "First Tenant" --plan pro
```

`create-tenant` prompts twice for a pre-generated `omega_<locator>_<secret>` API key using hidden terminal input. The CLI never prints the secret. Generate a key into a mode-0600 file with `omega generate-api-key --output ./tenant.key`, move it into your password/secret manager, then enter it through the hidden prompt.

## API-key rotation after the CodeQL hardening update

OMEGA now stores API-key secrets with Argon2id. API keys use the form `omega_<24-hex-public-locator>_<secret>`: the locator is indexed for O(1) lookup and only an Argon2id hash of `secret + server pepper` is stored. Migration `0004` deactivates every older deterministic API-key digest because raw secrets are intentionally never stored and therefore cannot be converted safely.

Rotate a tenant key explicitly:

```bash
omega rotate-api-key --tenant-id <tenant-id>
```

The command accepts and confirms the new key through hidden terminal input and does not emit the secret to stdout/stderr.

## Credit packages

Configure these Stripe Price IDs:

```text
STRIPE_PRICE_CREDITS_1000
STRIPE_PRICE_CREDITS_5000
STRIPE_PRICE_CREDITS_20000
```

Discover public packages:

```http
GET /v1/billing/packages
```

Create Checkout:

```http
POST /v1/checkout
Authorization: Bearer omega_...
Content-Type: application/json

{"package_id":"credits_1000"}
```

Credits are granted only from a Stripe-signed paid Checkout webhook. The payment event and wallet
credit commit in the same PostgreSQL transaction, and duplicate Stripe events are idempotent.

Webhook endpoint:

```text
POST /v1/payment-webhooks/stripe
```

## Run a Skill

```http
POST /v1/skills/repository-intelligence/runs
Authorization: Bearer omega_...
Idempotency-Key: customer-operation-123
Content-Type: application/json

{"input":{"repository":"owner/project"}}
```

A successful request returns HTTP 202 with `QUEUED` or `PENDING_DISPATCH`. `PENDING_DISPATCH`
means the reservation is safe in PostgreSQL and the outbox dispatcher will retry Redis delivery.

## Run an Agent

```http
POST /v1/agents/omega-security/runs
Authorization: Bearer omega_...
Idempotency-Key: security-run-123
Content-Type: application/json

{"input":{"objective":"Audit the supplied repository"},"max_spend_credits":500}
```

The worker checks remaining budget before launching each skill. Reaching the caller's spend cap
finishes as `PARTIAL / BUDGET_EXHAUSTED` rather than charging beyond the limit.

## Cancel a Run

```http
POST /v1/runs/{run_id}/cancel
Authorization: Bearer omega_...
```

Queued runs are cancelled and refunded immediately. Running jobs stop between skills and settle
only completed billable work.

## API-key scopes

Primary tenant keys receive:

- `agents:run`
- `skills:run`
- `billing:read`
- `billing:write`
- `runs:read`
- `runs:cancel`

Internal skill prompts, validation rules, and permissions are never exposed by public catalog
endpoints.

## Reconciliation

```bash
omega reconcile-wallet --tenant-id <tenant-id>
omega reconcile-run --run-id <run-id> --action refund
omega reconcile-run --run-id <run-id> --action settle --charge <credits>
```

Manual run reconciliation is restricted to `BLOCKED / AMBIGUOUS_PROVIDER_STATE`. OMEGA refuses
automatic re-execution when a provider call may already have occurred.

## Production validation

```bash
./verify.sh
```

CI additionally performs PostgreSQL/Redis migration and billing integration tests. Security gates
include dependency audit, Python SAST, Trivy filesystem/container/IaC scanning, and SBOM generation.

See `docs/ARCHITECTURE.md`, `docs/BILLING.md`, `docs/OPERATIONS.md`, and `docs/RUNBOOK.md`.
