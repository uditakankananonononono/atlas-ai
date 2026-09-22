"""Tenant-isolate approval policies."""
from alembic import op
import sqlalchemy as sa
revision="20260922_m00_policy_tenant_isolation"
down_revision="20260922_m01_tenant_isolation"
branch_labels=None
depends_on=None

def upgrade():
    op.add_column("m00_approval_policies",sa.Column("tenant_id",sa.String(120),nullable=False,server_default="local"))
    op.drop_constraint("m00_approval_policies_pkey","m00_approval_policies",type_="primary")
    op.create_primary_key("m00_approval_policies_pkey","m00_approval_policies",["tenant_id","id"])
    op.alter_column("m00_approval_policies","tenant_id",server_default=None)

def downgrade():
    op.drop_constraint("m00_approval_policies_pkey","m00_approval_policies",type_="primary")
    op.create_primary_key("m00_approval_policies_pkey","m00_approval_policies",["id"])
    op.drop_column("m00_approval_policies","tenant_id")
