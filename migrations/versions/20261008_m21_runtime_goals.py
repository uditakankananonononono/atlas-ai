"""Claire runtime goal/job table (tenant+actor scoped)."""
from alembic import op
import sqlalchemy as sa
revision='20261008_m21_runtime_goals'
down_revision='20261008_m16_view_version'
branch_labels=None
depends_on=None
EXPECTED_COLUMNS={'id':(sa.String,False),'tenant_id':(sa.String,False),'actor_id':(sa.String,False),'purpose':(sa.Text,False),
 'criteria':(sa.Text,False),'max_steps':(sa.Integer,False),'status':(sa.String,False),'attempts':(sa.Integer,False),
 'lease_owner':(sa.String,True),'lease_token':(sa.String,True),'lease_expires_at':(sa.String,True),'blocker':(sa.String,True),
 'report':(sa.Text,True),'verdict':(sa.Text,True),'created_at':(sa.String,False),'updated_at':(sa.String,False)}
LATER={'cancel_requested_at'}  # added by 20261008_m21_runtime_cancel; a table created from the current model has it
EXPECTED_INDEXES={'ix_claire_runtime_goals_tenant_id':['tenant_id'],'ix_claire_runtime_goals_actor_id':['actor_id'],'ix_claire_runtime_goals_status':['status']}
def _verify_existing(inspector):
 """A table that already exists is accepted only if its shape matches exactly; otherwise refuse loudly."""
 problems=[]
 columns={c['name']:c for c in inspector.get_columns('claire_runtime_goals')}
 for name,(kind,nullable) in EXPECTED_COLUMNS.items():
  col=columns.get(name)
  if col is None:problems.append(f'missing column {name}');continue
  if not isinstance(col['type'],kind) or (kind is sa.String and isinstance(col['type'],sa.Text)) or (kind is sa.Text and not isinstance(col['type'],sa.Text)):
   problems.append(f'column {name} has type {type(col["type"]).__name__}')
  if bool(col['nullable'])!=nullable:problems.append(f'column {name} nullability differs')
 for name in sorted(set(columns)-set(EXPECTED_COLUMNS)-LATER):problems.append(f'unexpected column {name}')
 if inspector.get_pk_constraint('claire_runtime_goals').get('constrained_columns')!=['id']:problems.append('primary key is not (id)')
 indexes={i['name']:i['column_names'] for i in inspector.get_indexes('claire_runtime_goals')}
 for name,cols in EXPECTED_INDEXES.items():
  if indexes.get(name)!=cols:problems.append(f'missing or wrong index {name}')
 if problems:raise RuntimeError('claire_runtime_goals already exists with an incompatible shape; refusing to stamp it: '+'; '.join(problems))
def upgrade():
 inspector=sa.inspect(op.get_bind())
 if 'claire_runtime_goals' in inspector.get_table_names():
  _verify_existing(inspector);return
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
 bind=op.get_bind()
 if bind.execute(sa.text('SELECT 1 FROM claire_runtime_goals LIMIT 1')).first():
  # Goals hold owner work and evidence; a non-empty table is never dropped automatically.
  raise RuntimeError('Cannot drop claire_runtime_goals automatically: it holds goal evidence')
 op.drop_index('ix_claire_runtime_goals_status',table_name='claire_runtime_goals')
 op.drop_index('ix_claire_runtime_goals_actor_id',table_name='claire_runtime_goals')
 op.drop_index('ix_claire_runtime_goals_tenant_id',table_name='claire_runtime_goals')
 op.drop_table('claire_runtime_goals')
