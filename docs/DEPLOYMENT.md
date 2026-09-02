# Production Deployment

Required secret values:
- DATABASE_URL
- REDIS_URL
- OMEGA_API_KEY_PEPPER
- OMEGA_ADMIN_TOKEN
- OPENAI_API_KEY
- STRIPE_SECRET_KEY
- STRIPE_WEBHOOK_SECRET
- OMEGA_PUBLIC_URL

Inject them at runtime through your secret manager. Never bake them into images.

Run database migrations before API/worker rollout:

```bash
alembic upgrade head
```

Run at least one API instance and one ARQ worker:

```bash
omega serve
arq omega.jobs.WorkerSettings
```

For Kubernetes, create the `omega-runtime` Secret through External Secrets/Vault/SOPS integration,
then deploy API and worker resources.
