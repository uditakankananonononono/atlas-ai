"""M20 reported local action journal, not independent effect receipts."""
from alembic import op
import sqlalchemy as sa
revision = '20261007_m20_action_records'
down_revision = '20260927_m21_owner_journal'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('m20_action_records',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('task_id', sa.String(), nullable=True),
        sa.Column('payload_json', sa.JSON(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_m20_action_records_tenant_id','m20_action_records',['tenant_id'])
    op.create_index('ix_m20_action_records_task_id','m20_action_records',['task_id'])


def downgrade():
    op.drop_table('m20_action_records')
