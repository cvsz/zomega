from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column(
        "api_keys",
        sa.Column("key_type", sa.String(30), nullable=False, server_default="api_key"),
    )
    op.add_column("api_keys", sa.Column("role", sa.String(40), nullable=True))

def downgrade():
    op.drop_column("api_keys", "role")
    op.drop_column("api_keys", "key_type")
