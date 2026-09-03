from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("plan", sa.String(40), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("stripe_customer_id", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("stripe_customer_id", name="uq_tenants_stripe_customer_id"),
    )
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("key_digest", sa.String(128), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("key_digest", name="uq_api_keys_key_digest"),
    )
    op.create_index("ix_api_keys_tenant_id", "api_keys", ["tenant_id"])
    op.create_table(
        "wallets",
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("available_credits", sa.BigInteger(), nullable=False),
        sa.Column("reserved_credits", sa.BigInteger(), nullable=False),
        sa.Column("version", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "wallet_ledger",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("reference_type", sa.String(40), nullable=False),
        sa.Column("reference_id", sa.String(120), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_wallet_ledger_tenant_id", "wallet_ledger", ["tenant_id"])
    op.create_index("ix_ledger_tenant_created", "wallet_ledger", ["tenant_id", "created_at"])
    op.create_table(
        "runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_id", sa.String(120), nullable=False),
        sa.Column("skill_id", sa.String(120), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("input_json", sa.JSON(), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("charged_credits", sa.BigInteger(), nullable=False),
        sa.Column("max_spend_credits", sa.BigInteger(), nullable=False),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_runs_tenant_id", "runs", ["tenant_id"])
    op.create_table(
        "reservations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("settled_amount", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("run_id", name="uq_reservations_run_id"),
    )
    op.create_index("ix_reservations_tenant_id", "reservations", ["tenant_id"])
    op.create_table(
        "usage_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("metric", sa.String(50), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_usage_events_run_id", "usage_events", ["run_id"])
    op.create_table(
        "payment_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("provider_event_id", sa.String(150), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True),
        sa.Column("credits", sa.BigInteger(), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("provider_event_id", name="uq_payment_events_provider_event_id"),
    )
    op.create_index("ix_payment_events_tenant_id", "payment_events", ["tenant_id"])
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "key", name="uq_idempotency_tenant_key"),
    )
    op.create_index("ix_idempotency_records_tenant_id", "idempotency_records", ["tenant_id"])
    op.create_table(
        "evidence",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_evidence_run_id", "evidence", ["run_id"])

def downgrade():
    op.drop_table("evidence")
    op.drop_table("idempotency_records")
    op.drop_table("payment_events")
    op.drop_table("usage_events")
    op.drop_table("reservations")
    op.drop_table("runs")
    op.drop_table("wallet_ledger")
    op.drop_table("wallets")
    op.drop_table("api_keys")
    op.drop_table("tenants")
