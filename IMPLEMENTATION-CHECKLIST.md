# OMEGA Implementation Checklist

## Repository identity

- [x] Replace template identity and references with OMEGA / `zomega`.
- [x] Align release implementation at version 2.1.0.
- [x] Update changelog for user-visible 2.1 changes.
- [ ] Confirm repository description, topics, homepage, and template status in GitHub settings.
- [ ] Confirm license ownership and year.

## Ownership and governance

- [x] Configure `.github/CODEOWNERS`.
- [x] Provide contribution, pull request, and code-of-conduct guidance.
- [ ] Configure branch protection or repository rulesets in GitHub settings.
- [ ] Require pull request review and passing status checks in GitHub settings.

## Security

- [x] Provide a security policy and private vulnerability-reporting guidance.
- [x] Enable Dependabot configuration, CodeQL, and dependency review workflows.
- [x] Add dependency audit, Python SAST, Trivy filesystem/container/IaC scans, and SBOM generation.
- [x] Keep GitHub Actions permissions least-privileged.
- [x] Enforce route-level API-key scopes.
- [x] Prevent public catalog prompt/policy leakage.
- [x] Harden Kubernetes/Helm security contexts and default-deny networking.
- [ ] Enable Dependabot alerts/security updates, secret scanning, and push protection in GitHub settings.

## Billing and reliability

- [x] Stripe payment event + wallet credit atomic transaction.
- [x] Duplicate provider-event race protection.
- [x] PostgreSQL wallet row locking and non-negative balance constraints.
- [x] Unique financial ledger references.
- [x] Transactional outbox for run dispatch.
- [x] Concurrent idempotency-key serialization.
- [x] Retry-safe skill execution checkpoints.
- [x] Budget-aware agent scheduling.
- [x] Cancellation settlement/refund semantics.
- [x] Reservation reaper.
- [x] Wallet reconciliation.
- [x] Operator reconciliation for ambiguous provider states.

## Development and testing

- [x] Define Python 3.12 and pinned service dependencies.
- [x] Maintain unit, catalog, state, dependency, and repository-contract tests.
- [x] Add PostgreSQL/Redis migration and billing integration tests.
- [x] Keep Makefile and shell entrypoints connected to real commands.
- [x] Use production Dockerfile and safe `.env.example` placeholders.
- [ ] Add a formatter/linter policy when the repository selects Ruff/Black or equivalent.

## CI/CD and release

- [x] Validate repository, Python compilation, tests, and 100 Skills / 12 Agents catalog.
- [x] Run PostgreSQL and Redis integration gates.
- [x] Build immutable GHCR image tags from commit SHA.
- [x] Generate build provenance attestations.
- [x] Verify image attestation before production deploy.
- [x] Run Alembic migration as a Helm pre-upgrade hook.
- [x] Deploy Helm with `--atomic --wait` and external readiness verification.
- [ ] Configure the GitHub `production` environment, reviewers, `KUBECONFIG_B64`, and `OMEGA_HEALTH_URL`.

## Documentation

- [x] Maintain architecture, billing, security, deployment, operations, and runbook docs.
- [x] Record transactional reliability decision under `docs/adr/`.

## Final verification

- [ ] PR CI/security/CodeQL/dependency-review checks pass.
- [ ] Fresh production-like bootstrap passes using configured PostgreSQL/Redis.
- [ ] Production GitHub environment is configured.
- [ ] Live Stripe/OpenAI credentials are configured through secret management.
