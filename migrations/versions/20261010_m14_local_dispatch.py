"""Explicit finite local dispatch jobs, no startup worker or legacy backfill."""
from alembic import op
import sqlalchemy as sa
revision='20261010_m14_local_dispatch'
down_revision='20261010_m14_builder_admission'
branch_labels=None
depends_on=None
def upgrade():
    p=op.create_table('m14_local_dispatch_pool',sa.Column('id',sa.Integer,primary_key=True),sa.Column('policy',sa.JSON,nullable=False))
    op.bulk_insert(p,[dict(id=1,policy=dict(workers=2,sandbox_tasks=4,max_wave_tasks=2))])
    op.create_table('m14_local_dispatch_jobs',sa.Column('id',sa.String(36),primary_key=True),sa.Column('tenant_id',sa.String(120),nullable=False),sa.Column('actor_id',sa.String(120),nullable=False),sa.Column('wave_id',sa.String(36),nullable=False,unique=True),sa.Column('batch_id',sa.String(36),nullable=False),sa.Column('payload',sa.JSON,nullable=False),sa.Column('digest',sa.String(64),nullable=False),sa.Column('state',sa.String(30),nullable=False),sa.Column('fence',sa.Integer,nullable=False),sa.Column('token',sa.String(36)),sa.Column('worker_id',sa.String(120)),sa.Column('result',sa.JSON))
    op.create_index('ix_m14_local_dispatch_jobs_tenant_id','m14_local_dispatch_jobs',['tenant_id'])
def downgrade():
    if op.get_bind().execute(sa.text("SELECT count(*) FROM m14_local_dispatch_jobs WHERE state IN ('queued','claimed')")).scalar():raise RuntimeError('unsettled local jobs refuse downgrade')
    op.drop_table('m14_local_dispatch_jobs');op.drop_table('m14_local_dispatch_pool')
