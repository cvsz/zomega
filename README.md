# zomega Production 3.0

zomega is a paid-before-use, multi-tenant Agents + Skills platform with 12 specialized Agents and 100 billable Skills.

zomega 3.0 completes the source-side commercial and enterprise baseline on top of the transactional
billing and control-plane foundations from 2.x.

## Core invariants

```text
API key / service account
→ tenant + role/scope + entitlement
→ rate limit + tenant quota policy
→ transactional run + wallet reservation + ledger + outbox
→ Redis dispatch
→ retry-safe worker checkpoint
→ OpenAI Responses API
→ meter
→ settle / refund
→ evidence + audit + reconciliation
```

No billable run is dispatched unless its reservation and durable queue intent commit successfully.

## zomega 3.0 capabilities

- Argon2id API keys with indexed public locators
- tenant self-service API-key lifecycle
- service accounts with RBAC presets
- immutable tenant audit log + NDJSON export + retention
- tenant monthly run and credit caps enforced inside PostgreSQL admission transactions
- per-tenant allowed Agent/Skill policy
- subscription/plan administration behind the platform admin token
- usage/dashboard API
- Ed25519 publisher identity and signed private-skill manifests
- signer-key snapshots for historical signature verification
- private-skill entitlement grants
- marketplace listings and idempotent purchases
- atomic buyer debit + publisher revenue-share credit
- marketplace-aware wallet reconciliation
- checksummed PostgreSQL backup evidence
- isolated restore verification
- Kubernetes topology spread + PodDisruptionBudgets
- immutable GHCR releases + provenance attestation

## Service accounts and RBAC

Primary tenant keys can create scoped service accounts:

```http
POST /v1/service-accounts
Authorization: Bearer zomega_...
Content-Type: application/json

{"name":"automation","role":"operator"}
```

Roles:

- `reader`: read-only billing/run/audit/dashboard/catalog-related controls
- `operator`: run/cancel Agent and Skill workloads
- `billing`: billing and subscription visibility/write operations
- `publisher`: private registry and marketplace publishing
- `tenant-admin`: all tenant-level scopes

A role cannot request scopes outside its preset.

## Commercial control plane

Tenant dashboard:

```http
GET /v1/dashboard
Authorization: Bearer zomega_...
```

Platform-admin quota policy:

```http
PUT /v1/admin/tenants/{tenant_id}/control
X-zomega-Admin-Token: ...
Content-Type: application/json

{
  "monthly_credit_limit": 50000,
  "monthly_run_limit": 2000,
  "allowed_agents": [],
  "allowed_skills": [],
  "audit_retention_days": 365
}
```

Quota enforcement runs inside the same PostgreSQL transaction that admits the run, using an advisory
lock scoped to tenant + month.

## Signed private skills

Publishers register an Ed25519 public key and submit canonical JSON manifests signed with the matching
private key. zomega stores the manifest hash, signature, and signer public-key snapshot.

```http
POST /v1/private-skills
Authorization: Bearer zomega_...
```

Verify a stored version:

```http
GET /v1/private-skills/{skill_version_id}/verify
Authorization: Bearer zomega_...
```

## Marketplace

A publisher can list a signed private skill. A buyer purchase uses `Idempotency-Key` and commits in
one transaction:

```text
buyer wallet debit
+ buyer financial ledger
+ publisher wallet credit
+ publisher financial ledger
+ marketplace revenue split ledger
+ private-skill grant
```

Platform revenue remains explicitly recorded in the marketplace ledger.

## Backup and disaster recovery

Create a backup:

```bash
make backup
```

The backup emits a custom-format dump, SHA-256 checksum, and JSON evidence manifest.

Restore verification requires a dedicated disposable PostgreSQL cluster, the source connection for cluster-identity comparison, an explicit drill confirmation, and a target database marker:

```bash
ZOMEGA_BACKUP_FILE=backups/zomega-....dump \
ZOMEGA_SOURCE_DATABASE_URL=postgresql://.../zomega_source \
ZOMEGA_RESTORE_VERIFY_DATABASE_URL=postgresql://.../zomega_restore \
ZOMEGA_RESTORE_TARGET_MARKER=REPLACE_WITH_32_TO_128_CHARACTER_RANDOM_TOKEN \
ZOMEGA_RESTORE_CONFIRMATION=DRILL \
make restore-verify
```

Before invoking `pg_restore --clean --if-exists`, the script compares the PostgreSQL cluster system identifier reported by both connections and refuses to proceed if either identifier cannot be read, is malformed, or matches the source cluster. It computes the SHA-256 digest of the 32-128 character random value supplied as `ZOMEGA_RESTORE_TARGET_MARKER` and requires the target database comment to equal `ZOMEGA_DISPOSABLE_RESTORE_TARGET_SHA256:<lowercase_sha256_hex>`. PostgreSQL comments are readable by any connected user, including for shared database objects, so the raw marker token must never be stored in a comment. Provision only the digest on the dedicated disposable restore database, for example:

```sql
COMMENT ON DATABASE zomega_restore
IS 'ZOMEGA_DISPOSABLE_RESTORE_TARGET_SHA256:REPLACE_WITH_LOWERCASE_SHA256_HEX_OF_MARKER_TOKEN';
```

Generate the random token with a cryptographically secure generator and keep the raw token only in the approved secret store. Compute its lowercase SHA-256 hex digest and place only that digest in the database comment. Never set this marker on a source or production application database. Missing, unreadable, or mismatched marker fails closed before restore. The digest label is defense-in-depth against accidental target selection; it is not proof of database identity or a substitute for an isolated disposable target and operator review.

The manual GitHub Disaster Recovery Drill workflow is limited to `main` and uses the protected `production` GitHub Environment. Configure these environment secrets:

- `DR_SOURCE_DATABASE_URL`
- `DR_RESTORE_DATABASE_URL`
- `DR_RESTORE_TARGET_MARKER`

The production environment must retain its required-reviewer protection. Do not run a restore workflow until the restore target is separately provisioned, marked, and reviewed. The workflow does not upload the database dump as an Actions artifact and removes its ephemeral backup on completion.

## Validation

```bash
make lint
make typecheck
make test
make validate
make verify
```

CI additionally proves:

- fresh migration through Alembic head `0008`
- zomega 2.2 → 3.0 primary-key scope upgrade compatibility
- PostgreSQL/Redis billing, control-plane, quota, registry, marketplace integration
- Ed25519 signature verification
- marketplace buyer and publisher reconciliation
- API health/catalog smoke test
- migration downgrade/upgrade round trip
- CodeQL, dependency review, pip-audit, Bandit, Trivy and SBOM gates

See `docs/COMMERCIAL.md`, `docs/PRIVATE_REGISTRY.md`, `docs/DISASTER_RECOVERY.md`, and
`docs/ARCHITECTURE.md`.
