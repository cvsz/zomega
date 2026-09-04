from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "tenant_controls",
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("monthly_credit_limit", sa.BigInteger(), nullable=True),
        sa.Column("monthly_run_limit", sa.BigInteger(), nullable=True),
        sa.Column("allowed_agents", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("allowed_skills", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("audit_retention_days", sa.BigInteger(), nullable=False, server_default="365"),
        sa.Column("version", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("monthly_credit_limit IS NULL OR monthly_credit_limit > 0", name="ck_control_credit_limit_positive"),
        sa.CheckConstraint("monthly_run_limit IS NULL OR monthly_run_limit > 0", name="ck_control_run_limit_positive"),
        sa.CheckConstraint("audit_retention_days >= 30", name="ck_control_audit_retention_min"),
    )
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("provider_subscription_id", sa.String(150), nullable=True, unique=True),
        sa.Column("plan", sa.String(40), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_subscriptions_tenant_id", "subscriptions", ["tenant_id"])

    op.create_table(
        "publishers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("ed25519_public_key_pem", sa.String(4096), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_publishers_tenant_id", "publishers", ["tenant_id"])

    op.create_table(
        "private_skill_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("publisher_id", sa.String(36), sa.ForeignKey("publishers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("skill_id", sa.String(120), nullable=False),
        sa.Column("version", sa.String(80), nullable=False),
        sa.Column("manifest_json", sa.JSON(), nullable=False),
        sa.Column("manifest_sha256", sa.String(64), nullable=False),
        sa.Column("signature_b64", sa.String(512), nullable=False),
        sa.Column("publisher_public_key_pem", sa.String(4096), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("publisher_id", "skill_id", "version", name="uq_private_skill_publisher_version"),
    )
    op.create_index("ix_private_skill_versions_publisher_id", "private_skill_versions", ["publisher_id"])

    op.create_table(
        "private_skill_grants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("skill_version_id", sa.String(36), sa.ForeignKey("private_skill_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "skill_version_id", name="uq_private_skill_grant"),
    )
    op.create_index("ix_private_skill_grants_tenant_id", "private_skill_grants", ["tenant_id"])
    op.create_index("ix_private_skill_grants_skill_version_id", "private_skill_grants", ["skill_version_id"])

    op.create_table(
        "marketplace_listings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("skill_version_id", sa.String(36), sa.ForeignKey("private_skill_versions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("price_credits", sa.BigInteger(), nullable=False),
        sa.Column("publisher_share_bps", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("price_credits > 0", name="ck_marketplace_price_positive"),
        sa.CheckConstraint("publisher_share_bps >= 0 AND publisher_share_bps <= 10000", name="ck_marketplace_share_bps"),
    )
    op.create_index("ix_marketplace_listings_skill_version_id", "marketplace_listings", ["skill_version_id"])

    op.create_table(
        "marketplace_ledger",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("buyer_tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("publisher_id", sa.String(36), sa.ForeignKey("publishers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("listing_id", sa.String(36), sa.ForeignKey("marketplace_listings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("gross_credits", sa.BigInteger(), nullable=False),
        sa.Column("publisher_credits", sa.BigInteger(), nullable=False),
        sa.Column("platform_credits", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("buyer_tenant_id", "idempotency_key", name="uq_marketplace_buyer_idempotency"),
        sa.CheckConstraint("gross_credits > 0", name="ck_marketplace_gross_positive"),
        sa.CheckConstraint("publisher_credits >= 0", name="ck_marketplace_publisher_nonnegative"),
        sa.CheckConstraint("platform_credits >= 0", name="ck_marketplace_platform_nonnegative"),
    )
    op.create_index("ix_marketplace_ledger_buyer_tenant_id", "marketplace_ledger", ["buyer_tenant_id"])
    op.create_index("ix_marketplace_ledger_publisher_id", "marketplace_ledger", ["publisher_id"])
    op.create_index("ix_marketplace_ledger_listing_id", "marketplace_ledger", ["listing_id"])

    op.create_index("ix_runs_tenant_created", "runs", ["tenant_id", "created_at"])

def downgrade():
    op.drop_index("ix_runs_tenant_created", table_name="runs")
    op.drop_table("marketplace_ledger")
    op.drop_table("marketplace_listings")
    op.drop_table("private_skill_grants")
    op.drop_table("private_skill_versions")
    op.drop_table("publishers")
    op.drop_table("subscriptions")
    op.drop_table("tenant_controls")
