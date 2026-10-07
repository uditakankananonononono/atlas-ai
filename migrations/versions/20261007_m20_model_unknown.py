"""Persist unresolved model holds; loss of unresolved uncertainty is refused."""
from alembic import op
import sqlalchemy as sa
revision = "20261007_m20_model_unknown"
down_revision = "20261007_m20_risk_register"
branch_labels = None
depends_on = None

def upgrade():
    if "model_outcome_unknown" not in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("m20_tasks")}:
        op.add_column("m20_tasks", sa.Column("model_outcome_unknown", sa.Boolean(), nullable=False, server_default=sa.false()))

def downgrade():
    count = op.get_bind().execute(sa.text("SELECT count(*) FROM m20_tasks WHERE model_outcome_unknown = true")).scalar()
    if count: raise RuntimeError("Cannot remove unresolved M20 model outcome holds")
    with op.batch_alter_table("m20_tasks") as batch:
        batch.drop_column("model_outcome_unknown")
