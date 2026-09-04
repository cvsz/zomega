from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("api_keys", sa.Column("key_prefix", sa.String(length=24), nullable=True))
    op.create_index("ix_api_keys_key_prefix", "api_keys", ["key_prefix"], unique=True)
    op.alter_column(
        "api_keys",
        "key_digest",
        existing_type=sa.String(length=128),
        type_=sa.String(length=255),
        existing_nullable=False,
    )

    # Current BLAKE2b digests and all older deterministic digests cannot be converted to
    # Argon2id because raw API-key secrets are intentionally never stored.
    # Deactivate them fail-closed and require explicit rotation.
    op.execute("""
        UPDATE api_keys
        SET active = FALSE
        WHERE active = TRUE
          AND key_prefix IS NULL
    """)

def downgrade():
    op.drop_index("ix_api_keys_key_prefix", table_name="api_keys")
    op.drop_column("api_keys", "key_prefix")
    op.alter_column(
        "api_keys",
        "key_digest",
        existing_type=sa.String(length=255),
        type_=sa.String(length=128),
        existing_nullable=False,
    )
