"""Create the durable Module 22 install-pipeline tables (candidates, proposals, jobs, portfolio)."""
from alembic import op
from app.modules.m22_tools_hub.pipeline import PIPELINE_TABLES

revision = "20260924_m22_install_pipeline"
down_revision = "20260924_m10_reviewer_keys"  # integration: chained after pb2 (m01 -> m10) instead of m20 so there is one linear head
branch_labels = None
depends_on = None

TABLES = PIPELINE_TABLES


def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        table.create(bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(TABLES):
        table.drop(bind, checkfirst=True)
