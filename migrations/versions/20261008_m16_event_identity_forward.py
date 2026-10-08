"""Enforce event identity without silently deleting preexisting duplicates."""
from alembic import op
import sqlalchemy as sa
revision='20261008_m16_identity_forward'
down_revision='20261007_m20_model_unknown'
branch_labels=None
depends_on=None
def upgrade():
 bind=op.get_bind();inspector=sa.inspect(bind)
 if 'm16_events' not in inspector.get_table_names():raise RuntimeError('m16_events schema missing')
 constraints=inspector.get_unique_constraints('m16_events')+inspector.get_indexes('m16_events')
 if any(c.get('unique',True) and c.get('column_names')==['tenant_id','id'] for c in constraints):return
 if bind.execute(sa.text('SELECT 1 FROM m16_events GROUP BY tenant_id,id HAVING count(*) > 1 LIMIT 1')).first():
  raise RuntimeError('Duplicate M16 event identities require owner-reviewed reconciliation; no rows deleted')
 op.create_index('uq_m16_event_id','m16_events',['tenant_id','id'],unique=True)
def downgrade():
 raise RuntimeError('Cannot remove M16 identity protection automatically')
