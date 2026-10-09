"""Inactive M24 write-ahead tables, legacy quarantine; never enables dispatch."""
from alembic import op
import sqlalchemy as sa
revision='20261009_m24_write_ahead'
down_revision='20261008_m20_chroma_jobs'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('m24_dispatch_cutover',sa.Column('id',sa.Integer,primary_key=True),sa.Column('protocol_epoch',sa.Integer,nullable=False),
        sa.Column('state',sa.String(40),nullable=False),sa.Column('verification_digest',sa.String(64)),sa.Column('verified_at',sa.DateTime(timezone=True)),
        sa.CheckConstraint('protocol_epoch IN (0,2)'))
    op.execute(sa.text("INSERT INTO m24_dispatch_cutover (id,protocol_epoch,state) VALUES (1,0,'locked')"))
    op.create_table('m24_provider_operations',
        sa.Column('id',sa.String(36),primary_key=True),sa.Column('tenant_id',sa.String(120),nullable=False),
        sa.Column('approval_id',sa.String(36),nullable=False),sa.Column('request_hash',sa.String(64),nullable=False),
        sa.Column('request',sa.JSON,nullable=False),sa.Column('action_type',sa.String(120),nullable=False),
        sa.Column('provider_account',sa.String(200),nullable=False),sa.Column('environment',sa.String(20),nullable=False),
        sa.Column('api_version',sa.String(80),nullable=False),sa.Column('provider_key',sa.String(255),nullable=False),
        sa.Column('protocol_epoch',sa.Integer,nullable=False),sa.Column('state',sa.String(40),nullable=False),
        sa.Column('fence',sa.String(36)),sa.Column('lease_until',sa.DateTime(timezone=True)),
        sa.Column('first_attempt_at',sa.DateTime(timezone=True)),sa.Column('dispatch_not_after',sa.DateTime(timezone=True)),
        sa.Column('result',sa.JSON),sa.Column('failure',sa.String(80)),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('tenant_id','approval_id'),sa.UniqueConstraint('provider_account','environment','provider_key'),
        sa.CheckConstraint("environment = 'test'"),sa.CheckConstraint('protocol_epoch = 2'))
    for name,column in [('tenant_id','tenant_id'),('approval_id','approval_id')]:
        op.create_index('ix_m24_provider_operations_'+name,'m24_provider_operations',[column])
    op.create_table('m24_provider_attempts',sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('operation_id',sa.String(36),nullable=False),sa.Column('fence',sa.String(36),nullable=False,unique=True),
        sa.Column('request_hash',sa.String(64),nullable=False),sa.Column('started_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_m24_provider_attempts_operation_id','m24_provider_attempts',['operation_id'])
    op.create_table('m24_operation_events',sa.Column('id',sa.Integer,primary_key=True,autoincrement=True),
        sa.Column('operation_id',sa.String(36),nullable=False),sa.Column('event',sa.String(80),nullable=False),
        sa.Column('actor',sa.String(120),nullable=False),sa.Column('at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_m24_operation_events_operation_id','m24_operation_events',['operation_id'])
    op.create_table('m24_legacy_quarantine',sa.Column('approval_id',sa.String(36),primary_key=True),
        sa.Column('tenant_id',sa.String(120),nullable=False),sa.Column('classification',sa.String(80),nullable=False),
        sa.Column('approval_time',sa.DateTime(timezone=True)),sa.Column('recorded_result',sa.JSON),
        sa.Column('inventoried_at',sa.DateTime(timezone=True),nullable=False))
    # Cross-dialect classification in Python; no state becomes ready and no provider keys are invented.
    from datetime import datetime,timezone,timedelta
    now=datetime.now(timezone.utc);connection=op.get_bind()
    rows=connection.execute(sa.text("SELECT a.id,a.user_id,a.decided_at,e.result FROM m00_approval_requests a LEFT JOIN m24_billing_executions e ON e.approval_id=a.id WHERE a.module_id=24 AND a.status='approved'"))
    table=sa.table('m24_legacy_quarantine',sa.column('approval_id',sa.String),sa.column('tenant_id',sa.String),
        sa.column('classification',sa.String),sa.column('approval_time',sa.DateTime(timezone=True)),
        sa.column('recorded_result',sa.JSON),sa.column('inventoried_at',sa.DateTime(timezone=True)))
    import json
    for ident,tenant,when,result in rows:
        if isinstance(when,str):when=datetime.fromisoformat(when)
        if when is not None and when.tzinfo is None:when=when.replace(tzinfo=timezone.utc)
        if isinstance(result,str):result=json.loads(result)
        kind='legacy-recorded' if result is not None else 'legacy-unknown-time' if when is None else 'legacy-unknown-under24h' if now-when<timedelta(hours=24) else 'legacy-unknown-over24h'
        connection.execute(table.insert().values(approval_id=ident,tenant_id=tenant,classification=kind,approval_time=when,recorded_result=result,inventoried_at=now))

def downgrade():
    for name in ('m24_provider_operations','m24_provider_attempts','m24_operation_events','m24_legacy_quarantine'):
        if op.get_bind().execute(sa.text('SELECT count(*) FROM '+name)).scalar():
            raise RuntimeError('populated M24 durability evidence; destructive downgrade refused')
    for name in ('m24_legacy_quarantine','m24_operation_events','m24_provider_attempts','m24_provider_operations','m24_dispatch_cutover'):
        op.drop_table(name)
