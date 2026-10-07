"""Durable once-per-message M05 delivery claims."""
from alembic import op
import sqlalchemy as sa
revision = "20261007_m05_delivery_claims"
down_revision = "20260927_m21_owner_journal"
branch_labels = None
depends_on = None


def upgrade():
    # The historical baseline imports current metadata on a fresh install.
    # Existing installs still need this explicit addition.
    if not sa.inspect(op.get_bind()).has_table("m05_delivery_claims"):
        op.create_table("m05_delivery_claims",
            sa.Column("tenant_id", sa.String(120), primary_key=True),
            sa.Column("message_id", sa.String(36), primary_key=True),
            sa.Column("approval_id", sa.String(36), nullable=False),
            sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table("m05_delivery_claims")
