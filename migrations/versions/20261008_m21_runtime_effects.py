"""Claire runtime effect journal (idempotency and reconciliation of non-read calls)."""
from alembic import op
import sqlalchemy as sa
revision='20261008_m21_runtime_effects'
down_revision='20261008_m21_runtime_approvals'
branch_labels=None
depends_on=None
T='claire_runtime_effects'
EXPECTED={'id':(sa.String,False),'tenant_id':(sa.String,False),'actor_id':(sa.String,False),'goal_id':(sa.String,False),
 'tool':(sa.String,False),'idempotency_key':(sa.String,False),'state':(sa.String,False),'attempts':(sa.Integer,False),
 'receipt_json':(sa.Text,True),'created_at':(sa.String,False),'updated_at':(sa.String,False)}
IDX={'ix_claire_runtime_effects_tenant_id':['tenant_id'],'ix_claire_runtime_effects_actor_id':['actor_id'],'ix_claire_runtime_effects_goal_id':['goal_id']}
UQ=('uq_claire_runtime_effects_goal_key',['goal_id','idempotency_key'])
def _verify(inspector):
 problems=[];cols={c['name']:c for c in inspector.get_columns(T)}
 for n,(kind,nullable) in EXPECTED.items():
  c=cols.get(n)
  if c is None:problems.append(f'missing column {n}');continue
  if not isinstance(c['type'],kind):problems.append(f'column {n} has type {type(c["type"]).__name__}')
  if bool(c['nullable'])!=nullable:problems.append(f'column {n} nullability differs')
 for n in sorted(set(cols)-set(EXPECTED)):problems.append(f'unexpected column {n}')
 if inspector.get_pk_constraint(T).get('constrained_columns')!=['id']:problems.append('primary key is not (id)')
 have={i['name']:i['column_names'] for i in inspector.get_indexes(T)}
 for n,c in IDX.items():
  if have.get(n)!=c:problems.append(f'missing or wrong index {n}')
 uqs={u['name']:u['column_names'] for u in inspector.get_unique_constraints(T)}
 uqs.update({i['name']:i['column_names'] for i in inspector.get_indexes(T) if i.get('unique')})
 if uqs.get(UQ[0])!=UQ[1]:problems.append('missing or wrong unique constraint '+UQ[0])
 if problems:raise RuntimeError(T+' already exists with an incompatible shape; refusing to stamp it: '+'; '.join(problems))
def upgrade():
 inspector=sa.inspect(op.get_bind())
 if T in inspector.get_table_names():
  _verify(inspector);return
 op.create_table(T,
  sa.Column('id',sa.String(36),primary_key=True),
  sa.Column('tenant_id',sa.String(200),nullable=False),sa.Column('actor_id',sa.String(200),nullable=False),
  sa.Column('goal_id',sa.String(36),nullable=False),sa.Column('tool',sa.String(100),nullable=False),
  sa.Column('idempotency_key',sa.String(64),nullable=False),sa.Column('state',sa.String(20),nullable=False),
  sa.Column('attempts',sa.Integer(),nullable=False),sa.Column('receipt_json',sa.Text(),nullable=True),
  sa.Column('created_at',sa.String(40),nullable=False),sa.Column('updated_at',sa.String(40),nullable=False),
  sa.UniqueConstraint(*UQ[1],name=UQ[0]))
 for n,c in IDX.items():op.create_index(n,T,c)
def downgrade():
 if op.get_bind().execute(sa.text(f'SELECT 1 FROM {T} LIMIT 1')).first():
  raise RuntimeError('Cannot drop claire_runtime_effects automatically: it holds effect journal records')
 for n in IDX:op.drop_index(n,table_name=T)
 op.drop_table(T)
