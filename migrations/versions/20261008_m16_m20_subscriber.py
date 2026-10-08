"""Add minimal M16 subscriber projection, cursor and dedup receipts."""
from alembic import op
import sqlalchemy as sa
revision='20261008_m16_m20_subscriber'
down_revision='20261008_m20_event_outbox'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('m16_m20_stream_cursors',
        sa.Column('consumer',sa.String(80),primary_key=True),
        sa.Column('tenant_id',sa.String(120),primary_key=True),
        sa.Column('cursor',sa.String(80),nullable=False))
    op.create_table('m16_m20_event_receipts',
        sa.Column('consumer',sa.String(80),primary_key=True),
        sa.Column('tenant_id',sa.String(120),primary_key=True),
        sa.Column('event_id',sa.String(64),primary_key=True))
    op.create_table('m16_m20_task_status',
        sa.Column('tenant_id',sa.String(120),primary_key=True),
        sa.Column('task_id',sa.String(120),primary_key=True),
        sa.Column('state',sa.String(40),nullable=False),
        sa.Column('action_ids',sa.JSON(),nullable=False))

def downgrade():
    op.drop_table('m16_m20_task_status')
    op.drop_table('m16_m20_event_receipts')
    op.drop_table('m16_m20_stream_cursors')
