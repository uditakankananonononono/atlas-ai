"""Claire runtime approvals: revocation provenance (revoked_at + revoked_by, always set together)."""
from alembic import op
import sqlalchemy as sa
revision='20261008_m21_runtime_revoke'
down_revision='20261008_m21_runtime_designated'
branch_labels=None
depends_on=None
T='claire_runtime_approvals'
NEW={'revoked_at':40,'revoked_by':200}
def _shape_ok(c,n):
 return isinstance(c['type'],sa.String) and not isinstance(c['type'],sa.Text) and bool(c['nullable']) and getattr(c['type'],'length',None) in (None,NEW[n])
def upgrade():
 cols={c['name']:c for c in sa.inspect(op.get_bind()).get_columns(T)}
 have=[n for n in NEW if n in cols]
 if len(have)==2:
  bad=[n for n in NEW if not _shape_ok(cols[n],n)]
  if bad:raise RuntimeError(T+'.'+','.join(bad)+' already exist with an incompatible shape; refusing to stamp it')
  return
 if have:raise RuntimeError(T+' has only one of revoked_at/revoked_by (partial revocation columns); refusing to stamp it')
 for n,ln in NEW.items():op.add_column(T,sa.Column(n,sa.String(ln),nullable=True))
def downgrade():
 if op.get_bind().execute(sa.text(f'SELECT 1 FROM {T} WHERE revoked_at IS NOT NULL OR revoked_by IS NOT NULL LIMIT 1')).first():
  raise RuntimeError('Cannot drop claire_runtime_approvals.revoked_at/revoked_by automatically: they hold revocation provenance')
 with op.batch_alter_table(T) as b:
  b.drop_column('revoked_by');b.drop_column('revoked_at')
