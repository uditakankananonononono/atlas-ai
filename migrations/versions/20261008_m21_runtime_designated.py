"""Claire runtime goals: optional designated approvers (JSON list of principal ids; null = any approver-role principal)."""
from alembic import op
import sqlalchemy as sa
revision='20261008_m21_runtime_designated'
down_revision='20261008_m21_runtime_cancel'
branch_labels=None
depends_on=None
T='claire_runtime_goals'
def upgrade():
 cols={c['name']:c for c in sa.inspect(op.get_bind()).get_columns(T)}
 if 'designated_approvers' in cols:
  c=cols['designated_approvers']
  if not isinstance(c['type'],sa.Text) or not c['nullable']:
   raise RuntimeError(T+'.designated_approvers already exists with an incompatible shape; refusing to stamp it')
  return
 op.add_column(T,sa.Column('designated_approvers',sa.Text,nullable=True))
def downgrade():
 if op.get_bind().execute(sa.text(f'SELECT 1 FROM {T} WHERE designated_approvers IS NOT NULL LIMIT 1')).first():
  raise RuntimeError('Cannot drop claire_runtime_goals.designated_approvers automatically: it holds approver restrictions')
 with op.batch_alter_table(T) as b:b.drop_column('designated_approvers')
