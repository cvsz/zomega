# Changelog

All notable OMEGA changes are documented here.

## [Unreleased]

### Added

- Tenant self-service API-key create/list/revoke API.
- Tenant-scoped immutable audit event model and API.
- Migration `0005` for audit events.
- Ruff correctness lint and mypy security/control-plane checks.
- PostgreSQL/Redis control-plane integration tests.
- Live FastAPI smoke verification in CI.
- Mode-0600 API-key file generation.

### Changed

- OMEGA version to 2.2.0.
- Primary tenant keys now include `keys:read`, `keys:write`, and `audit:read`.
- Helm and static Kubernetes image defaults align with 2.2.0.
- Release workflow now repeats lint/type gates before publishing an image.

### Security

- API-key secrets use Argon2id with a public locator for indexed lookup.
- API-key lifecycle audit records never contain raw secrets.
- Self-service key revocation refuses to revoke the currently authenticated key.
- API-key scope input is validated against an explicit allowlist.
