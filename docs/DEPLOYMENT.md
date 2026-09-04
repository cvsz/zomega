# Production Deployment — zomega 3.0

## Required runtime secrets

- DATABASE_URL
- REDIS_URL
- zomega_API_KEY_PEPPER
- zomega_ADMIN_TOKEN
- OPENAI_API_KEY
- STRIPE_SECRET_KEY
- STRIPE_WEBHOOK_SECRET
- STRIPE_PRICE_CREDITS_1000
- STRIPE_PRICE_CREDITS_5000
- STRIPE_PRICE_CREDITS_20000
- zomega_PUBLIC_URL

Inject runtime values through GitHub Environment Secrets plus a Kubernetes secret manager such as
External Secrets, Vault, or SOPS. Never bake credentials into the image.

## Database migration

The current Alembic head is `0008`.

For direct deployments:

```bash
alembic upgrade head
```

The Helm chart runs `alembic upgrade head` as a pre-install/pre-upgrade hook. The new API/worker
version is not rolled out if migration fails.

zomega CI also proves a data-bearing upgrade path from the 2.2 schema at `0005` to the 3.0 head,
including expansion of existing primary-key scopes.

## Runtime processes

```bash
zomega serve
arq zomega.jobs.WorkerSettings
```

The worker owns execution plus outbox dispatch, reservation reaping, wallet reconciliation, and
audit-retention pruning.

## Kubernetes / Helm

Provision the `zomega-runtime` Secret, then deploy an immutable commit-SHA image:

```bash
helm upgrade --install zomega deploy/helm/zomega \
  --namespace zomega \
  --create-namespace \
  --set image.repository=ghcr.io/cvsz/zomega \
  --set image.tag=<immutable-commit-sha> \
  --atomic \
  --wait
```

The production GitHub workflow verifies the GHCR build attestation before deployment.

zomega 3.0 includes:

- two API replicas by default
- two worker replicas by default
- soft topology spread across Kubernetes nodes
- PodDisruptionBudgets with at least one API and one worker available
- non-root/read-only/seccomp/capability-drop security contexts
- default-deny NetworkPolicy with explicit runtime egress

## Required GitHub production environment

Environment: `production`

Secret:
- `KUBECONFIG_B64`

Variable:
- `zomega_HEALTH_URL`

Recommended protection:
- required reviewer
- deployment branch/tag restriction
- prevent self-review where supported

## Disaster recovery

For the manual DR drill workflow configure separate secrets:

- `DR_SOURCE_DATABASE_URL`
- `DR_RESTORE_DATABASE_URL`

The restore database must be dedicated/disposable and must never be the production source DB.

See `docs/DISASTER_RECOVERY.md`.
