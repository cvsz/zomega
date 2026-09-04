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

Restore verification requires a dedicated disposable restore database:

```bash
ZOMEGA_BACKUP_FILE=backups/zomega-....dump \
ZOMEGA_RESTORE_VERIFY_DATABASE_URL=postgresql://.../zomega_restore \
make restore-verify
```

The script refuses to restore into `ZOMEGA_SOURCE_DATABASE_URL` when supplied.

GitHub also includes a gated manual `Disaster Recovery Drill` workflow. Production must configure
`DR_SOURCE_DATABASE_URL` and a separate `DR_RESTORE_DATABASE_URL`.

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
