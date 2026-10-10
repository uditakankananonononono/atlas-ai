"""Fixed 1000 logical admission policy. No dispatch, no legacy backfill."""
from alembic import op
import sqlalchemy as sa
revision='20261010_m14_builder_admission'
down_revision='20261010_m14_review_continue'
branch_labels=None
depends_on=None

def upgrade():
    pool=op.create_table('m14_builder_pool',sa.Column('id',sa.Integer,primary_key=True),sa.Column('epoch',sa.Integer,nullable=False),sa.Column('limits',sa.JSON,nullable=False),sa.Column('used',sa.JSON,nullable=False))
    op.bulk_insert(pool,[dict(id=1,epoch=0,limits=dict(slots=1000,cpu_units=1000,memory_mb=256000,runtime_seconds=1000000,cost_cents=0),used=dict(slots=0,cpu_units=0,memory_mb=0,runtime_seconds=0,cost_cents=0))])
    op.create_table('m14_builder_tenants',sa.Column('tenant_id',sa.String(120),primary_key=True),sa.Column('limits',sa.JSON,nullable=False),sa.Column('used',sa.JSON,nullable=False))
    op.create_table('m14_builder_batches',sa.Column('id',sa.String(36),primary_key=True),sa.Column('tenant_id',sa.String(120),nullable=False),sa.Column('actor_id',sa.String(120),nullable=False),sa.Column('payload',sa.JSON,nullable=False),sa.Column('digest',sa.String(64),nullable=False),sa.Column('state',sa.String(30),nullable=False),sa.Column('approval_id',sa.String(36),nullable=False,unique=True),sa.Column('decided_by',sa.String(120)),sa.Column('decided_at',sa.String(40)))
    op.create_index('ix_m14_builder_batches_tenant_id','m14_builder_batches',['tenant_id'])
    op.create_table('m14_builder_slots',sa.Column('id',sa.String(36),primary_key=True),sa.Column('batch_id',sa.String(36),nullable=False),sa.Column('tenant_id',sa.String(120),nullable=False),sa.Column('actor_id',sa.String(120),nullable=False),sa.Column('work_key',sa.String(64),nullable=False),sa.Column('wave_id',sa.String(36),nullable=False),sa.Column('project_id',sa.String(36),nullable=False),sa.Column('task_id',sa.String(120),nullable=False),sa.Column('state',sa.String(30),nullable=False),sa.Column('resources',sa.JSON,nullable=False),sa.Column('expires_at',sa.String(40),nullable=False),sa.Column('fence',sa.Integer,nullable=False),sa.Column('token',sa.String(36)),sa.Column('worker_id',sa.String(120)),sa.Column('reconciliation',sa.JSON),sa.UniqueConstraint('work_key'))
    for field in ('batch_id','tenant_id'):op.create_index('ix_m14_builder_slots_'+field,'m14_builder_slots',[field])
    op.create_table('m14_builder_admission_events',sa.Column('id',sa.Integer,primary_key=True,autoincrement=True),sa.Column('batch_id',sa.String(36),nullable=False),sa.Column('slot_id',sa.String(36)),sa.Column('actor_id',sa.String(120),nullable=False),sa.Column('event',sa.String(40),nullable=False),sa.Column('at',sa.String(40),nullable=False),sa.Column('details',sa.JSON,nullable=False))

def downgrade():
    # Refuse destructive removal of live or outcome-unknown reservations.
    connection=op.get_bind()
    if connection.execute(sa.text("SELECT count(*) FROM m14_builder_slots WHERE state IN ('reserved','claimed','unknown')")).scalar():
        raise RuntimeError('active logical admissions must be explicitly settled before downgrade')
    for name in ('m14_builder_admission_events','m14_builder_slots','m14_builder_batches','m14_builder_tenants','m14_builder_pool'):op.drop_table(name)
