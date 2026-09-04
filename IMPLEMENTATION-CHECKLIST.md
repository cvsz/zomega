# OMEGA Implementation Checklist

## Repository identity

- [x] Replace template identity and references with OMEGA / `zomega`.
- [x] Align source release at version 2.2.0.
- [x] Update changelog and roadmap.
- [ ] Confirm repository description, topics, homepage, template status, license ownership, and year in GitHub settings.

## Ownership and governance

- [x] Configure `.github/CODEOWNERS`.
- [x] Provide contribution, pull request, and code-of-conduct guidance.
- [ ] Configure branch protection or repository rulesets in GitHub settings.
- [ ] Require pull request review and passing status checks in GitHub settings.

## Security

- [x] Security policy and vulnerability-reporting guidance.
- [x] Dependabot configuration, CodeQL, dependency review.
- [x] pip-audit, Bandit, Trivy filesystem/container/IaC, SBOM.
- [x] Least-privileged GitHub Actions permissions.
- [x] Route-level API-key scopes.
- [x] Argon2id API-key secret storage.
- [x] Public catalog prompt/policy protection.
- [x] Kubernetes/Helm workload hardening and default-deny networking.
- [x] Tenant audit log for API-key mutations.
- [ ] Enable Dependabot alerts/security updates, secret scanning, and push protection in GitHub settings.

## Billing and reliability

- [x] Atomic Stripe event + wallet credit transaction.
- [x] Duplicate-event race protection.
- [x] PostgreSQL wallet row locking and financial constraints.
- [x] Transactional outbox.
- [x] Cross-replica idempotency.
- [x] Retry-safe execution checkpoints.
- [x] Budget-aware scheduling and cancellation.
- [x] Reservation reaper and wallet reconciliation.
- [x] Operator reconciliation for ambiguous provider states.

## Control plane

- [x] Tenant self-service API-key listing.
- [x] Tenant self-service API-key creation.
- [x] Tenant self-service API-key revocation.
- [x] Explicit scope allowlist.
- [x] Immutable tenant audit events.
- [x] Audit event retrieval API.

## Development and testing

- [x] Python 3.12 and pinned runtime dependencies.
- [x] Pinned Ruff and mypy development checks.
- [x] Unit/catalog/state/security tests.
- [x] PostgreSQL/Redis billing, queue, and control-plane integration tests.
- [x] Live FastAPI smoke test.
- [x] Production Dockerfile and safe `.env.example`.

## CI/CD and release

- [x] Compile/test/lint/type/catalog validation.
- [x] PostgreSQL/Redis integration gates.
- [x] Immutable GHCR commit-SHA images.
- [x] Build provenance attestations.
- [x] Deploy-time attestation verification.
- [x] Alembic Helm pre-upgrade migration.
- [x] Helm `--atomic --wait` and readiness verification.
- [ ] Configure GitHub `production` environment, reviewers, `KUBECONFIG_B64`, and `OMEGA_HEALTH_URL`.

## Final verification

- [ ] OMEGA 2.2 PR CI/Security/CodeQL/Dependency Review pass.
- [x] Fresh PostgreSQL/Redis migration and integration bootstrap covered in CI.
- [ ] Production GitHub environment configured.
- [ ] Live Stripe/OpenAI credentials configured through secret management.
