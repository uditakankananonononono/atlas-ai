"""Alembic coverage for six M05/M10/M15 tables previously auto-provisioned by create_all.

Revision history: the first submitted revision id (20261010_m05_m10_m15_uncovered_tables,
37 chars) exceeded the Postgres alembic_version.version_num VARCHAR(32) limit; the peer
observed a real StringDataRightTruncation on their old head (SQLite hides it) and rejected
it. Historical builder NOT RUN; peer observed the old head fail on PG; peer's narrow rename
probe passed upgrade/downgrade/re-upgrade; the new fix awaits re-audit. This renamed revision
(20261010_m05_m10_m15_tables, 28 chars) is not claimed PG-passed.

m05 pair: INTEGRATION8 conversion intent confirmed; m10/m15 four: no
intentional-omission note found (absence is not proof), strategy policy applied.

Authored PREP-NORUN: never executed against any database by the author. Schemas
transcribed by reading the ORM rows at base efa5649f7cbee5800e1cb38d0d38fbd3e5c55eca;
PG/SQLite type fidelity unverified. Constructor Base.metadata.create_all calls are
retained for dev/test per docs/DATABASE_STRATEGY.md. Named unique constraints are an
authoring choice (ORM leaves them unnamed); index names follow ix_<table>_<column>.
"""
from alembic import op
import sqlalchemy as sa
revision='20261010_m05_m10_m15_tables'
down_revision='20261010_m14_sandbox_wave'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('m05_cadence_policies',
        sa.Column('pk',sa.Integer,primary_key=True,autoincrement=True),
        sa.Column('tenant_id',sa.String(120),nullable=False),
        sa.Column('version',sa.Integer,nullable=False),
        sa.Column('rules',sa.JSON,nullable=False),
        sa.Column('live_thread_days',sa.Integer,nullable=False),
        sa.Column('actor',sa.String(200),nullable=False),
        sa.Column('reason',sa.String(2000),nullable=False),
        sa.Column('at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_m05_cadence_policies_tenant_id','m05_cadence_policies',['tenant_id'])
    op.create_table('m05_delivery_claims',
        sa.Column('pk',sa.Integer,primary_key=True,autoincrement=True),
        sa.Column('tenant_id',sa.String(120),nullable=False),
        sa.Column('message_id',sa.String(36),nullable=False),
        sa.Column('snapshot',sa.JSON,nullable=False),
        sa.UniqueConstraint('tenant_id','message_id',name='uq_m05_delivery_claims_tenant_message'))
    op.create_table('m10_promise_snapshots',
        sa.Column('pk',sa.Integer,primary_key=True,autoincrement=True),
        sa.Column('tenant_id',sa.String(120),nullable=False),
        sa.Column('thread_id',sa.String(300),nullable=False),
        sa.Column('snapshot_sha256',sa.String(64),nullable=False),
        sa.Column('previous_snapshot_sha256',sa.String(64),nullable=False),
        sa.Column('snapshot',sa.JSON,nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('tenant_id','thread_id',name='uq_m10_promise_snapshots_tenant_thread'))
    op.create_index('ix_m10_promise_snapshots_tenant_id','m10_promise_snapshots',['tenant_id'])
    op.create_index('ix_m10_promise_snapshots_thread_id','m10_promise_snapshots',['thread_id'])
    op.create_table('m10_promise_source_messages',
        sa.Column('id',sa.Integer,primary_key=True,autoincrement=True),
        sa.Column('tenant_id',sa.String(120),nullable=False),
        sa.Column('message_id',sa.String(200),nullable=False),
        sa.Column('content_sha256',sa.String(64),nullable=False),
        sa.Column('content_bytes',sa.LargeBinary,nullable=False),
        sa.Column('persisted_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('tenant_id','message_id',name='uq_m10_promise_source_messages_tenant_message'))
    op.create_index('ix_m10_promise_source_messages_tenant_id','m10_promise_source_messages',['tenant_id'])
    op.create_index('ix_m10_promise_source_messages_message_id','m10_promise_source_messages',['message_id'])
    op.create_table('m15_provider_publication_receipts',
        sa.Column('id',sa.Integer,primary_key=True,autoincrement=True),
        sa.Column('tenant_id',sa.String(120),nullable=False),
        sa.Column('approval_id',sa.String(200),nullable=False),
        sa.Column('version_id',sa.String(200),nullable=False),
        sa.Column('provider',sa.String(200),nullable=False),
        sa.Column('object_key',sa.String(1000),nullable=False),
        sa.Column('published_sha256',sa.String(64),nullable=False),
        sa.Column('payload',sa.JSON,nullable=False),
        sa.Column('persisted_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('tenant_id','approval_id',name='uq_m15_provider_publication_receipts_tenant_approval'),
        sa.UniqueConstraint('tenant_id','provider','object_key',name='uq_m15_provider_publication_receipts_tenant_provider_object'))
    op.create_index('ix_m15_provider_publication_receipts_tenant_id','m15_provider_publication_receipts',['tenant_id'])
    op.create_table('m15_publication_provider_keys',
        sa.Column('id',sa.Integer,primary_key=True,autoincrement=True),
        sa.Column('tenant_id',sa.String(120),nullable=False),
        sa.Column('provider',sa.String(200),nullable=False),
        sa.Column('key_id',sa.String(200),nullable=False),
        sa.Column('public_key',sa.LargeBinary,nullable=False),
        sa.Column('fingerprint_sha256',sa.String(64),nullable=False),
        sa.Column('active',sa.Boolean,nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('retired_at',sa.DateTime(timezone=True),nullable=True),
        sa.UniqueConstraint('tenant_id','provider','key_id',name='uq_m15_publication_provider_keys_tenant_provider_key'))
    op.create_index('ix_m15_publication_provider_keys_tenant_id','m15_publication_provider_keys',['tenant_id'])

def downgrade():
    for table in ('m15_publication_provider_keys','m15_provider_publication_receipts','m10_promise_source_messages',
                  'm10_promise_snapshots','m05_delivery_claims','m05_cadence_policies'):
        op.drop_table(table)
