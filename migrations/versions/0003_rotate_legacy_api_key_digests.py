from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

def upgrade():
    # Legacy API-key digests were 64 hex chars (HMAC-SHA256). Raw keys are never stored,
    # so they cannot be rehashed safely. Fail closed and require explicit operator rotation.
    op.execute("""
        UPDATE api_keys
        SET active = FALSE
        WHERE active = TRUE
          AND length(key_digest) = 64
    """)

def downgrade():
    # Deliberately do not reactivate legacy credentials automatically.
    pass
