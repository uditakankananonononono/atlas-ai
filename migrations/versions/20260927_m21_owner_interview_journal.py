"""M21 consent-first interview and persistent owner journal."""
from alembic import op
import sqlalchemy as sa

revision = "20260927_m21_owner_journal"
down_revision = "20260924_m09_key_governance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Mirrors the M21 SQL models, while avoiding ad-hoc create_all in production.
    op.create_table(
        "claire_interview_consent",
        sa.Column("tenant_id", sa.String(120), primary_key=True),
        sa.Column("actor_id", sa.String(120), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "claire_interview_answers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("actor_id", sa.String(120), nullable=False),
        sa.Column("question_id", sa.String(80), nullable=False),
        sa.Column("choice", sa.String(80), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("source_reference", sa.String(240), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_claire_interview_answers_tenant_id", "claire_interview_answers", ["tenant_id"])
    op.create_index("ix_claire_interview_answers_actor_id", "claire_interview_answers", ["actor_id"])
    op.create_index("claire_interview_active_answer", "claire_interview_answers", ["tenant_id", "actor_id", "question_id"], unique=True,
                    postgresql_where=sa.text("revoked_at IS NULL"), sqlite_where=sa.text("revoked_at IS NULL"))
    op.create_table(
        "claire_owner_journal",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("actor_id", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("context", sa.Text(), nullable=False),
        sa.Column("source_reference", sa.String(240), nullable=False),
        sa.Column("vector", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_claire_owner_journal_tenant_id", "claire_owner_journal", ["tenant_id"])
    op.create_index("ix_claire_owner_journal_actor_id", "claire_owner_journal", ["actor_id"])


def downgrade() -> None:
    op.drop_index("ix_claire_owner_journal_actor_id", table_name="claire_owner_journal")
    op.drop_index("ix_claire_owner_journal_tenant_id", table_name="claire_owner_journal")
    op.drop_table("claire_owner_journal")
    op.drop_index("claire_interview_active_answer", table_name="claire_interview_answers")
    op.drop_index("ix_claire_interview_answers_actor_id", table_name="claire_interview_answers")
    op.drop_index("ix_claire_interview_answers_tenant_id", table_name="claire_interview_answers")
    op.drop_table("claire_interview_answers")
    op.drop_table("claire_interview_consent")
