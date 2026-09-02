# Billing Guarantees

- Credit purchase is server-authoritative from Stripe webhook events.
- Stripe event IDs are unique in `payment_events`.
- Wallet updates are transactional.
- Every reserve/charge/refund/credit produces a ledger entry.
- A run receives a maximum spend reservation before queueing.
- A failed run refunds any still-open reservation.
- A successful run settles its charge and refunds the unused remainder.
- Idempotency keys prevent duplicate run creation for the same tenant and request.
