from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

NEW_SCOPES = [
    "dashboard:read",
    "subscription:read",
    "registry:read",
    "registry:write",
    "marketplace:read",
    "marketplace:write",
]

def upgrade():
    scopes_sql = ", ".join(f"'{scope}'" for scope in NEW_SCOPES)
    op.execute(f"""
        UPDATE api_keys AS k
        SET scopes = (
            SELECT json_agg(scope ORDER BY scope)
            FROM (
                SELECT DISTINCT jsonb_array_elements_text(k.scopes::jsonb) AS scope
                UNION
                SELECT unnest(ARRAY[{scopes_sql}]::text[]) AS scope
            ) merged
        )
        WHERE k.active = TRUE
          AND k.name IN ('primary', 'primary-rotated')
    """)

def downgrade():
    pass
