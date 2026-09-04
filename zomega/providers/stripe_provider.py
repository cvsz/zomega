import stripe
from fastapi import HTTPException
from ..config import settings

stripe.api_key = settings.stripe_secret_key

def credit_packages() -> dict[str, dict]:
    return {
        "credits_1000": {"credits": 1000, "price_id": settings.stripe_price_credits_1000},
        "credits_5000": {"credits": 5000, "price_id": settings.stripe_price_credits_5000},
        "credits_20000": {"credits": 20000, "price_id": settings.stripe_price_credits_20000},
    }

def public_credit_packages() -> list[dict]:
    return [{"id": k, "credits": v["credits"]} for k, v in credit_packages().items()]

def create_checkout(tenant_id: str, package_id: str) -> dict:
    package = credit_packages().get(package_id)
    if not package:
        raise HTTPException(404, "Unknown credit package")
    if not package["price_id"] or package["price_id"].startswith("price_REPLACE_ME"):
        raise HTTPException(503, "Stripe credit package is not configured")

    session = stripe.checkout.Session.create(
        mode="payment",
        success_url=f"{settings.zomega_public_url}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.zomega_public_url}/billing/cancel",
        client_reference_id=tenant_id,
        metadata={
            "tenant_id": tenant_id,
            "package_id": package_id,
            "credits": str(package["credits"]),
        },
        line_items=[{"quantity": 1, "price": package["price_id"]}],
    )
    return {
        "id": session.id,
        "url": session.url,
        "package_id": package_id,
        "credits": package["credits"],
    }

def construct_event(payload: bytes, signature: str):
    return stripe.Webhook.construct_event(
        payload=payload,
        sig_header=signature,
        secret=settings.stripe_webhook_secret,
    )
