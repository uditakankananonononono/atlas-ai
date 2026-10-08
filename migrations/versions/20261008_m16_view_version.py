"""M16 dashboard view: integer version column for compare-and-set saves."""
from alembic import op
import sqlalchemy as sa
revision = '20261008_m16_view_version'
down_revision = '20261008_m10_account_scope'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('m16_view_prefs', sa.Column('version', sa.Integer(), nullable=False, server_default='0'))


def downgrade():
    op.drop_column('m16_view_prefs', 'version')
