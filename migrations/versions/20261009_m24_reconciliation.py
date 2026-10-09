"""Reviewed positive lookup evidence only. No legacy repair/backfill or activation."""
from alembic import op
import sqlalchemy as sa
revision='20261009_m24_reconciliation'
down_revision='20261009_m24_invoice_steps'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('m24_lookup_evidence',sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('operation_id',sa.String(36),sa.ForeignKey('m24_provider_operations.id'),nullable=False),sa.Column('tenant_id',sa.String(120),nullable=False),
        sa.Column('role',sa.String(40),nullable=False),sa.Column('binding_hash',sa.String(64),nullable=False),sa.Column('provider_account',sa.String(200),nullable=False),
        sa.Column('environment',sa.String(20),nullable=False),sa.Column('api_version',sa.String(80),nullable=False),sa.Column('object_id',sa.String(200),nullable=False),
        sa.Column('receipt',sa.JSON,nullable=False),sa.Column('evidence_digest',sa.String(64),nullable=False),sa.Column('observed_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('accepted_by',sa.String(120)),sa.Column('accepted_at',sa.DateTime(timezone=True)))
    op.create_index('ix_m24_lookup_evidence_operation_id','m24_lookup_evidence',['operation_id'])

def downgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM m24_lookup_evidence')).scalar():raise RuntimeError('populated lookup evidence; destructive downgrade refused')
    op.drop_table('m24_lookup_evidence')
