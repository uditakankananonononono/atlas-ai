"""Durable tenant-isolated M19 generation state and evidence observations."""
from alembic import op
import sqlalchemy as sa
revision='20261003_m19_runs'
down_revision='20260927_m21_owner_journal'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('m19_runs',sa.Column('tenant_id',sa.String(120),primary_key=True),
        sa.Column('id',sa.String(36),primary_key=True),sa.Column('request_key',sa.String(200),nullable=False),
        sa.Column('request_hash',sa.String(64),nullable=False),sa.Column('version',sa.Integer(),nullable=False),
        sa.Column('snapshot',sa.JSON(),nullable=False),sa.UniqueConstraint('tenant_id','request_key'))
    op.create_table('m19_run_events',sa.Column('tenant_id',sa.String(120),primary_key=True),
        sa.Column('run_id',sa.String(36),primary_key=True),sa.Column('version',sa.Integer(),primary_key=True),
        sa.Column('event',sa.JSON(),nullable=False))
def downgrade():
    op.drop_table('m19_run_events');op.drop_table('m19_runs')
