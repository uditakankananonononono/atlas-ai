"""Cancellation snapshots, no sparse legacy conversion or activation."""
from alembic import op
import sqlalchemy as sa
revision='20261009_m24_cancellation'
down_revision='20261009_m24_reconciliation'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('m24_cancellation_snapshots',sa.Column('operation_id',sa.String(36),sa.ForeignKey('m24_provider_operations.id'),primary_key=True),
        sa.Column('customer_id',sa.String(200),nullable=False),sa.Column('subscription_id',sa.String(200),nullable=False),sa.Column('before_state',sa.JSON,nullable=False),
        sa.Column('form',sa.JSON,nullable=False),sa.Column('binding_hash',sa.String(64),nullable=False))

def downgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM m24_cancellation_snapshots')).scalar():raise RuntimeError('populated cancellation snapshot; destructive downgrade refused')
    op.drop_table('m24_cancellation_snapshots')
