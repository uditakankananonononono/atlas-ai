"""Claire runtime goals: owner cancel request for a running goal."""
from alembic import op
import sqlalchemy as sa
revision='20261008_m21_runtime_cancel'
down_revision='20261008_m21_runtime_separation'
branch_labels=None
depends_on=None
T='claire_runtime_goals'
def upgrade():
 cols={c['name']:c for c in sa.inspect(op.get_bind()).get_columns(T)}
 if 'cancel_requested_at' in cols:
  c=cols['cancel_requested_at']
  if not isinstance(c['type'],sa.String) or isinstance(c['type'],sa.Text) or not c['nullable']:
   raise RuntimeError(T+'.cancel_requested_at already exists with an incompatible shape; refusing to stamp it')
  return
 op.add_column(T,sa.Column('cancel_requested_at',sa.String(40),nullable=True))
def downgrade():
 if op.get_bind().execute(sa.text(f'SELECT 1 FROM {T} WHERE cancel_requested_at IS NOT NULL LIMIT 1')).first():
  raise RuntimeError('Cannot drop claire_runtime_goals.cancel_requested_at automatically: it holds cancel requests')
 with op.batch_alter_table(T) as b:b.drop_column('cancel_requested_at')
