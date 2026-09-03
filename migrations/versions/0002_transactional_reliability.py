from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("runs", sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.false()))

    op.create_check_constraint("ck_wallet_available_nonnegative", "wallets", "available_credits >= 0")
    op.create_check_constraint("ck_wallet_reserved_nonnegative", "wallets", "reserved_credits >= 0")
    op.create_check_constraint("ck_reservation_amount_positive", "reservations", "amount > 0")
    op.create_check_constraint("ck_reservation_settled_nonnegative", "reservations", "settled_amount >= 0")
    op.create_check_constraint("ck_ledger_amount_nonzero", "wallet_ledger", "amount <> 0")

    op.execute("""
    DO $$
    BEGIN
      IF EXISTS (
        SELECT 1
        FROM wallet_ledger
        GROUP BY tenant_id, kind, reference_type, reference_id
        HAVING COUNT(*) > 1
      ) THEN
        RAISE EXCEPTION 'wallet_ledger contains duplicate references; reconcile before applying 0002';
      END IF;
    END $$;
    """)
    op.create_unique_constraint(
        "uq_ledger_reference",
        "wallet_ledger",
        ["tenant_id", "kind", "reference_type", "reference_id"],
    )

    op.create_table(
        "outbox_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("aggregate_type", sa.String(40), nullable=False),
        sa.Column("aggregate_id", sa.String(36), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("attempts", sa.BigInteger(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "aggregate_type", "aggregate_id", "event_type",
            name="uq_outbox_aggregate_event",
        ),
    )
    op.create_index("ix_outbox_events_aggregate_id", "outbox_events", ["aggregate_id"])
    op.create_index("ix_outbox_events_available_at", "outbox_events", ["available_at"])
    op.create_index(
        "ix_outbox_pending_dispatch",
        "outbox_events",
        ["status", "available_at"],
    )

    op.create_table(
        "skill_executions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("skill_id", sa.String(120), nullable=False),
        sa.Column("sequence_no", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("provider_response_id", sa.String(150), nullable=True),
        sa.Column("input_tokens", sa.BigInteger(), nullable=False),
        sa.Column("output_tokens", sa.BigInteger(), nullable=False),
        sa.Column("charged_credits", sa.BigInteger(), nullable=False),
        sa.Column("output_json", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("run_id", "sequence_no", name="uq_skill_execution_run_sequence"),
        sa.UniqueConstraint("run_id", "skill_id", name="uq_skill_execution_run_skill"),
    )
    op.create_index("ix_skill_executions_run_id", "skill_executions", ["run_id"])

def downgrade():
    op.drop_table("skill_executions")
    op.drop_table("outbox_events")
    op.drop_constraint("uq_ledger_reference", "wallet_ledger", type_="unique")
    op.drop_constraint("ck_ledger_amount_nonzero", "wallet_ledger", type_="check")
    op.drop_constraint("ck_reservation_settled_nonnegative", "reservations", type_="check")
    op.drop_constraint("ck_reservation_amount_positive", "reservations", type_="check")
    op.drop_constraint("ck_wallet_reserved_nonnegative", "wallets", type_="check")
    op.drop_constraint("ck_wallet_available_nonnegative", "wallets", type_="check")
    op.drop_column("runs", "cancel_requested")
