"""Separate verified billing inbox and unsigned quarantine, no legacy promotion."""
from alembic import op
import sqlalchemy as sa
revision='20261009_m24_verified_inbox'
down_revision='20261009_m24_cancellation'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('m24_verified_inbox',sa.Column('identity',sa.String(400),primary_key=True),
        sa.Column('provider_account',sa.String(200),nullable=False),sa.Column('environment',sa.String(20),nullable=False),
        sa.Column('event_id',sa.String(120),nullable=False),sa.Column('event_type',sa.String(120),nullable=False),sa.Column('created',sa.Integer,nullable=False),
        sa.Column('digest',sa.String(64),nullable=False),sa.Column('payload_digest',sa.String(64),nullable=False),sa.Column('payload',sa.JSON,nullable=False),sa.Column('state',sa.String(30),nullable=False),
        sa.Column('failure',sa.String(120),nullable=True),sa.Column('verified_at',sa.DateTime(timezone=True),nullable=False),sa.Column('applied_at',sa.DateTime(timezone=True),nullable=True))
    op.create_table('m24_inbox_quarantine',sa.Column('id',sa.String(36),primary_key=True),sa.Column('event_id',sa.String(120),nullable=False),
        sa.Column('digest',sa.String(64),nullable=False),sa.Column('reason',sa.String(120),nullable=False),sa.Column('observed_at',sa.DateTime(timezone=True),nullable=False))
    op.create_table('m24_inbox_resource_bindings',sa.Column('identity',sa.String(400),primary_key=True),sa.Column('provider_account',sa.String(200),nullable=False),
        sa.Column('environment',sa.String(20),nullable=False),sa.Column('resource_id',sa.String(200),nullable=False),sa.Column('tenant_id',sa.String(120),nullable=False),
        sa.Column('customer_id',sa.String(200),nullable=False),sa.Column('version',sa.Integer,nullable=False),sa.Column('event_digest',sa.String(64),nullable=True))

def downgrade():
    for table in ('m24_verified_inbox','m24_inbox_quarantine','m24_inbox_resource_bindings'):
        if op.get_bind().execute(sa.text('SELECT count(*) FROM '+table)).scalar():raise RuntimeError('populated verified inbox; destructive downgrade refused')
    for table in ('m24_verified_inbox','m24_inbox_quarantine','m24_inbox_resource_bindings'):op.drop_table(table)
