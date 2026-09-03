# Changelog

All notable OMEGA changes are documented here. The format follows Keep a Changelog;
versioning follows the policy documented in `docs/release.md`.

## [Unreleased]

### Added

- Transactional outbox for durable run dispatch
- Durable per-skill execution checkpoints
- Reservation reaper and wallet reconciliation jobs
- Run cancellation and operator reconciliation commands
- Route-level API-key scope enforcement
- Fixed server-owned Stripe credit packages
- PostgreSQL/Redis billing integration tests
- Trivy, dependency audit, Python SAST, container scanning, and SBOM gates
- Immutable GHCR release build with provenance attestation
- Atomic Helm production deployment workflow
- ADR for real-money transactional reliability

### Changed

- OMEGA version to 2.1.0
- Public catalog now exposes sanitized DTOs only
- Agent execution is budget-aware before launching each skill
- Kubernetes/Helm workloads use hardened security contexts and explicit NetworkPolicy egress
- Initial Alembic migration is frozen and deterministic

### Fixed

- Stripe webhook event/wallet-credit atomicity gap
- Concurrent Stripe duplicate-event race
- Reservation-without-queue-intent failure mode
- Concurrent idempotency-key race across API replicas
- Idempotency hash omission of requested spend reservation
- Cancellation arriving during the final skill
- Historical migration drift caused by importing live model metadata

### Security

- Internal skill prompts, validation rules, and permissions are no longer exposed by catalog routes.
- API keys now enforce billing, run, agent, and skill scopes per route.
