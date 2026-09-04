from fastapi import HTTPException
from sqlalchemy import func, select

from .audit import record_audit
from .db import session_scope
from .models import MarketplaceLedger, MarketplaceListing, PrivateSkill, SkillLicense, Wallet, WalletLedger

def create_listing(
    tenant_id: str,
    actor_key_id: str,
    private_skill_id: str,
    price_credits: int,
    revenue_share_bps: int = 8000,
) -> dict:
    if price_credits <= 0:
        raise HTTPException(400, "price_credits must be positive")
    if not 0 <= revenue_share_bps <= 10000:
        raise HTTPException(400, "revenue_share_bps out of range")
    with session_scope() as db:
        skill = db.execute(
            select(PrivateSkill).where(
                PrivateSkill.id == private_skill_id,
                PrivateSkill.tenant_id == tenant_id,
                PrivateSkill.status == "active",
            )
        ).scalar_one_or_none()
        if not skill:
            raise HTTPException(404, "Active private skill not found")
        listing = MarketplaceListing(
            publisher_tenant_id=tenant_id,
            private_skill_id=private_skill_id,
            price_credits=price_credits,
            revenue_share_bps=revenue_share_bps,
            status="draft",
        )
        db.add(listing)
        db.flush()
        listing_id = listing.id
    record_audit(tenant_id, "api_key", actor_key_id, "marketplace.listing_created", "marketplace_listing", listing_id, {"private_skill_id": private_skill_id, "price_credits": price_credits, "revenue_share_bps": revenue_share_bps})
    return {"id": listing_id, "status": "draft", "price_credits": price_credits, "revenue_share_bps": revenue_share_bps}

def set_listing_status(tenant_id: str, actor_key_id: str, listing_id: str, status: str) -> dict:
    if status not in {"draft", "active", "suspended"}:
        raise HTTPException(400, "Invalid listing status")
    with session_scope() as db:
        row = db.execute(
            select(MarketplaceListing)
            .where(MarketplaceListing.id == listing_id, MarketplaceListing.publisher_tenant_id == tenant_id)
            .with_for_update()
        ).scalar_one_or_none()
        if not row:
            raise HTTPException(404, "Listing not found")
        row.status = status
    record_audit(tenant_id, "api_key", actor_key_id, "marketplace.listing_status_changed", "marketplace_listing", listing_id, {"status": status})
    return {"id": listing_id, "status": status}

def list_marketplace() -> list[dict]:
    with session_scope() as db:
        rows = db.execute(
            select(MarketplaceListing, PrivateSkill)
            .join(PrivateSkill, PrivateSkill.id == MarketplaceListing.private_skill_id)
            .where(MarketplaceListing.status == "active", PrivateSkill.status == "active")
            .order_by(MarketplaceListing.created_at.desc())
        ).all()
        return [{
            "id": listing.id,
            "publisher_tenant_id": listing.publisher_tenant_id,
            "skill": {"slug": skill.slug, "version": skill.version, "manifest_hash": skill.manifest_hash},
            "price_credits": listing.price_credits,
            "revenue_share_bps": listing.revenue_share_bps,
        } for listing, skill in rows]

def record_publisher_revenue(
    publisher_tenant_id: str,
    listing_id: str,
    sale_reference_id: str,
    gross_credits: int,
    revenue_share_bps: int,
) -> int:
    publisher_credits = gross_credits * revenue_share_bps // 10000
    if publisher_credits <= 0:
        return 0
    with session_scope() as db:
        existing = db.execute(
            select(MarketplaceLedger.id).where(
                MarketplaceLedger.tenant_id == publisher_tenant_id,
                MarketplaceLedger.kind == "publisher_revenue",
                MarketplaceLedger.reference_type == "sale",
                MarketplaceLedger.reference_id == sale_reference_id,
            )
        ).scalar_one_or_none()
        if existing:
            return 0
        db.add(MarketplaceLedger(
            tenant_id=publisher_tenant_id,
            kind="publisher_revenue",
            amount_credits=publisher_credits,
            reference_type="sale",
            reference_id=sale_reference_id,
            metadata_json={"listing_id": listing_id, "gross_credits": gross_credits, "revenue_share_bps": revenue_share_bps},
        ))
    return publisher_credits

def marketplace_balance(tenant_id: str) -> dict:
    with session_scope() as db:
        balance = db.execute(
            select(func.coalesce(func.sum(MarketplaceLedger.amount_credits), 0)).where(
                MarketplaceLedger.tenant_id == tenant_id
            )
        ).scalar_one()
        rows = db.execute(
            select(MarketplaceLedger)
            .where(MarketplaceLedger.tenant_id == tenant_id)
            .order_by(MarketplaceLedger.created_at.desc())
            .limit(200)
        ).scalars().all()
        return {
            "balance_credits": int(balance),
            "ledger": [{
                "id": r.id,
                "kind": r.kind,
                "amount_credits": r.amount_credits,
                "reference_type": r.reference_type,
                "reference_id": r.reference_id,
                "metadata": r.metadata_json,
                "created_at": r.created_at,
            } for r in rows],
        }


def purchase_listing(buyer_tenant_id: str, actor_key_id: str, listing_id: str) -> dict:
    with session_scope() as db:
        listing = db.execute(
            select(MarketplaceListing)
            .where(MarketplaceListing.id == listing_id, MarketplaceListing.status == "active")
            .with_for_update()
        ).scalar_one_or_none()
        if not listing:
            raise HTTPException(404, "Active listing not found")
        if listing.publisher_tenant_id == buyer_tenant_id:
            raise HTTPException(409, "Publisher cannot purchase its own listing")

        existing = db.execute(
            select(SkillLicense).where(
                SkillLicense.tenant_id == buyer_tenant_id,
                SkillLicense.listing_id == listing_id,
            )
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(409, "Listing already licensed")

        wallet = db.execute(
            select(Wallet).where(Wallet.tenant_id == buyer_tenant_id).with_for_update()
        ).scalar_one_or_none()
        if not wallet:
            raise HTTPException(404, "Buyer wallet not found")
        if wallet.available_credits < listing.price_credits:
            raise HTTPException(
                402,
                detail={
                    "code": "INSUFFICIENT_CREDITS",
                    "required": listing.price_credits,
                    "available": wallet.available_credits,
                },
            )

        license_row = SkillLicense(
            tenant_id=buyer_tenant_id,
            listing_id=listing_id,
            purchase_price_credits=listing.price_credits,
        )
        db.add(license_row)
        db.flush()

        wallet.available_credits -= listing.price_credits
        wallet.version += 1
        db.add(WalletLedger(
            tenant_id=buyer_tenant_id,
            kind="charge",
            amount=-listing.price_credits,
            reference_type="marketplace_license",
            reference_id=license_row.id,
            metadata_json={"listing_id": listing_id},
        ))

        publisher_credits = listing.price_credits * listing.revenue_share_bps // 10000
        if publisher_credits > 0:
            db.add(MarketplaceLedger(
                tenant_id=listing.publisher_tenant_id,
                kind="publisher_revenue",
                amount_credits=publisher_credits,
                reference_type="marketplace_license",
                reference_id=license_row.id,
                metadata_json={
                    "listing_id": listing_id,
                    "buyer_tenant_id": buyer_tenant_id,
                    "gross_credits": listing.price_credits,
                    "revenue_share_bps": listing.revenue_share_bps,
                },
            ))
        license_id = license_row.id
        price = listing.price_credits
        publisher_tenant_id = listing.publisher_tenant_id

    record_audit(
        buyer_tenant_id,
        "api_key",
        actor_key_id,
        "marketplace.purchased",
        "skill_license",
        license_id,
        {"listing_id": listing_id, "price_credits": price, "publisher_tenant_id": publisher_tenant_id},
    )
    return {
        "license_id": license_id,
        "listing_id": listing_id,
        "price_credits": price,
        "publisher_tenant_id": publisher_tenant_id,
    }

def list_licenses(tenant_id: str) -> list[dict]:
    with session_scope() as db:
        rows = db.execute(
            select(SkillLicense, MarketplaceListing, PrivateSkill)
            .join(MarketplaceListing, MarketplaceListing.id == SkillLicense.listing_id)
            .join(PrivateSkill, PrivateSkill.id == MarketplaceListing.private_skill_id)
            .where(SkillLicense.tenant_id == tenant_id)
            .order_by(SkillLicense.created_at.desc())
        ).all()
        return [{
            "license_id": lic.id,
            "listing_id": listing.id,
            "purchase_price_credits": lic.purchase_price_credits,
            "skill": {
                "slug": skill.slug,
                "version": skill.version,
                "manifest_hash": skill.manifest_hash,
            },
            "created_at": lic.created_at,
        } for lic, listing, skill in rows]
