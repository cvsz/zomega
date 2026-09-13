# zomega Status

_Last evidence review: 2026-09-08_

## Executive status

| Area | Status | Evidence / limitation |
|---|---|---|
| Source/runtime baseline | PASS | zomega 3.0 source, billing, commercial controls, registry, marketplace, migrations through 0008 |
| CI correctness | PASS | unit, integration, lint, mypy, migration round-trip, 2.2→3.0 upgrade test |
| Security pipeline | PASS | CodeQL, dependency review, pip-audit, Bandit, Trivy filesystem/IaC/container, SBOM |
| GitHub governance | PASS with drift remediation pending | main is protected; ruleset/environment automation has been applied. Legacy branch-protection check names are being reconciled to workflow check names |
| Protected production environment | PARTIAL | environment + reviewer exist; not all required secrets/variables are present |
| Production deployment | PENDING | kubeconfig and health URL are still missing |
| Runtime provider inputs | PARTIAL | PostgreSQL and OpenAI are configured; Redis/runtime-auth/Stripe inputs remain missing |
| Disaster recovery tooling | PASS | backup checksum/evidence + isolated restore verification + gated DR workflow exist |
| Real DR evidence | PENDING | first real production DR drill has not been evidenced |
| Database/Redis HA | PENDING | production HA/replication topology not yet evidenced |
| DNS/TLS/Ingress | PENDING | no verified external readiness endpoint |
| Multi-region | PENDING | no replication/failover/failback evidence |

## Confirmed GitHub governance

- `main` is protected.
- repository-admin automation exists through `make operator-apply`.
- fail-closed verification exists through `make operator-verify`.
- secret scanning, push protection, Dependabot controls, protected `production` environment, and reviewer configuration are tracked as applied.
- active ruleset policy requires PR review and the real workflow checks.
- this review found legacy branch-protection contexts drifted from workflow check names; the hardening patch reconciles them to:
  - `unit`
  - `integration`
  - `Analyze Actions and Python`
  - `application-security`
  - `dependency-review`

## Production inputs

Confirmed present:

- `DATABASE_URL`
- `OPENAI_API_KEY`

Still required:

- `KUBECONFIG_B64`
- `ZOMEGA_HEALTH_URL`
- `DR_SOURCE_DATABASE_URL`
- `DR_RESTORE_DATABASE_URL`
- `REDIS_URL`
- `ZOMEGA_API_KEY_PEPPER`
- `ZOMEGA_ADMIN_TOKEN`
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PRICE_CREDITS_1000`
- `STRIPE_PRICE_CREDITS_5000`
- `STRIPE_PRICE_CREDITS_20000`

## Live evidence still required

zomega should not be described as fully production-complete until all of the following are evidenced:

1. immutable attested image deployed through `Deploy Production`;
2. external `/health/ready` returns ready;
3. wallet reconciliation passes after a production smoke transaction;
4. live Stripe duplicate-event delivery proves idempotency;
5. real DR drill restores to a separate database and passes financial/schema invariants;
6. PostgreSQL/Redis HA and durable encrypted backup storage are operating;
7. DNS/TLS/Ingress and monitoring/alerting are verified;
8. multi-region RPO/RTO and failover/failback are tested if multi-region is claimed.

## Open PR review

PR #8 (`feat: add zomega ECC bundle`) is not a runtime blocker. It is generated Claude/Codex tooling and is currently diverged from `main` (behind the current architecture). It should be regenerated or rebased against the current repository and manually reviewed for policy/config accuracy before merge.

## Definition of current readiness

**Source-ready:** yes.

**Governance-ready:** yes, after applying the branch-protection context reconciliation in the current hardening PR.

**Deploy-ready:** no — protected production inputs are incomplete.

**Production-evidenced:** no — external readiness, real DR, live billing smoke/idempotency, HA, and operational infrastructure evidence remain outstanding.
