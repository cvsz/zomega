# Billing Guarantees — OMEGA 3.0

## Financial invariants

- A billable run cannot dispatch until its wallet reservation commits.
- Wallet mutations use PostgreSQL row locks.
- `available_credits >= 0` and `reserved_credits >= 0` are database constraints.
- Every financial movement has a unique ledger reference.
- Verified Stripe event insertion and wallet credit occur in one transaction.
- Duplicate Stripe events cannot credit twice.
- Marketplace purchases are idempotent by buyer tenant + idempotency key.
- Buyer marketplace debit, publisher earning, revenue-share accounting, and entitlement grant commit atomically.
- Open reservation totals must equal `wallet.reserved_credits`.
- Wallet reconciliation derives net value from Stripe credits, run charges, marketplace charges, and marketplace earnings.

## Checkout integrity

Clients submit a package identifier rather than an arbitrary price or credit amount. OMEGA maps
packages to operator-configured Stripe Price IDs and grants credits only after signed paid webhook
verification.

## Execution budgets and tenant limits

Run reservation is bounded by Skill/Agent pricing and caller `max_spend_credits`.

OMEGA 3.0 additionally enforces tenant-month:

- run limits
- credit/spend limits
- Agent allowlists
- Skill allowlists

The credit cap includes settled execution charges, marketplace purchases, open reservations, and the
candidate reservation.

## Marketplace revenue share

A marketplace purchase locks buyer and publisher wallet rows in deterministic tenant-ID order.

```text
buyer - gross purchase
publisher + publisher share
platform accounting = gross - publisher share
```

Publisher earnings become usable OMEGA credits immediately after the transaction commits.

## Reconciliation

```bash
omega reconcile-wallet --tenant-id <tenant-id>
```

A failed reconciliation is a financial incident. Freeze affected automated financial mutations,
inspect wallet ledger/reservations/payment events/marketplace ledger, and correct state only through
an audited procedure.

Ambiguous upstream AI provider states are not automatically refunded because billable work may have
completed externally.
