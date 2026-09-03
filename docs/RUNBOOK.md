# Runbook — OMEGA 2.1

## Redis unavailable during run creation

Expected state: `PENDING_DISPATCH`.

1. Do not create another run with a different idempotency key.
2. Restore Redis.
3. Confirm the outbox dispatcher moves the run to `QUEUED`.
4. Verify exactly one reservation exists.

## Ambiguous provider state

OMEGA sets `BLOCKED / AMBIGUOUS_PROVIDER_STATE` and refuses automatic provider re-execution.

1. Inspect the run evidence and `skill_executions`.
2. Check the provider dashboard/logs for the attempted response.
3. If no billable completion occurred:
   `omega reconcile-run --run-id <id> --action refund`
4. If billable work occurred, determine the defensible charge:
   `omega reconcile-run --run-id <id> --action settle --charge <credits>`
5. Record incident evidence and root cause.

## Payment mismatch

1. Freeze the affected tenant if money integrity is uncertain.
2. Run `omega reconcile-wallet --tenant-id <id>`.
3. Compare Stripe event ID, `payment_events`, wallet ledger, and wallet balance.
4. Never edit wallet columns directly.
5. Correct money only through an audited reconciliation procedure.

## Duplicate Stripe webhook

Expected behavior: HTTP success with `duplicate=true`; no additional credit ledger entry.

## Expired reservation

The reservation reaper refunds stale `PENDING_DISPATCH`, `QUEUED`, failed, or cancelled runs.
A `BLOCKED` ambiguous provider state requires operator reconciliation and is not auto-refunded.

## Secret compromise

1. Revoke the exposed credential at the provider.
2. Rotate the secret.
3. Update the production secret manager.
4. Roll API/worker pods.
5. Verify readiness and provider connectivity.
6. Review logs for misuse without exposing the secret value.
