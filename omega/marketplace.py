from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from fastapi import HTTPException

from .db import session_scope
from .models import (
    MarketplaceListing, MarketplaceLedger, PrivateSkillVersion, PrivateSkillGrant,
    Publisher, Wallet, WalletLedger
)
from .audit import record_audit

def create_listing(
    tenant_id: str,
    actor_key_id: str,
    skill_version_id: str,
    price_credits: int,
    publisher_share_bps: int = 8000,
) -> dict:
    if price_credits <= 0:
        raise HTTPException(400, "price_credits must be positive")
    if publisher_share_bps < 0 or publisher_share_bps > 10000:
        raise HTTPException(400, "publisher_share_bps must be between 0 and 10000")
    with session_scope() as db:
        row = db.execute(
            select(PrivateSkillVersion, Publisher)
            .join(Publisher, Publisher.id == PrivateSkillVersion.publisher_id)
            .where(
                PrivateSkillVersion.id == skill_version_id,
                Publisher.tenant_id == tenant_id,
                PrivateSkillVersion.status == "active",
            )
        ).first()
        if not row:
            raise HTTPException(404, "Private skill version not found")
        listing = MarketplaceListing(
            skill_version_id=skill_version_id,
            price_credits=price_credits,
            publisher_share_bps=publisher_share_bps,
            status="active",
        )
        db.add(listing)
        db.flush()
        listing_id = listing.id
    record_audit(
        tenant_id, "api_key", actor_key_id, "marketplace.listing_created", "marketplace_listing", listing_id,
        {"price_credits": price_credits, "publisher_share_bps": publisher_share_bps},
    )
    return {"id": listing_id, "skill_version_id": skill_version_id, "price_credits": price_credits, "publisher_share_bps": publisher_share_bps}

def list_listings() -> list[dict]:
    with session_scope() as db:
        rows = db.execute(
            select(MarketplaceListing, PrivateSkillVersion, Publisher)
            .join(PrivateSkillVersion, PrivateSkillVersion.id == MarketplaceListing.skill_version_id)
            .join(Publisher, Publisher.id == PrivateSkillVersion.publisher_id)
            .where(MarketplaceListing.status == "active", PrivateSkillVersion.status == "active")
            .order_by(MarketplaceListing.created_at.desc())
        ).all()
        return [{
            "id": listing.id,
            "skill_version_id": skill.id,
            "skill_id": skill.skill_id,
            "version": skill.version,
            "publisher": publisher.name,
            "price_credits": listing.price_credits,
            "publisher_share_bps": listing.publisher_share_bps,
        } for listing, skill, publisher in rows]

def purchase_listing(
    tenant_id: str,
    actor_key_id: str,
    listing_id: str,
    idempotency_key: str,
) -> dict:
    if not idempotency_key or len(idempotency_key) > 200:
        raise HTTPException(400, "Valid Idempotency-Key required")

    with session_scope() as db:
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:k))"),
            {"k": f"marketplace:{tenant_id}:{idempotency_key}"},
        )
        existing = db.execute(
            select(MarketplaceLedger).where(
                MarketplaceLedger.buyer_tenant_id == tenant_id,
                MarketplaceLedger.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        if existing:
            return {"purchase_id": existing.id, "status": existing.status, "replayed": True}

        row = db.execute(
            select(MarketplaceListing, PrivateSkillVersion, Publisher)
            .join(PrivateSkillVersion, PrivateSkillVersion.id == MarketplaceListing.skill_version_id)
            .join(Publisher, Publisher.id == PrivateSkillVersion.publisher_id)
            .where(
                MarketplaceListing.id == listing_id,
                MarketplaceListing.status == "active",
                PrivateSkillVersion.status == "active",
            )
        ).first()
        if not row:
            raise HTTPException(404, "Marketplace listing not found")
        listing, skill, publisher = row
        if publisher.tenant_id == tenant_id:
            raise HTTPException(409, "Publisher cannot purchase own listing")

        wallet = db.execute(
            select(Wallet).where(Wallet.tenant_id == tenant_id).with_for_update()
        ).scalar_one_or_none()
        if not wallet:
            raise HTTPException(404, "Wallet not found")
        if wallet.available_credits < listing.price_credits:
            raise HTTPException(402, detail={"code": "INSUFFICIENT_CREDITS", "required": listing.price_credits, "available": wallet.available_credits})

        publisher_credits = (listing.price_credits * listing.publisher_share_bps) // 10000
        platform_credits = listing.price_credits - publisher_credits
        wallet.available_credits -= listing.price_credits
        wallet.version += 1

        purchase = MarketplaceLedger(
            buyer_tenant_id=tenant_id,
            publisher_id=publisher.id,
            listing_id=listing.id,
            idempotency_key=idempotency_key,
            gross_credits=listing.price_credits,
            publisher_credits=publisher_credits,
            platform_credits=platform_credits,
            status="settled",
        )
        db.add(purchase)
        db.flush()

        db.add(WalletLedger(
            tenant_id=tenant_id,
            kind="marketplace_charge",
            amount=-listing.price_credits,
            reference_type="marketplace_purchase",
            reference_id=purchase.id,
            metadata_json={"listing_id": listing.id, "publisher_id": publisher.id},
        ))
        db.execute(
            pg_insert(PrivateSkillGrant)
            .values(
                tenant_id=tenant_id,
                skill_version_id=skill.id,
                source="marketplace",
            )
            .on_conflict_do_nothing(index_elements=["tenant_id", "skill_version_id"])
        )
        purchase_id = purchase.id

    record_audit(
        tenant_id, "api_key", actor_key_id, "marketplace.purchased", "marketplace_purchase", purchase_id,
        {"listing_id": listing_id},
    )
    return {
        "purchase_id": purchase_id,
        "status": "settled",
        "gross_credits": listing.price_credits,
        "publisher_credits": publisher_credits,
        "platform_credits": platform_credits,
        "replayed": False,
    }

def publisher_earnings(tenant_id: str) -> dict:
    with session_scope() as db:
        publisher = db.execute(select(Publisher).where(Publisher.tenant_id == tenant_id)).scalar_one_or_none()
        if not publisher:
            return {"publisher_credits": 0, "sales": 0}
        rows = db.execute(
            select(MarketplaceLedger).where(
                MarketplaceLedger.publisher_id == publisher.id,
                MarketplaceLedger.status == "settled",
            )
        ).scalars().all()
        return {
            "publisher_credits": sum(int(row.publisher_credits) for row in rows),
            "sales": len(rows),
        }
