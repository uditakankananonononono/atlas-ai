"""Claire runtime separation of duties: record who resolved an unknown effect."""
from alembic import op
import sqlalchemy as sa
revision='20261008_m21_runtime_separation'
down_revision='20261008_m21_runtime_effects'
branch_labels=None
depends_on=None
T='claire_runtime_effects'
def upgrade():
 cols={c['name']:c for c in sa.inspect(op.get_bind()).get_columns(T)}
 if 'resolved_by' in cols:
  c=cols['resolved_by']
  if not isinstance(c['type'],sa.String) or not c['nullable']:
   raise RuntimeError(T+'.resolved_by already exists with an incompatible shape; refusing to stamp it')
  return
 op.add_column(T,sa.Column('resolved_by',sa.String(200),nullable=True))
def downgrade():
 if op.get_bind().execute(sa.text(f'SELECT 1 FROM {T} WHERE resolved_by IS NOT NULL LIMIT 1')).first():
  raise RuntimeError('Cannot drop claire_runtime_effects.resolved_by automatically: it holds resolver records')
 with op.batch_alter_table(T) as b:b.drop_column('resolved_by')
