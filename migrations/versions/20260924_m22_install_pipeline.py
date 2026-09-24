"""Create the durable Module 22 install-pipeline tables (proposals, jobs, portfolio)."""
from alembic import op
from app.modules.m22_tools_hub.pipeline import JobRow, PortfolioRow, ProposalRow

revision = "20260924_m22_install_pipeline"
down_revision = "20260922_m20_runtime_schema"
branch_labels = None
depends_on = None

TABLES = (ProposalRow.__table__, JobRow.__table__, PortfolioRow.__table__)


def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        table.create(bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(TABLES):
        table.drop(bind, checkfirst=True)
