from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "tenant_quotas",
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("monthly_credit_cap", sa.BigInteger(), nullable=False, server_default="100000"),
        sa.Column("max_api_keys", sa.BigInteger(), nullable=False, server_default="20"),
        sa.Column("max_concurrent_runs", sa.BigInteger(), nullable=False, server_default="10"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("monthly_credit_cap > 0", name="ck_quota_monthly_credit_cap_positive"),
        sa.CheckConstraint("max_api_keys > 0", name="ck_quota_max_api_keys_positive"),
        sa.CheckConstraint("max_concurrent_runs > 0", name="ck_quota_max_concurrent_runs_positive"),
    )
    op.create_table(
        "subscription_states",
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("provider", sa.String(30), nullable=False, server_default="stripe"),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("plan", sa.String(40), nullable=False),
        sa.Column("provider_subscription_id", sa.String(150), nullable=True, unique=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "tenant_usage_monthly",
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("period", sa.String(7), primary_key=True),
        sa.Column("runs", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("charged_credits", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("runs >= 0", name="ck_usage_runs_nonnegative"),
        sa.CheckConstraint("charged_credits >= 0", name="ck_usage_charged_nonnegative"),
        sa.CheckConstraint("input_tokens >= 0", name="ck_usage_input_tokens_nonnegative"),
        sa.CheckConstraint("output_tokens >= 0", name="ck_usage_output_tokens_nonnegative"),
    )
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "name", name="uq_org_tenant_name"),
    )
    op.create_index("ix_organizations_tenant_id", "organizations", ["tenant_id"])
    op.create_table(
        "organization_members",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "subject", name="uq_org_member_subject"),
        sa.CheckConstraint("role IN ('owner','admin','developer','viewer','billing')", name="ck_org_member_role"),
    )
    op.create_index("ix_organization_members_organization_id", "organization_members", ["organization_id"])
    op.create_table(
        "service_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("api_key_id", sa.String(36), sa.ForeignKey("api_keys.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "name", name="uq_service_account_tenant_name"),
        sa.CheckConstraint("status IN ('active','disabled')", name="ck_service_account_status"),
    )
    op.create_index("ix_service_accounts_tenant_id", "service_accounts", ["tenant_id"])
    op.create_index("ix_service_accounts_organization_id", "service_accounts", ["organization_id"])
    op.create_table(
        "private_skills",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("manifest_json", sa.JSON(), nullable=False),
        sa.Column("manifest_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "slug", "version", name="uq_private_skill_tenant_slug_version"),
        sa.CheckConstraint("status IN ('active','disabled','revoked')", name="ck_private_skill_status"),
    )
    op.create_index("ix_private_skills_tenant_id", "private_skills", ["tenant_id"])
    op.create_table(
        "marketplace_listings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("publisher_tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("private_skill_id", sa.String(36), sa.ForeignKey("private_skills.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("price_credits", sa.BigInteger(), nullable=False),
        sa.Column("revenue_share_bps", sa.BigInteger(), nullable=False, server_default="8000"),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("price_credits > 0", name="ck_listing_price_positive"),
        sa.CheckConstraint("revenue_share_bps BETWEEN 0 AND 10000", name="ck_listing_revenue_share_bps"),
        sa.CheckConstraint("status IN ('draft','active','suspended')", name="ck_listing_status"),
    )
    op.create_index("ix_marketplace_listings_publisher_tenant_id", "marketplace_listings", ["publisher_tenant_id"])
    op.create_table(
        "marketplace_ledger",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("amount_credits", sa.BigInteger(), nullable=False),
        sa.Column("reference_type", sa.String(40), nullable=False),
        sa.Column("reference_id", sa.String(120), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "kind", "reference_type", "reference_id", name="uq_marketplace_ledger_reference"),
        sa.CheckConstraint("amount_credits <> 0", name="ck_marketplace_ledger_nonzero"),
    )
    op.create_index("ix_marketplace_ledger_tenant_id", "marketplace_ledger", ["tenant_id"])

    op.execute("""
        INSERT INTO tenant_quotas (tenant_id, monthly_credit_cap, max_api_keys, max_concurrent_runs)
        SELECT id, 100000, 20, 10 FROM tenants
        ON CONFLICT (tenant_id) DO NOTHING
    """)
    op.execute("""
        INSERT INTO subscription_states (tenant_id, provider, status, plan)
        SELECT id, 'stripe', 'active', plan FROM tenants
        ON CONFLICT (tenant_id) DO NOTHING
    """)

def downgrade():
    op.drop_table("marketplace_ledger")
    op.drop_table("marketplace_listings")
    op.drop_table("private_skills")
    op.drop_table("service_accounts")
    op.drop_table("organization_members")
    op.drop_table("organizations")
    op.drop_table("tenant_usage_monthly")
    op.drop_table("subscription_states")
    op.drop_table("tenant_quotas")
