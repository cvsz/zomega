# OMEGA Architecture

This document is the repository-level architecture entrypoint. The detailed service
architecture and operational boundaries are maintained in
[`docs/ARCHITECTURE.md`](ARCHITECTURE.md).

## System context

Authenticated tenants submit Agent and Skill runs to the OMEGA API. The API checks
tenant authorization, entitlements, rate limits, pricing, and available credits
before reserving funds and enqueueing durable work.

## Components and responsibilities

- FastAPI API: authentication, authorization, billing endpoints, run submission, and status.
- PostgreSQL: durable tenants, wallets, runs, payments, evidence, and audit state.
- Redis and ARQ: rate limiting and background execution queue.
- Worker: OpenAI execution, metering, settlement/refund, and evidence recording.
- Stripe: hosted checkout and signed payment-event source.
- Skills and Agents catalogs: declarative, validated capability definitions.

## Trust boundaries and security

API keys, payment events, model-provider responses, and queued jobs are untrusted at
their boundaries. Authorization, signature verification, tenant scoping, idempotency,
and transactional credit invariants must be enforced server-side.

## Deployment and recovery

The service is containerized and depends on PostgreSQL, Redis, Stripe, OpenAI, and an
HTTPS public URL. Deployment, operations, recovery, and rollback details are tracked
in the uppercase service documents under `docs/`.

Material decisions belong in [`docs/adr/`](adr/).
