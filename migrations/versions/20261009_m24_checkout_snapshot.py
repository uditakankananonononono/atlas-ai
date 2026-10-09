"""Exact checkout forms. No backfill and no activation."""
from alembic import op
import sqlalchemy as sa
revision='20261009_m24_checkout_snapshot'
down_revision='20261009_m24_write_ahead'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('m24_checkout_snapshots',
        sa.Column('operation_id',sa.String(36),sa.ForeignKey('m24_provider_operations.id'),primary_key=True),
        sa.Column('form',sa.JSON,nullable=False),sa.Column('form_hash',sa.String(64),nullable=False),
        sa.Column('binding_hash',sa.String(64),nullable=False),sa.Column('adapter_version',sa.String(80),nullable=False))

def downgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM m24_checkout_snapshots')).scalar():
        raise RuntimeError('populated checkout snapshot; destructive downgrade refused')
    op.drop_table('m24_checkout_snapshots')
