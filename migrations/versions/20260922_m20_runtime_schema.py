"""Create the durable Module 20 cognitive-runtime schema.

The initial generated migration treated the separately declared GCW metadata as
pre-existing and emitted destructive drops. This revision creates those tables
from frozen historical metadata, in dependency order. Live runtime metadata
would incorrectly create future tables/columns before their additive revisions.
"""
from alembic import op
from migrations.gcw_schema_20260922 import Base as GCWBase

revision = "20260922_m20_runtime_schema"
down_revision = "20260922_m00_policy_tenant_iso"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    for table in GCWBase.metadata.sorted_tables:
        table.create(bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(GCWBase.metadata.sorted_tables):
        table.drop(bind, checkfirst=True)
