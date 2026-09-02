# OMEGA Roadmap

This roadmap tracks the repository and service foundations that support OMEGA's
paid-before-use, multi-tenant execution model.

## Foundation

- [x] Tenant-scoped authentication and authorization boundary
- [x] Durable PostgreSQL state and migration entrypoints
- [x] Redis-backed rate limiting and background-job boundary
- [x] Stripe checkout and signed webhook flow
- [x] OpenAI-backed agent and skill execution path
- [x] Run evidence and credit reservation/settlement model
- [x] 100 Skills and 12 Agents catalog
- [x] Repository governance, CI, CodeQL, dependency review, and Dependabot baseline

## Next hardening areas

- [ ] Complete production deployment wiring and environment protections
- [ ] Add trusted artifact provenance, signing, and rollback evidence
- [ ] Expand integration and end-to-end coverage against PostgreSQL, Redis, Stripe, and OpenAI test environments
- [ ] Add container, IaC, SBOM, and dependency policy checks appropriate to deployment
- [ ] Record material architecture decisions as ADRs

The service must preserve tenant isolation, authorization, billing correctness, and
fail-closed security behavior as capabilities are added.
