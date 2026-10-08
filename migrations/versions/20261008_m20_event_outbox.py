"""Add the opt-in M20 checkpoint event outbox."""
from alembic import op
import sqlalchemy as sa

revision = '20261008_m20_event_outbox'
down_revision = '20261008_m16_view_version'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('m20_runtime_event_outbox',
        sa.Column('event_id',sa.String(64),primary_key=True),
        sa.Column('tenant_id',sa.String(120),nullable=False),
        sa.Column('task_id',sa.String(120),nullable=False),
        sa.Column('state',sa.String(40),nullable=False),
        sa.Column('action_ids',sa.JSON(),nullable=False),
        sa.Column('delivered',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.create_index('ix_m20_runtime_event_outbox_tenant_id','m20_runtime_event_outbox',['tenant_id'])


def downgrade():
    op.drop_index('ix_m20_runtime_event_outbox_tenant_id',table_name='m20_runtime_event_outbox')
    op.drop_table('m20_runtime_event_outbox')
