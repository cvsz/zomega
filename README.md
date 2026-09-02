# OMEGA Production 2.0

OMEGA is a paid-before-use, multi-tenant Agents + Skills API.

This edition has no development execution provider and no local in-memory billing path.
Billable execution uses OpenAI through the official Python SDK; payments use Stripe Checkout
and signed Stripe webhooks; durable state uses PostgreSQL; rate limiting and background jobs
use Redis + ARQ.

## Invariant

```text
API key → tenant → entitlement → rate limit → price → transactional credit reservation
→ durable queue → worker → OpenAI Responses API → meter → settle/refund → evidence
```

A run cannot be queued unless the wallet reservation succeeds.

## Required services

- PostgreSQL
- Redis
- Stripe account + secret/webhook signing secret
- OpenAI API key
- HTTPS public URL

## Boot

```bash
cp .env.example .env
# fill required values
docker compose up --build -d
docker compose exec api omega create-tenant --name "First Tenant" --plan pro
```

The tenant creation command prints the API key exactly once.

## Buy credits

Authenticated clients call:

```http
POST /v1/checkout
Authorization: Bearer omega_...
Content-Type: application/json

{"credits":1000}
```

The API returns a Stripe-hosted checkout URL. Credits are granted only from a verified
`checkout.session.completed` or `checkout.session.async_payment_succeeded` event whose
`payment_status` is `paid`.

Configure Stripe to send events to:

`POST /v1/payment-webhooks/stripe`

## Run a Skill

```http
POST /v1/skills/repository-intelligence/runs
Authorization: Bearer omega_...
Idempotency-Key: customer-operation-123
Content-Type: application/json

{"input":{"repository":"owner/project"}}
```

Returns HTTP 202 and a `run_id`. Poll `GET /v1/runs/{run_id}`.

## Run an Agent

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
