"""Durable post-ingest drafting ownership. Never backfill guessed phases."""
from alembic import op
import sqlalchemy as sa
revision='20261007_m10_draft_work'
down_revision='20261007_m10_account_messages'
branch_labels=None
depends_on=None

def upgrade():
 if 'm10_draft_work' in sa.inspect(op.get_bind()).get_table_names():return
 op.create_table('m10_draft_work',
  sa.Column('tenant_id',sa.String(120),primary_key=True),
  sa.Column('message_id',sa.String(36),primary_key=True),
  sa.Column('account_id',sa.String(36),nullable=False),
  sa.Column('phase',sa.String(40),nullable=False),
  sa.Column('data',sa.JSON(),nullable=False))
 op.create_index('ix_m10_draft_work_account_id','m10_draft_work',['account_id'])
 op.create_index('ix_m10_draft_work_phase','m10_draft_work',['phase'])

def downgrade():
 if 'm10_draft_work' not in sa.inspect(op.get_bind()).get_table_names():return
 if op.get_bind().execute(sa.text('SELECT 1 FROM m10_draft_work LIMIT 1')).first():
  raise RuntimeError('Cannot remove durable draft ownership or unknown outcomes')
 op.drop_table('m10_draft_work')
