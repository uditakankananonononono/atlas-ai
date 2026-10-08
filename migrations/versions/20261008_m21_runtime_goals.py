"""Claire runtime goal/job table (tenant+actor scoped)."""
from alembic import op
import sqlalchemy as sa
revision='20261008_m21_runtime_goals'
down_revision='20261008_m16_identity_forward'
branch_labels=None
depends_on=None
def upgrade():
 inspector=sa.inspect(op.get_bind())
 if 'claire_runtime_goals' in inspector.get_table_names():return
 op.create_table('claire_runtime_goals',
  sa.Column('id',sa.String(36),primary_key=True),
  sa.Column('tenant_id',sa.String(200),nullable=False),
  sa.Column('actor_id',sa.String(200),nullable=False),
  sa.Column('purpose',sa.Text,nullable=False),
  sa.Column('criteria',sa.Text,nullable=False),
  sa.Column('max_steps',sa.Integer,nullable=False),
  sa.Column('status',sa.String(20),nullable=False),
  sa.Column('attempts',sa.Integer,nullable=False),
  sa.Column('lease_owner',sa.String(100),nullable=True),
  sa.Column('lease_token',sa.String(64),nullable=True),
  sa.Column('lease_expires_at',sa.String(40),nullable=True),
  sa.Column('blocker',sa.String(100),nullable=True),
  sa.Column('report',sa.Text,nullable=True),
  sa.Column('verdict',sa.Text,nullable=True),
  sa.Column('created_at',sa.String(40),nullable=False),
  sa.Column('updated_at',sa.String(40),nullable=False))
 op.create_index('ix_claire_runtime_goals_tenant_id','claire_runtime_goals',['tenant_id'])
 op.create_index('ix_claire_runtime_goals_actor_id','claire_runtime_goals',['actor_id'])
 op.create_index('ix_claire_runtime_goals_status','claire_runtime_goals',['status'])
def downgrade():
 # Goals hold owner work and evidence; dropping them is not automatic.
 raise RuntimeError('Cannot drop claire_runtime_goals automatically: it holds goal evidence')
