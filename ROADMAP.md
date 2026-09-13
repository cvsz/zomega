# zomega Roadmap

zomega 3.0 completes the source-side commercial, marketplace, enterprise service-account, and
application-layer disaster-recovery baseline.

## Completed source baseline

- [x] 12 Agents and 100 Skills
- [x] paid-before-use billing and transactional wallet ledger
- [x] Stripe signed webhook fulfillment
- [x] transactional outbox and retry-safe execution
- [x] cancellation, reservation reaping, reconciliation
- [x] Argon2id API keys and tenant-scoped permissions
- [x] service accounts with RBAC presets
- [x] immutable audit log, export, and retention
- [x] tenant quota/admission policy
- [x] plan/subscription administration
- [x] usage/dashboard API
- [x] Ed25519 private-skill registry
- [x] private-skill entitlement grants
- [x] marketplace listing/purchase/revenue-share settlement
- [x] marketplace-aware financial reconciliation
- [x] PostgreSQL/Redis integration tests
- [x] zomega 2.2 → 3.0 migration compatibility test
- [x] CodeQL/SAST/dependency/container/IaC/SBOM gates
- [x] immutable GHCR provenance
- [x] Helm atomic migration/deployment
- [x] app topology spread and PodDisruptionBudgets
- [x] checksummed backup and restore-verification tooling
- [x] gated DR drill workflow

## Operator / infrastructure configuration remaining

These cannot be completed by repository source alone:

- [x] GitHub main-branch ruleset / required reviews / required checks
- [x] GitHub secret scanning and push protection
- [x] GitHub production environment approvals
- [ ] `KUBECONFIG_B64` and `ZOMEGA_HEALTH_URL` (production environment exists; values still pending)
- [ ] dedicated `DR_SOURCE_DATABASE_URL` and `DR_RESTORE_DATABASE_URL`
- [ ] production PostgreSQL HA / replicas / backups storage
- [ ] production Redis HA
- [ ] production Stripe secret, webhook secret, and Price IDs
- [x] production OpenAI API key configured in protected environment
- [ ] DNS, TLS, ingress and external readiness endpoint
- [ ] external secret manager / rotation process
- [ ] multi-region database replication and traffic failover

## Current operational priority

1. Reconcile legacy branch protection required-check names with the active ruleset/workflow check names.
2. Supply remaining protected production inputs (`KUBECONFIG_B64`, Redis, runtime auth secrets, Stripe, health URL, and DR databases).
3. Run immutable production deploy and verify external readiness.
4. Execute the first real DR drill against a separate restore database and retain evidence.
5. Complete HA/backup/observability infrastructure before claiming production resilience.

## Optional future product surfaces

- browser customer dashboard UI over the existing dashboard/control-plane APIs
- external OIDC/SSO identity provider integration for human users
- publisher fiat payout integration from marketplace accounting
- multi-region control plane once database/Redis infrastructure is provisioned

Every extension must preserve tenant isolation, ledger correctness, idempotency, signature integrity,
retry safety, and fail-closed authorization.
