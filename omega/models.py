from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import (
    String, BigInteger, Boolean, DateTime, ForeignKey,
    UniqueConstraint, JSON, Index, CheckConstraint
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func

def uid() -> str:
    return str(uuid.uuid4())

class Base(DeclarativeBase):
    pass

class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    plan: Mapped[str] = mapped_column(String(40), nullable=False, default="pro")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    stripe_customer_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class ApiKey(Base):
    __tablename__ = "api_keys"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    key_type: Mapped[str] = mapped_column(String(30), nullable=False, default="api_key")
    role: Mapped[str | None] = mapped_column(String(40))
    key_prefix: Mapped[str | None] = mapped_column(String(24), nullable=True, unique=True, index=True)
    key_digest: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    scopes: Mapped[list] = mapped_column(JSON, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Wallet(Base):
    __tablename__ = "wallets"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    available_credits: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    reserved_credits: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        CheckConstraint("available_credits >= 0", name="ck_wallet_available_nonnegative"),
        CheckConstraint("reserved_credits >= 0", name="ck_wallet_reserved_nonnegative"),
    )

class WalletLedger(Base):
    __tablename__ = "wallet_ledger"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reference_type: Mapped[str] = mapped_column(String(40), nullable=False)
    reference_id: Mapped[str] = mapped_column(String(120), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        Index("ix_ledger_tenant_created", "tenant_id", "created_at"),
        UniqueConstraint("tenant_id", "kind", "reference_type", "reference_id", name="uq_ledger_reference"),
        CheckConstraint("amount <> 0", name="ck_ledger_amount_nonzero"),
    )

class Run(Base):
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    agent_id: Mapped[str] = mapped_column(String(120), nullable=False)
    skill_id: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")
    input_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    result_json: Mapped[dict | None] = mapped_column(JSON)
    charged_credits: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    max_spend_credits: Mapped[int] = mapped_column(BigInteger, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80))
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class Reservation(Base):
    __tablename__ = "reservations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), unique=True)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    settled_amount: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="reserved")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_reservation_amount_positive"),
        CheckConstraint("settled_amount >= 0", name="ck_reservation_settled_nonnegative"),
    )

class UsageEvent(Base):
    __tablename__ = "usage_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    metric: Mapped[str] = mapped_column(String(50), nullable=False)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class PaymentEvent(Base):
    __tablename__ = "payment_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    tenant_id: Mapped[str | None] = mapped_column(ForeignKey("tenants.id", ondelete="SET NULL"), index=True)
    credits: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("tenant_id", "key", name="uq_idempotency_tenant_key"),)

class Evidence(Base):
    __tablename__ = "evidence"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    aggregate_type: Mapped[str] = mapped_column(String(40), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint("aggregate_type", "aggregate_id", "event_type", name="uq_outbox_aggregate_event"),
    )

class SkillExecution(Base):
    __tablename__ = "skill_executions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    skill_id: Mapped[str] = mapped_column(String(120), nullable=False)
    sequence_no: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")
    provider_response_id: Mapped[str | None] = mapped_column(String(150))
    input_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    charged_credits: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    output_json: Mapped[dict | None] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("run_id", "sequence_no", name="uq_skill_execution_run_sequence"),
        UniqueConstraint("run_id", "skill_id", name="uq_skill_execution_run_skill"),
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    actor_type: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(120))
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        Index("ix_audit_tenant_created", "tenant_id", "created_at"),
    )


class TenantControl(Base):
    __tablename__ = "tenant_controls"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    monthly_credit_limit: Mapped[int | None] = mapped_column(BigInteger)
    monthly_run_limit: Mapped[int | None] = mapped_column(BigInteger)
    allowed_agents: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    allowed_skills: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    audit_retention_days: Mapped[int] = mapped_column(BigInteger, nullable=False, default=365)
    version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        CheckConstraint("monthly_credit_limit IS NULL OR monthly_credit_limit > 0", name="ck_control_credit_limit_positive"),
        CheckConstraint("monthly_run_limit IS NULL OR monthly_run_limit > 0", name="ck_control_run_limit_positive"),
        CheckConstraint("audit_retention_days >= 30", name="ck_control_audit_retention_min"),
    )

class Subscription(Base):
    __tablename__ = "subscriptions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(30), nullable=False, default="manual")
    provider_subscription_id: Mapped[str | None] = mapped_column(String(150), unique=True)
    plan: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Publisher(Base):
    __tablename__ = "publishers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    ed25519_public_key_pem: Mapped[str] = mapped_column(String(4096), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class PrivateSkillVersion(Base):
    __tablename__ = "private_skill_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    publisher_id: Mapped[str] = mapped_column(ForeignKey("publishers.id", ondelete="CASCADE"), index=True)
    skill_id: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    manifest_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    signature_b64: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint("publisher_id", "skill_id", "version", name="uq_private_skill_publisher_version"),
    )

class PrivateSkillGrant(Base):
    __tablename__ = "private_skill_grants"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    skill_version_id: Mapped[str] = mapped_column(ForeignKey("private_skill_versions.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint("tenant_id", "skill_version_id", name="uq_private_skill_grant"),
    )

class MarketplaceListing(Base):
    __tablename__ = "marketplace_listings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    skill_version_id: Mapped[str] = mapped_column(ForeignKey("private_skill_versions.id", ondelete="CASCADE"), unique=True, index=True)
    price_credits: Mapped[int] = mapped_column(BigInteger, nullable=False)
    publisher_share_bps: Mapped[int] = mapped_column(BigInteger, nullable=False, default=8000)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        CheckConstraint("price_credits > 0", name="ck_marketplace_price_positive"),
        CheckConstraint("publisher_share_bps >= 0 AND publisher_share_bps <= 10000", name="ck_marketplace_share_bps"),
    )

class MarketplaceLedger(Base):
    __tablename__ = "marketplace_ledger"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    buyer_tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    publisher_id: Mapped[str] = mapped_column(ForeignKey("publishers.id", ondelete="CASCADE"), index=True)
    listing_id: Mapped[str] = mapped_column(ForeignKey("marketplace_listings.id", ondelete="CASCADE"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    gross_credits: Mapped[int] = mapped_column(BigInteger, nullable=False)
    publisher_credits: Mapped[int] = mapped_column(BigInteger, nullable=False)
    platform_credits: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="settled")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint("buyer_tenant_id", "idempotency_key", name="uq_marketplace_buyer_idempotency"),
        CheckConstraint("gross_credits > 0", name="ck_marketplace_gross_positive"),
        CheckConstraint("publisher_credits >= 0", name="ck_marketplace_publisher_nonnegative"),
        CheckConstraint("platform_credits >= 0", name="ck_marketplace_platform_nonnegative"),
    )
