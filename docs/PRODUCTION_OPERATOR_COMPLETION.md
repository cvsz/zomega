# Production Operator Completion

Issue #13 tracks controls that require repository administration, production credentials, and live infrastructure. The source tree provides idempotent tooling so those controls can be applied and verified from an administrator-authenticated GitHub CLI session without storing secrets in the repository.

## One-command apply

Authenticate `gh` as a repository administrator, export the real production values, and run:

```bash
export KUBECONFIG=/secure/path/to/production.kubeconfig
export ZOMEGA_HEALTH_URL=https://zomega.example.com
export DR_SOURCE_DATABASE_URL='postgresql://...source...'
export DR_RESTORE_DATABASE_URL='postgresql://...dedicated-restore...'
export DATABASE_URL='postgresql+psycopg://...'
export REDIS_URL='redis://:...@.../0'
export ZOMEGA_API_KEY_PEPPER='...'
export ZOMEGA_ADMIN_TOKEN='...'
export OPENAI_API_KEY='...'
export STRIPE_SECRET_KEY='...'
export STRIPE_WEBHOOK_SECRET='...'
export STRIPE_PRICE_CREDITS_1000='price_...'
export STRIPE_PRICE_CREDITS_5000='price_...'
export STRIPE_PRICE_CREDITS_20000='price_...'
make operator-apply
```

`production-operator-complete.sh` applies the repository ruleset, required review protection, secret scanning/push protection, Dependabot controls, protected `production` environment, supplied environment secrets, and production URL variables. It never prints secret values.

If `KUBECONFIG_B64` is not supplied but `KUBECONFIG` names a readable file, the script base64-encodes it before storing it as the `KUBECONFIG_B64` environment secret.

## Verify

```bash
make operator-verify
```

Verification is fail-closed. It checks governance, repository security controls, required secret names, latest default-branch checks, the latest Dependency Review, and the external `/health/ready` endpoint. Secret values are not retrieved.

## Deployment behavior

The `Deploy Production` workflow is manual-only, runs only when dispatched from `main`, and uses the protected `production` GitHub Environment. It requires a full lowercase 40-character `image_tag` commit SHA and an explicit `kubectl_version` in `vX.Y.Z` form. The selected source commit must be an ancestor of the current `main` commit before production credentials are loaded.

The workflow pins each third-party action to a full commit SHA, pins Helm to `v4.3.1`, checks kubectl/API-server version skew, and verifies that the image attestation was signed by this repository's `.github/workflows/release.yml`, with a source digest matching `image_tag`. Attestations from self-hosted runners are rejected. The deployment command uses validated environment variables rather than interpolating dispatch input into shell source.

The runtime secret contains connection URLs and provider credentials required by the API, worker, and migration job. The workflow writes values to a mode-`0600` temporary env file, passes only the file path to `kubectl --from-env-file`, and removes the file on step exit. The kubeconfig is mode `0600` and removed in an `always()` cleanup step. This does not prove production environment approvals, successful deployment, or live readiness; those remain external operator gates.

## Evidence gates that remain inherently live

Repository automation cannot truthfully manufacture production evidence. The following only pass after real infrastructure and credentials are supplied:

- successful immutable attested Release and Deploy Production runs;
- reachable external `/health/ready`;
- successful Disaster Recovery Drill against a separate restore database;
- wallet reconciliation after a production smoke transaction;
- live Stripe duplicate-event idempotency verification;
- multi-region replication/failover, documented RPO/RTO, and failover/failback drills.

Keep Issue #13 open until these live gates have recorded evidence.
