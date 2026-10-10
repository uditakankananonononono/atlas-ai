"""Immutable approval-bound M14 one-wave ledger, opt-in dispatch only."""
from alembic import op
import sqlalchemy as sa
revision='20261010_m14_sandbox_wave'
down_revision='20261009_m24_generation_budget'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('m14_sandbox_waves',
        sa.Column('id',sa.String(36),primary_key=True),sa.Column('tenant_id',sa.String(120),nullable=False),
        sa.Column('actor_id',sa.String(120),nullable=False),sa.Column('project_id',sa.String(36),nullable=False),
        sa.Column('payload',sa.JSON,nullable=False),sa.Column('digest',sa.String(64),nullable=False),
        sa.Column('state',sa.String(40),nullable=False),sa.Column('approval_id',sa.String(36),unique=True),
        sa.Column('claim_key',sa.String(64),unique=True),sa.Column('result',sa.JSON),sa.Column('created_at',sa.String(40),nullable=False))
    op.create_index('ix_m14_sandbox_waves_tenant_id','m14_sandbox_waves',['tenant_id'])
    op.create_index('ix_m14_sandbox_waves_project_id','m14_sandbox_waves',['project_id'])
    op.create_table('m14_sandbox_wave_tasks',sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('wave_id',sa.String(36),nullable=False),sa.Column('task_id',sa.String(120),nullable=False),sa.Column('receipt',sa.JSON,nullable=False))
    op.create_index('ix_m14_sandbox_wave_tasks_wave_id','m14_sandbox_wave_tasks',['wave_id'])
    op.create_table('m14_sandbox_wave_artifacts',sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('wave_id',sa.String(36),nullable=False),sa.Column('task_id',sa.String(120),nullable=False),sa.Column('name',sa.String(200),nullable=False),
        sa.Column('sha256',sa.String(64),nullable=False),sa.Column('content_base64',sa.String(1400000),nullable=False))
    op.create_index('ix_m14_sandbox_wave_artifacts_wave_id','m14_sandbox_wave_artifacts',['wave_id'])

def downgrade():
    for table in ('m14_sandbox_wave_artifacts','m14_sandbox_wave_tasks','m14_sandbox_waves'):op.drop_table(table)
