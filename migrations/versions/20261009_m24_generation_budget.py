"""Inactive generation budget seam, no provisioning/backfill/activation."""
from alembic import op
import sqlalchemy as sa
revision='20261009_m24_generation_budget'
down_revision='20261009_m24_verified_inbox'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('m24_generation_budgets',sa.Column('id',sa.String(120),primary_key=True),sa.Column('tenant_id',sa.String(120),nullable=False),
        sa.Column('account',sa.String(200),nullable=False),sa.Column('price_schedule',sa.JSON,nullable=False),
        *[sa.Column(key,sa.Integer,nullable=False) for key in ('available_input','available_output','available_micro_usd','available_attempts')],
        sa.CheckConstraint('available_input >= 0 AND available_output >= 0 AND available_micro_usd >= 0 AND available_attempts >= 0'))
    op.create_table('m24_generations',sa.Column('id',sa.String(36),primary_key=True),sa.Column('approval_id',sa.String(36),nullable=False),
        sa.Column('tenant_id',sa.String(120),nullable=False),sa.Column('budget_id',sa.String(120),sa.ForeignKey('m24_generation_budgets.id'),nullable=False),
        sa.Column('request_hash',sa.String(64),nullable=False),sa.Column('request',sa.JSON,nullable=False),sa.Column('binding_hash',sa.String(64),nullable=False),
        sa.Column('state',sa.String(40),nullable=False),sa.Column('fence',sa.String(36),nullable=True),sa.Column('lease_until',sa.DateTime(timezone=True),nullable=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('output',sa.JSON,nullable=True),sa.Column('failure',sa.String(80),nullable=True),sa.UniqueConstraint('approval_id'))
    op.create_table('m24_generation_budget_attempts',sa.Column('generation_id',sa.String(36),sa.ForeignKey('m24_generations.id'),primary_key=True),
        sa.Column('state',sa.String(30),nullable=False),*[sa.Column(key,sa.Integer,nullable=False) for key in ('reserved_input','reserved_output','reserved_micro_usd')],
        *[sa.Column(key,sa.Integer,nullable=True) for key in ('actual_input','actual_output','actual_micro_usd')],
        sa.CheckConstraint('reserved_input >= 0 AND reserved_output >= 0 AND reserved_micro_usd >= 0'))
    op.create_table('m24_generation_events',sa.Column('id',sa.Integer,primary_key=True,autoincrement=True),sa.Column('generation_id',sa.String(36),nullable=False),
        sa.Column('event',sa.String(80),nullable=False),sa.Column('at',sa.DateTime(timezone=True),nullable=False))

def downgrade():
    tables=('m24_generation_events','m24_generation_budget_attempts','m24_generations','m24_generation_budgets')
    for table in tables:
        if op.get_bind().execute(sa.text('SELECT count(*) FROM '+table)).scalar():raise RuntimeError('populated generation ledger; destructive downgrade refused')
    for table in tables:op.drop_table(table)
