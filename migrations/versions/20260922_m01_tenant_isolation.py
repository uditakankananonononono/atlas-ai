"""Tenant-scope M01 opportunity records.

Existing pre-tenant rows are assigned to the development-compatible `local`
tenant. New IDs include tenant identity, so rescans cannot collide across
owners even though the historical primary-key shape is retained.
"""
from alembic import op
import sqlalchemy as sa

revision = "20260922_m01_tenant_isolation"
down_revision = "96ad3c0c61e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "m01_opportunities",
        sa.Column("tenant_id", sa.String(length=120), nullable=False, server_default="local"),
    )
    op.create_index("ix_m01_opportunities_tenant_id", "m01_opportunities", ["tenant_id"], unique=False)
    op.alter_column("m01_opportunities", "tenant_id", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_m01_opportunities_tenant_id", table_name="m01_opportunities")
    op.drop_column("m01_opportunities", "tenant_id")
