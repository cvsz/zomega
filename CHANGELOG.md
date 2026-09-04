# Changelog

All notable OMEGA changes are documented here.

## [Unreleased]

### Added

- OMEGA 3.0 commercial and enterprise control-plane APIs.
- Tenant monthly credit/run quotas enforced transactionally.
- Per-tenant Agent and Skill allowlists.
- Subscription and plan administration.
- Customer usage/dashboard API.
- Service accounts with deterministic RBAC presets.
- Audit NDJSON export and scheduled tenant-specific retention.
- Ed25519 publisher profiles and signed private-skill registry.
- Historical signer-key snapshots and stored manifest verification.
- Private-skill entitlement grants.
- Marketplace listings, idempotent purchases, and revenue-share accounting.
- Atomic publisher wallet settlement for marketplace earnings.
- Migrations `0006`–`0008`.
- Checksummed backup evidence and isolated restore verification.
- Gated disaster-recovery drill workflow.
- Kubernetes topology spread and PodDisruptionBudgets.
- OMEGA 2.2 → 3.0 migration compatibility test.

### Changed

- OMEGA source/API/Helm/Kubernetes version to 3.0.0.
- Monthly credit limits account for execution charges, open reservations, and marketplace purchases.
- Wallet reconciliation includes marketplace buyer debits and publisher earnings.
- Existing active primary keys receive OMEGA 3.0 commercial scopes during migration.
- Release type-checking covers commercial, registry, and marketplace modules.

### Security

- Private-skill manifests use Ed25519 asymmetric verification.
- Stored skill versions retain the signer key snapshot needed for historical verification.
- Platform plan/quota mutation requires constant-time validated `X-OMEGA-Admin-Token`.
- Service-account role scopes cannot be escalated beyond the selected preset.
- DR restore verification refuses the configured source database.
