# OMEGA Production 2.2

OMEGA is a paid-before-use, multi-tenant Agents + Skills API with 12 specialized Agents and 100 billable Skills.

OMEGA 2.2 adds a self-service tenant control plane on top of the 2.1 transactional reliability baseline:
API-key lifecycle management, immutable audit events, Argon2id API-key storage, Ruff/mypy gates,
PostgreSQL/Redis control-plane integration tests, and live API smoke verification.

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

## API-key model

OMEGA API keys use:

```text
omega_<24-hex-public-locator>_<secret>
```

The locator is indexed for O(1) lookup. The secret is stored only as Argon2id(secret + server pepper).

Generate a key without printing it:

```bash
omega generate-api-key --output ./tenant.key
chmod 600 ./tenant.key
```

Create the first tenant:

```bash
docker compose exec api omega create-tenant --name "First Tenant" --plan pro
```

The command accepts and confirms the key via hidden terminal input.

## Tenant API-key lifecycle

Primary tenant keys include:

- `keys:read`
- `keys:write`
- `audit:read`

List keys:

```http
GET /v1/api-keys
Authorization: Bearer omega_...
```

Create a secondary key:

```http
POST /v1/api-keys
Authorization: Bearer omega_...
Content-Type: application/json

{
  "name": "worker",
  "scopes": ["skills:run", "runs:read"]
}
```

The raw secret is returned exactly once. Listing keys never returns the secret.

Revoke a secondary key:

```http
DELETE /v1/api-keys/{key_id}
Authorization: Bearer omega_...
```

OMEGA refuses to revoke the currently authenticated key through this endpoint.

## Audit log

```http
GET /v1/audit?limit=100
Authorization: Bearer omega_...
```

API-key creation and revocation generate tenant-scoped audit events containing identifiers and
metadata only; secrets are never recorded.

## Required services

- PostgreSQL
- Redis
- Stripe account with three server-owned Price IDs
- OpenAI API key
- HTTPS public URL

## Boot

```bash
cp .env.example .env
docker compose up --build -d
docker compose exec api alembic upgrade head
```

## Credit packages

```http
GET /v1/billing/packages
```

```http
POST /v1/checkout
Authorization: Bearer omega_...
Content-Type: application/json

{"package_id":"credits_1000"}
```

Credits are granted only from a verified Stripe-signed paid Checkout webhook. Payment event
recording and wallet crediting commit atomically in PostgreSQL.

## Run execution

```http
POST /v1/skills/repository-intelligence/runs
Authorization: Bearer omega_...
Idempotency-Key: operation-123
Content-Type: application/json

{"input":{"repository":"owner/project"}}
```

```http
POST /v1/agents/omega-security/runs
Authorization: Bearer omega_...
Idempotency-Key: security-run-123
Content-Type: application/json

{"input":{"objective":"Audit the supplied repository"},"max_spend_credits":500}
```

## Production validation

```bash
./verify.sh
```

CI additionally runs:

- Python compilation
- unit tests
- Ruff correctness lint
- mypy checks for the security/control-plane modules
- PostgreSQL + Redis migrations
- billing/queue/control-plane integration tests
- live FastAPI health and catalog smoke tests
- CodeQL, dependency review, pip-audit, Bandit, Trivy, and SBOM generation
