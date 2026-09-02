import stripe
from ..config import settings

stripe.api_key = settings.stripe_secret_key

def create_checkout(tenant_id: str, credits: int) -> dict:
    amount = credits * settings.stripe_credit_unit_amount
    session = stripe.checkout.Session.create(
        mode="payment",
        success_url=f"{settings.omega_public_url}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.omega_public_url}/billing/cancel",
        client_reference_id=tenant_id,
        metadata={"tenant_id": tenant_id, "credits": str(credits)},
        line_items=[{
            "quantity": 1,
            "price_data": {
                "currency": settings.stripe_currency,
                "unit_amount": amount,
                "product_data": {"name": f"OMEGA {credits} credits"},
            },
        }],
    )
    return {"id": session.id, "url": session.url, "credits": credits}

def construct_event(payload: bytes, signature: str):
    return stripe.Webhook.construct_event(
        payload=payload,
        sig_header=signature,
        secret=settings.stripe_webhook_secret,
    )
