"""M00 approval impact preview: reviewer-seen external state snapshots."""
from alembic import op
import sqlalchemy as sa

revision = "20260924_m00_review_states"
down_revision = "20260922_m20_runtime_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "m00_approval_review_states",
        sa.Column("approval_id", sa.String(36), primary_key=True),
        sa.Column("state_hash", sa.String(64), nullable=False),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("probe", sa.String(200), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("m00_approval_review_states")
