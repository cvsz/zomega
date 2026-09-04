# Security — zomega 3.0

- Never commit secrets, API keys, private publisher keys, production credentials, or database dumps.
- Tenant API-key secrets are stored only as Argon2id hashes of secret + server pepper.
- API-key public locators are non-secret lookup identifiers.
- Service accounts use deterministic least-privilege RBAC scope presets.
- Platform quota/subscription mutation requires the separate admin token.
- Stripe webhooks require provider signature verification.
- Paid runs reserve balance before execution.
- Private skill authenticity uses Ed25519 signatures over canonical manifests.
- Stored private-skill versions retain the signer public-key snapshot for historical verification.
- SHA-256 is used for non-secret content integrity and backup checksums, not API-key password hashing.
- Marketplace purchase accounting is atomic and idempotent.
- Internal prompts/policies are not exposed by public catalog DTOs.
- Kubernetes workloads run non-root with read-only root filesystems, dropped capabilities, seccomp,
  disabled service-account token automounting, default-deny networking, topology spread, and PDBs.
- Production secrets must be injected by an external secret manager.
- Backup dumps must remain encrypted/protected by the storage layer and must not be uploaded as
  ordinary CI artifacts.
- Security gates must not be disabled merely to obtain a passing build.
