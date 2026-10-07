"""Tenant-scoped risk register and append-only revision records."""
from alembic import op
import sqlalchemy as sa
revision = '20261007_m20_risk_register'
down_revision = '20261007_m20_task_metadata'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('m20_risk_registers',
        sa.Column('tenant_id', sa.String(), primary_key=True),
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('goal', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    op.create_table('m20_risk_revisions',
        sa.Column('tenant_id', sa.String(), primary_key=True),
        sa.Column('register_id', sa.String(), primary_key=True),
        sa.Column('revision', sa.Integer(), primary_key=True),
        sa.Column('report_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table('m20_risk_revisions')
    op.drop_table('m20_risk_registers')
