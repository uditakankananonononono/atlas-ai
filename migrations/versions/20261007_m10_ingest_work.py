"""Claim extraction/embedding before provider work; unknowns never auto-retry."""
from alembic import op
import sqlalchemy as sa
revision='20261007_m10_ingest_work'
down_revision='20261007_m10_draft_work'
branch_labels=None
depends_on=None

def upgrade():
 if 'm10_ingest_work' in sa.inspect(op.get_bind()).get_table_names():return
 op.create_table('m10_ingest_work',sa.Column('tenant_id',sa.String(120),primary_key=True),sa.Column('account_id',sa.String(36),primary_key=True),sa.Column('gmail_id',sa.String(64),primary_key=True),sa.Column('phase',sa.String(40),nullable=False),sa.Column('data',sa.JSON(),nullable=False))
 op.create_index('ix_m10_ingest_work_phase','m10_ingest_work',['phase'])

def downgrade():
 if 'm10_ingest_work' not in sa.inspect(op.get_bind()).get_table_names():return
 if op.get_bind().execute(sa.text('SELECT 1 FROM m10_ingest_work LIMIT 1')).first():raise RuntimeError('Cannot remove ingestion ownership or unknown provider outcomes')
 op.drop_table('m10_ingest_work')
