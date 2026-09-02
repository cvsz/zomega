# Runbook

## Failed execution
1. Check run record.
2. Check evidence.
3. Confirm reservation was refunded or settled.
4. Fix root cause.
5. Retry using a new idempotency key.

## Payment mismatch
1. Freeze affected tenant if necessary.
2. Compare provider event IDs with payment_events.
3. Reconcile wallet ledger.
4. Never mutate balances without an audit entry.

## Secret compromise
1. Revoke.
2. Rotate.
3. Update runtime injection.
4. Restart consumers.
5. Verify.
