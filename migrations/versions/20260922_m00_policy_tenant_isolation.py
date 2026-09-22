"""Tenant-isolate approval policies."""
from alembic import op
import sqlalchemy as sa
revision="20260922_m00_policy_tenant_iso"
down_revision="20260922_m01_tenant_isolation"
branch_labels=None
depends_on=None

def upgrade():
    if op.get_bind().dialect.name == "sqlite":
        # SQLite does not preserve PostgreSQL's named primary-key constraint.
        # This compatibility path proves clean local migration; PostgreSQL gets
        # the production composite tenant key below.
        op.add_column("m00_approval_policies",sa.Column("tenant_id",sa.String(120),nullable=False,server_default="local"))
        op.create_index("ix_m00_approval_policies_tenant_id","m00_approval_policies",["tenant_id"],unique=False)
        return
    op.add_column("m00_approval_policies",sa.Column("tenant_id",sa.String(120),nullable=False,server_default="local"))
    op.drop_constraint("m00_approval_policies_pkey","m00_approval_policies",type_="primary")
    op.create_primary_key("m00_approval_policies_pkey","m00_approval_policies",["tenant_id","id"])
    op.alter_column("m00_approval_policies","tenant_id",server_default=None)

def downgrade():
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index("ix_m00_approval_policies_tenant_id",table_name="m00_approval_policies")
        op.drop_column("m00_approval_policies","tenant_id")
        return
    op.drop_constraint("m00_approval_policies_pkey","m00_approval_policies",type_="primary")
    op.create_primary_key("m00_approval_policies_pkey","m00_approval_policies",["id"])
    op.drop_column("m00_approval_policies","tenant_id")
