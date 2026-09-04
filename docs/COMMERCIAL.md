# Commercial Control Plane

zomega 3.0 enforces commercial limits before a billable run is admitted.

## Tenant controls

Each tenant can have:

- monthly credit limit
- monthly run limit
- Agent allowlist
- Skill allowlist
- audit retention period

Admission uses a PostgreSQL advisory transaction lock scoped to tenant and UTC month. This prevents
multiple API replicas from independently passing a quota check and oversubscribing the same limit.

The projected monthly credit spend includes settled run charges, marketplace purchases, currently
open reservations, and the candidate reservation.

## Subscription state

Platform administration can set plan and subscription status through admin-token protected routes.
Only `active` and `trialing` subscriptions leave the tenant active for API authentication.

## Dashboard

`GET /v1/dashboard` returns wallet state, monthly runs/charges/tokens/audit counts, current controls,
and subscription state. It is designed as the backend contract for a future browser dashboard.

## Service-account roles

Role presets are implemented as maximum scope sets. A service account may never request a scope that
is outside its selected role.
