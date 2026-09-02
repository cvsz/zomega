# OMEGA Implementation Checklist

Use this checklist when extending or releasing OMEGA so repository foundations remain
aligned with the service's actual stack and threat model.

## Repository identity

- [x] Replace template identity and references with OMEGA / `zomega`.
- [ ] Confirm repository description, topics, homepage, and template status.
- [ ] Confirm release version and changelog entry.
- [ ] Confirm license ownership and year.

## Ownership and governance

- [x] Configure `.github/CODEOWNERS`.
- [x] Provide contribution, pull request, and code-of-conduct guidance.
- [ ] Configure branch protection or repository rulesets.
- [ ] Require pull request review where appropriate.
- [ ] Require passing status checks before merge.

## Security

- [x] Provide a security policy and private vulnerability-reporting link.
- [x] Enable Dependabot configuration, CodeQL, and dependency review.
- [ ] Enable Dependabot alerts and security updates in repository settings.
- [ ] Configure secret scanning and push protection where available.
- [ ] Add stack-specific SAST, container, IaC, and SBOM checks as risk requires.
- [x] Keep GitHub Actions permissions least-privileged by default.

## Development

- [x] Define Python 3.12 and the pinned service dependencies.
- [ ] Add formatter and linter configuration when selected for the project.
- [x] Maintain unit, catalog, state, dependency, and repository-contract tests.
- [x] Keep Makefile and shell entrypoints connected to real commands.
- [x] Use the application Dockerfile and safe `.env.example` placeholders.

## CI/CD

- [x] Validate repository baseline, Python compilation, tests, and catalog counts.
- [x] Keep deployment and release workflows behind explicit workflow dispatch.
- [ ] Configure production environments, approvals, and deployment protections.
- [ ] Verify fork workflows do not receive unsafe credentials.

## Release

- [x] Document versioning, release gates, and rollback expectations.
- [ ] Update `CHANGELOG.md` for user-visible changes.
- [ ] Configure trusted artifact publishing only when the deployment target is ready.
- [ ] Add provenance, signing, and attestations for production artifacts where appropriate.

## Documentation

- [x] Maintain service-specific architecture, security, deployment, operations, and runbook docs.
- [x] Provide development, release, and ADR documentation entrypoints.
- [ ] Record material architectural decisions under `docs/adr/`.

## Final verification

- [ ] Fresh clone works with documented bootstrap steps.
- [ ] CI and security checks pass on `main` and pull requests.
- [ ] No secrets or private information are committed.
- [ ] A release can be created and rolled back according to documented procedures.
