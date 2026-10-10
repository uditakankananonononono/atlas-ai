"""Empty immutable ranking-capture tables; no backfill or genesis."""
from alembic import op
import sqlalchemy as sa
revision='20261010_m19_rank_snapshots'
down_revision='20261010_m14_wave_supersede'
branch_labels=None
depends_on=None
def upgrade():
    op.create_table('m19_snapshot_counters',sa.Column('tenant_id',sa.String(120),primary_key=True),sa.Column('revision',sa.Integer,nullable=False))
    op.create_table('m19_ranking_snapshots',sa.Column('id',sa.String(36),primary_key=True),sa.Column('tenant_id',sa.String(120),nullable=False),sa.Column('actor_id',sa.String(120),nullable=False),sa.Column('revision',sa.Integer,nullable=False),sa.Column('parameters_hash',sa.String(64),nullable=False),sa.Column('payload',sa.JSON,nullable=False),sa.Column('content_hash',sa.String(64),nullable=False),sa.UniqueConstraint('tenant_id','revision'))
    op.create_index('ix_m19_ranking_snapshots_tenant_id','m19_ranking_snapshots',['tenant_id'])
    op.create_index('ix_m19_ranking_snapshots_parameters_hash','m19_ranking_snapshots',['parameters_hash'])
def downgrade():
    op.drop_table('m19_ranking_snapshots');op.drop_table('m19_snapshot_counters')
