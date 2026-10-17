"""Durable tenant-scoped idea runs for M19; no backfill."""
from alembic import op
import sqlalchemy as sa
revision='20261017_m19_runs'
down_revision='20261011_m20_meta_state'
branch_labels=None
depends_on=None
def upgrade():
    op.create_table('m19_runs',sa.Column('pk',sa.Integer,primary_key=True,autoincrement=True),sa.Column('tenant_id',sa.String(120),nullable=False),sa.Column('id',sa.String(36),nullable=False,unique=True),sa.Column('state',sa.String(30),nullable=False),sa.Column('stage',sa.String(30),nullable=False),sa.Column('payload',sa.JSON,nullable=False),sa.Column('spent',sa.Float,nullable=False),sa.Column('reserved',sa.Float,nullable=False),sa.Column('budget_cap',sa.Float,nullable=False),sa.Column('priority',sa.Integer,nullable=False),sa.Column('version',sa.Integer,nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_m19_runs_tenant_id','m19_runs',['tenant_id'])
    op.create_index('ix_m19_runs_id','m19_runs',['id'])
    op.create_index('ix_m19_runs_stage','m19_runs',['stage'])
    op.create_table('m19_run_events',sa.Column('pk',sa.Integer,primary_key=True,autoincrement=True),sa.Column('tenant_id',sa.String(120),nullable=False),sa.Column('run_id',sa.String(36),nullable=False),sa.Column('kind',sa.String(40),nullable=False),sa.Column('version',sa.Integer,nullable=False),sa.Column('payload',sa.JSON,nullable=False),sa.Column('at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_m19_run_events_tenant_id','m19_run_events',['tenant_id'])
    op.create_index('ix_m19_run_events_run_id','m19_run_events',['run_id'])
def downgrade():
    op.drop_table('m19_run_events');op.drop_table('m19_runs')
