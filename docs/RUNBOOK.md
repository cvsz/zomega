# Runbook — zomega 3.0

## Redis unavailable during run creation

Expected state: `PENDING_DISPATCH`.

1. Do not create a second run with a different idempotency key.
2. Restore Redis.
3. Confirm outbox dispatch changes the run to `QUEUED`.
4. Verify exactly one open reservation exists.

## Ambiguous provider state

zomega sets `BLOCKED / AMBIGUOUS_PROVIDER_STATE` instead of automatically repeating a possibly
billable provider request.

Use:

```bash
zomega reconcile-run --run-id <id> --action refund
zomega reconcile-run --run-id <id> --action settle --charge <credits>
```

after provider evidence has been reviewed.

## Tenant quota denial

A `MONTHLY_RUN_LIMIT_EXCEEDED` or `MONTHLY_CREDIT_LIMIT_EXCEEDED` response is an admission denial,
not a worker failure.

Review:

- tenant control
- current UTC-month run count
- settled charges
- marketplace charges
- open reservations

Change limits only through the admin-token protected control route.

## Marketplace mismatch

1. Freeze marketplace mutation for the affected tenant if accounting is uncertain.
2. Reconcile buyer and publisher wallets.
3. Compare `marketplace_ledger`, `wallet_ledger`, and `private_skill_grants`.
4. Confirm exactly one purchase row for the buyer idempotency key.
5. Never edit wallet columns directly.

## Private-skill signature failure

1. Do not grant or list the version as trusted.
2. Verify canonical manifest bytes and stored SHA-256 content digest.
3. Verify against the signer public-key snapshot stored with that exact version.
4. If the publisher rotated keys, do not substitute the new profile key for historical verification.

## Payment mismatch

1. Freeze affected financial mutation if integrity is uncertain.
2. Run wallet reconciliation.
3. Compare Stripe event ID, payment event, wallet ledger, and wallet state.
4. Correct through an audited procedure only.

## Expired reservation

The reservation reaper refunds stale non-running reservations. A blocked ambiguous provider state
requires operator reconciliation.

## API/service-account compromise

1. Revoke the affected key.
2. Create a new least-privilege key or service account.
3. Review audit events for the compromised key ID.
4. Rotate `ZOMEGA_API_KEY_PEPPER` only with a coordinated key-rotation plan because it invalidates
   existing Argon2id verification material.

## Production secret compromise

1. Revoke the provider credential.
2. Rotate it at the provider.
3. Update the external secret manager.
4. roll API/worker pods
5. verify readiness and provider connectivity
6. review logs/audit data without exposing replacement secrets

## Disaster recovery

**Restore and restore verification are disabled.** Do not use any direct shell or Makefile restore entry point. Current Main intentionally fails closed before invoking `pg_restore` or connecting to a source/target database:

- `restore.sh`
- `make restore`
- `restore-verify.sh`
- `make restore-verify`
- `.github/workflows/dr-verify.yml`

No supported production restore command is available from this repository revision. Do not set or pass production database credentials to these disabled entry points.

Production recovery remains blocked until a separately reviewed, environment-protected operator workflow has explicit authorization, source/target PostgreSQL cluster identity verification (not URL inequality alone), a dedicated isolated restore target, backup checksum/schema validation, a rollback plan, and retained evidence. Production Environment reviewers and the restore/failover procedure must be independently verified before any re-enablement.

See `docs/DISASTER_RECOVERY.md` for the current containment boundary and acceptance gates. A disposable CI drill is not production DR evidence.
