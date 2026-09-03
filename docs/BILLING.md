# Billing Guarantees — OMEGA 2.1

## Invariants

- A billable run cannot dispatch until its wallet reservation commits.
- Wallet mutations use PostgreSQL row locks.
- `available_credits >= 0` and `reserved_credits >= 0` are database constraints.
- Every reserve, charge, refund, and credit has a ledger record.
- Ledger reference uniqueness prevents duplicate financial postings.
- Verified Stripe event insertion and wallet credit occur in one transaction.
- Duplicate Stripe events cannot credit twice.
- The sum of available + reserved credits must equal credit minus charge ledger totals.
- Open reservation totals must equal `wallet.reserved_credits`.

## Checkout integrity

Clients submit a package identifier, not a price or arbitrary credit amount. The server maps:

- `credits_1000`
- `credits_5000`
- `credits_20000`

to operator-configured Stripe Price IDs. Webhook fulfillment validates the signed package metadata
against the server catalog before granting credits.

## Execution budgets

Skill calls reserve their declared maximum. Agent calls reserve the lower of the workflow maximum
and the caller's `max_spend_credits`.

The worker checks the next skill's required reservation before execution. Insufficient remaining
budget ends the run as `PARTIAL / BUDGET_EXHAUSTED`; it is not an execution failure.

## Reconciliation

Use:

```bash
omega reconcile-wallet --tenant-id <tenant-id>
```

A failed reconciliation is an incident: freeze automated financial mutations for the affected
tenant until ledger, reservations, and payment events are reviewed.

Ambiguous provider states are deliberately not auto-refunded because an upstream billable request
may already have completed. Resolve explicitly with `omega reconcile-run`.
