# OMEGA Implementation Checklist

## Repository/source identity

- [x] OMEGA / zomega repository identity
- [x] source/API/Helm/Kubernetes release aligned at 3.0.0
- [x] changelog, roadmap, architecture and runbooks maintained
- [ ] confirm GitHub repository description/topics/homepage/license metadata in repository settings

## Authentication / enterprise controls

- [x] Argon2id API-key secrets with indexed public locators
- [x] route-level scopes
- [x] self-service API-key lifecycle
- [x] service-account key type
- [x] deterministic RBAC role presets
- [x] role scope-escalation prevention
- [x] constant-time platform admin-token authentication
- [x] audit event retrieval/export/retention

## Billing / reliability

- [x] atomic Stripe event + wallet credit
- [x] wallet locking and database constraints
- [x] idempotency and transactional outbox
- [x] retry-safe skill checkpoints
- [x] budget-aware execution/cancellation
- [x] reservation reaping and wallet reconciliation
- [x] marketplace debit/earning reconciliation

## Commercial SaaS controls

- [x] monthly run cap
- [x] monthly credit/spend cap
- [x] Agent allowlist
- [x] Skill allowlist
- [x] subscription state
- [x] plan administration
- [x] usage/dashboard API
- [x] upgrade migration for existing primary-key scopes

## Private registry / marketplace

- [x] publisher profile
- [x] Ed25519 public-key validation
- [x] signed canonical manifest publishing
- [x] signer-key snapshot
- [x] stored signature verification
- [x] private-skill entitlement grants
- [x] marketplace listing
- [x] idempotent marketplace purchase
- [x] buyer wallet debit
- [x] publisher wallet revenue-share settlement
- [x] platform revenue accounting

## Development / verification

- [x] Python 3.12 pinned runtime
- [x] Ruff and mypy gates
- [x] unit/catalog/state/security tests
- [x] PostgreSQL/Redis billing/control-plane/commercial integration
- [x] Ed25519 registry integration
- [x] marketplace reconciliation integration
- [x] API smoke test
- [x] migration round-trip
- [x] OMEGA 2.2 → 3.0 upgrade test
- [x] CodeQL/dependency review/pip-audit/Bandit/Trivy/SBOM workflows

## Deployment / DR

- [x] immutable GHCR SHA image
- [x] provenance attestation
- [x] deploy-time attestation verification
- [x] Helm pre-upgrade Alembic migration
- [x] Helm atomic rollout
- [x] topology spread
- [x] PodDisruptionBudgets
- [x] checksummed backup evidence
- [x] isolated restore verification
- [x] gated DR workflow
- [ ] configure production GitHub environment and credentials
- [ ] configure production PostgreSQL/Redis HA and backup storage
- [ ] execute and retain first real production DR drill evidence

## GitHub account/repository controls

- [ ] branch/ruleset protection
- [ ] required PR reviews/checks
- [ ] secret scanning/push protection
- [ ] Dependabot security settings
- [ ] production environment reviewers

## Final evidence

- [ ] OMEGA 3.0 PR CI/Security/CodeQL/Dependency Review pass
- [x] fresh database bootstrap is covered by CI
- [x] upgrade compatibility is covered by CI
- [ ] live Stripe/OpenAI credentials configured through secret management
- [ ] live production readiness endpoint verified
