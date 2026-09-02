# About OMEGA

OMEGA Production 2.0 is a paid-before-use, multi-tenant API for running governed
Agents and Skills. It is maintained in the `cvsz` GitHub namespace and is intended
to be operated as a service with durable state, explicit authorization, and auditable
financial and execution boundaries.

## Product scope

- Tenant-scoped API keys and authorization
- Entitlement, rate-limit, pricing, and credit-reservation enforcement
- Durable PostgreSQL state and Redis-backed jobs
- OpenAI-backed agent and skill execution
- Stripe Checkout and signed webhook processing
- Run evidence, settlement, refund, and operational controls

## Engineering posture

OMEGA treats security, billing correctness, tenant isolation, observability, testing,
documentation, and rollback as part of the product. Security-sensitive paths should
fail closed, and repository or CI gates should not be weakened to make a build green.

## Repository role

This repository contains the service, its policies, operational scripts, deployment
manifests, tests, and the catalog of 100 Skills and 12 Agents. Public documentation
must remain free of credentials, private keys, customer data, and other sensitive
information.

## Ownership

- GitHub: `github.com/cvsz/zomega`
- Maintainer: `@cvsz`
