"""Persist the honest score state of M22 discovery candidates (exact ranking without scanning a capped row set)."""
from alembic import op
import sqlalchemy as sa
revision = '20261004_m22_score_state'
down_revision = '20261003_m19_runs'
branch_labels = None
depends_on = None
_Q = ("fit", "security", "maintenance", "novelty")


def _state(signals):
    # Rows written before `unmeasured` existed used fixed placeholder constants: never assume they were complete.
    if not isinstance(signals, dict) or "unmeasured" not in signals:
        return "legacy_unverified"
    um = signals.get("unmeasured") or []
    if not um:
        return "complete"
    return "unmeasured" if all(k in um for k in _Q) else "partial"


def upgrade():
    op.add_column('m22_tool_candidates', sa.Column('score_state', sa.String(24), nullable=False, server_default='legacy_unverified'))
    op.create_index('ix_m22_tool_candidates_tenant_state_score', 'm22_tool_candidates', ['tenant_id', 'score_state', 'score'])
    table = sa.table('m22_tool_candidates', sa.column('pk', sa.Integer), sa.column('signals_json', sa.JSON), sa.column('score_state', sa.String))
    bind = op.get_bind()
    for pk, signals in bind.execute(sa.select(table.c.pk, table.c.signals_json)).fetchall():
        bind.execute(table.update().where(table.c.pk == pk).values(score_state=_state(signals)))


def downgrade():
    op.drop_index('ix_m22_tool_candidates_tenant_state_score', table_name='m22_tool_candidates')
    op.drop_column('m22_tool_candidates', 'score_state')
