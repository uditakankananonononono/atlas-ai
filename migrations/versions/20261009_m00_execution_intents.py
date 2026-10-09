"""Local execution intent/outcome ledger, no historical dispatch backfill."""
from alembic import op
import sqlalchemy as sa
revision='20261009_m00_execution_intents'
down_revision='20261008_m20_chroma_jobs'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('m00_execution_intents',
        sa.Column('approval_id',sa.String(36),primary_key=True),
        sa.Column('tenant_id',sa.String(120),nullable=False),
        sa.Column('effect_id',sa.String(200),nullable=False),
        sa.Column('request_hash',sa.String(64),nullable=False),
        sa.Column('adapter_version',sa.String(120),nullable=False),
        sa.Column('state',sa.String(32),nullable=False),
        sa.Column('fence',sa.String(36),nullable=True),
        sa.Column('lease_until',sa.DateTime(timezone=True),nullable=True),
        sa.Column('result',sa.JSON(),nullable=True),
        sa.Column('failure',sa.String(80),nullable=True),
        sa.UniqueConstraint('effect_id'))
    op.create_index('ix_m00_execution_intents_tenant_id','m00_execution_intents',['tenant_id'])

def downgrade():
    connection=op.get_bind()
    if connection.execute(sa.text('SELECT count(*) FROM m00_execution_intents')).scalar():
        raise RuntimeError('execution outcome ledger contains records; destructive downgrade refused')
    op.drop_index('ix_m00_execution_intents_tenant_id',table_name='m00_execution_intents')
    op.drop_table('m00_execution_intents')
