"""M20 clean-restart scheduler metadata."""
from alembic import op
import sqlalchemy as sa
revision = '20261007_m20_task_metadata'
down_revision = '20261007_m20_action_records'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('m20_tasks',sa.Column('runtime_metadata_json',sa.JSON(),nullable=False,server_default=sa.text("'{}'")))


def downgrade():
    with op.batch_alter_table('m20_tasks') as batch:
        batch.drop_column('runtime_metadata_json')
