"""Empty tenant meta-state snapshots; no cognition/backfill claim."""
from alembic import op
import sqlalchemy as sa
revision='20261011_m20_meta_state'
down_revision='20261010_m14_local_dispatch'
branch_labels=None
depends_on=None
def upgrade():
    op.create_table('m20_meta_state',sa.Column('tenant_id',sa.String(120),primary_key=True),sa.Column('kind',sa.String(32),primary_key=True),sa.Column('revision',sa.Integer,nullable=False),sa.Column('payload',sa.JSON,nullable=False))
def downgrade():op.drop_table('m20_meta_state')
