"""Owner review/continuation decisions and permanent typed keys; no backfill."""
from alembic import op
import sqlalchemy as sa
revision='20261010_m14_review_continue'
down_revision='20261010_m19_rank_snapshots'
branch_labels=None
depends_on=None
def upgrade():
    for table in ('m14_wave_reviews','m14_wave_continuations'):
        op.create_table(table,sa.Column('id',sa.String(36),primary_key=True),sa.Column('tenant_id',sa.String(120),nullable=False),sa.Column('actor_id',sa.String(120),nullable=False),sa.Column('payload',sa.JSON,nullable=False),sa.Column('digest',sa.String(64),nullable=False),sa.Column('approval_id',sa.String(36),nullable=False,unique=True),sa.Column('state',sa.String(30),nullable=False),sa.Column('decided_by',sa.String(120)),sa.Column('decided_at',sa.String(40)))
    op.create_table('m14_continuation_keys',sa.Column('id',sa.String(36),primary_key=True),sa.Column('project_key',sa.String(64),nullable=False),sa.Column('version',sa.Integer,nullable=False),sa.Column('prior_wave_id',sa.String(36),nullable=False),sa.Column('new_wave_id',sa.String(36),nullable=False,unique=True),sa.Column('owner_actor',sa.String(120),nullable=False),sa.Column('continuation_id',sa.String(36),nullable=False,unique=True),sa.Column('review_id',sa.String(36),nullable=False,unique=True),sa.Column('operation_type',sa.String(30),nullable=False),sa.UniqueConstraint('project_key','version'))
    op.create_index('ix_m14_continuation_keys_project_key','m14_continuation_keys',['project_key'])
def downgrade():
    op.drop_table('m14_continuation_keys');op.drop_table('m14_wave_continuations');op.drop_table('m14_wave_reviews')
