"""Inactive invoice substeps. No legacy conversion/backfill."""
from alembic import op
import sqlalchemy as sa
revision='20261009_m24_invoice_steps'
down_revision='20261009_m24_checkout_snapshot'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('m24_invoice_steps',
        sa.Column('id',sa.String(80),primary_key=True),sa.Column('operation_id',sa.String(36),sa.ForeignKey('m24_provider_operations.id'),nullable=False),
        sa.Column('role',sa.String(40),nullable=False),sa.Column('provider_key',sa.String(80),nullable=False),sa.Column('endpoint',sa.String(120),nullable=False),
        sa.Column('form',sa.JSON,nullable=False),sa.Column('binding_hash',sa.String(64),nullable=False),sa.Column('state',sa.String(40),nullable=False),
        sa.Column('fence',sa.String(36)),sa.Column('lease_until',sa.DateTime(timezone=True)),sa.Column('first_attempt_at',sa.DateTime(timezone=True)),
        sa.Column('dispatch_not_after',sa.DateTime(timezone=True)),sa.Column('result',sa.JSON),sa.Column('failure',sa.String(80)),
        sa.UniqueConstraint('operation_id','role'),sa.UniqueConstraint('provider_key'),sa.CheckConstraint("role IN ('draft-invoice','invoice-item')"))
    op.create_index('ix_m24_invoice_steps_operation_id','m24_invoice_steps',['operation_id'])
    op.create_table('m24_invoice_step_attempts',sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('step_id',sa.String(80),sa.ForeignKey('m24_invoice_steps.id'),nullable=False),sa.Column('fence',sa.String(36),nullable=False,unique=True),
        sa.Column('binding_hash',sa.String(64),nullable=False),sa.Column('at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_m24_invoice_step_attempts_step_id','m24_invoice_step_attempts',['step_id'])

def downgrade():
    for name in ('m24_invoice_steps','m24_invoice_step_attempts'):
        if op.get_bind().execute(sa.text('SELECT count(*) FROM '+name)).scalar():raise RuntimeError('populated invoice step evidence; destructive downgrade refused')
    op.drop_table('m24_invoice_step_attempts');op.drop_table('m24_invoice_steps')
