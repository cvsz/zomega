# Production Deployment — OMEGA 2.1

## Required runtime secrets

- DATABASE_URL
- REDIS_URL
- OMEGA_API_KEY_PEPPER
- OMEGA_ADMIN_TOKEN
- OPENAI_API_KEY
- STRIPE_SECRET_KEY
- STRIPE_WEBHOOK_SECRET
- STRIPE_PRICE_CREDITS_1000
- STRIPE_PRICE_CREDITS_5000
- STRIPE_PRICE_CREDITS_20000
- OMEGA_PUBLIC_URL

Inject secrets at runtime through GitHub Environment Secrets plus your Kubernetes secret manager
(External Secrets, Vault, SOPS, or an equivalent). Never bake credentials into the image.

## Database migration

OMEGA 2.1 freezes migration `0001` and applies additive reliability changes in `0002`.

For direct deployments:

```bash
alembic upgrade head
```

The Helm chart runs `alembic upgrade head` as a pre-install/pre-upgrade hook before API and worker
rollout. If the migration fails, Helm does not start the new application version.

## Containers

Run at least:

```bash
omega serve
arq omega.jobs.WorkerSettings
```

The worker owns normal run execution plus outbox dispatch, reservation reaping, and wallet
reconciliation cron jobs.

## Kubernetes / Helm

Provision the `omega-runtime` Secret first, then:

```bash
helm upgrade --install omega deploy/helm/omega   --namespace omega   --create-namespace   --set image.repository=ghcr.io/cvsz/zomega   --set image.tag=<immutable-commit-sha>   --atomic   --wait
```

The production GitHub workflow verifies the GHCR attestation before running this deployment.

## Required GitHub production environment

Create environment `production` with:

Secret:
- `KUBECONFIG_B64`

Variable:
- `OMEGA_HEALTH_URL`

Recommended environment protection:
- required reviewer
- deployment branch/tag restrictions
- prevent self-review where supported

Repository rules should require CI, CodeQL, dependency review, and security checks before merge.

## Network policy

OMEGA defaults to deny. API/worker/migration pods receive only:
- DNS egress
- TCP 443 for external APIs
- TCP 5432 for PostgreSQL
- TCP 6379 for Redis
- API ingress on port 8000

If your infrastructure uses different ports or a service mesh, adjust policy explicitly before deploy.
