"""Record which NLP engine scored each M01 opportunity.

``match_engine`` / ``deadline_engine`` let the dashboard and audits tell a real
embedding/dateparser result from a token/regex fallback.
"""
from alembic import op
import sqlalchemy as sa

revision = "20260924_m01_nlp_provenance"
down_revision = "20260922_m20_runtime_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("m01_opportunities", sa.Column("match_engine", sa.String(length=300), nullable=False, server_default="token-cosine"))
    op.add_column("m01_opportunities", sa.Column("deadline_engine", sa.String(length=300), nullable=False, server_default="regex-formats"))


def downgrade() -> None:
    op.drop_column("m01_opportunities", "deadline_engine")
    op.drop_column("m01_opportunities", "match_engine")
