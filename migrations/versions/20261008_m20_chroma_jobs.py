"""Add pending/completed durable Chroma fact index jobs."""
from alembic import op
import sqlalchemy as sa
revision='20261008_m20_chroma_jobs'
down_revision='20261008_m16_m20_subscriber'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('m20_chroma_index_jobs',
        sa.Column('tenant_id',sa.String(120),primary_key=True),
        sa.Column('fact_id',sa.String(120),primary_key=True),
        sa.Column('model_id',sa.String(200),nullable=False),
        sa.Column('content_hash',sa.String(64),nullable=False),
        sa.Column('complete',sa.Boolean(),nullable=False,server_default=sa.false()))

def downgrade():
    op.drop_table('m20_chroma_index_jobs')
