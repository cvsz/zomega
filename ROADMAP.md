# OMEGA Roadmap

OMEGA 2.1 establishes the production reliability baseline for the paid-before-use execution model.

## Completed foundation

- [x] 12 Agents and 100 Skills
- [x] Tenant-scoped API-key authentication and per-route scopes
- [x] PostgreSQL source of truth and deterministic Alembic migrations
- [x] Atomic prepaid wallet, reservations, ledger, settlement, and refund
- [x] Stripe Checkout with server-owned credit packages and signed webhook fulfillment
- [x] Transactional outbox and Redis/ARQ delivery
- [x] Retry-safe per-skill checkpoints and ambiguous-provider fail-safe
- [x] Budget-aware execution and cancellation
- [x] Reservation reaper and wallet reconciliation
- [x] OpenAI Responses API execution
- [x] Sanitized public catalog
- [x] PostgreSQL/Redis integration tests
- [x] SAST, dependency, container, secret, IaC, and SBOM security gates
- [x] Immutable GHCR publishing with provenance attestation
- [x] Helm migration hook, atomic deployment, readiness verification
- [x] Architecture ADRs

## Operator configuration remaining

These are repository/account settings or external credentials, not missing source implementation:

- [ ] GitHub repository ruleset / branch protection
- [ ] GitHub production environment approvals
- [ ] Dependabot alerts/security updates and secret push protection
- [ ] Production Kubernetes credentials
- [ ] Production Stripe Price IDs/webhook secret
- [ ] Production OpenAI API key
- [ ] Production DNS/TLS and external readiness URL

## Next product layer

After the production environment is live:

- tenant self-service API-key lifecycle
- plan/subscription administration
- customer usage dashboard
- publisher-signed private skill catalog
- marketplace and revenue-share accounting
- multi-region disaster recovery

Every future capability must preserve tenant isolation, billing correctness, retry safety, and
fail-closed security behavior.
