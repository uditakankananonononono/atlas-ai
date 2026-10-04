"""Persist the honest score state of M22 discovery candidates (exact ranking without scanning a capped row set)."""
from alembic import op
import sqlalchemy as sa
revision = '20261004_m22_score_state'
down_revision = '20261003_m19_runs'
branch_labels = None
depends_on = None
_Q = ("fit", "security", "maintenance", "novelty")


def _state(signals):
    # Mirrors pipeline._score_state. Rows written before `unmeasured` existed used fixed placeholder constants: never
    # assume complete. Missing key, null, non-list, non-string or unknown members are malformed => legacy_unverified.
    if not isinstance(signals, dict) or "unmeasured" not in signals:
        return "legacy_unverified"
    um = signals["unmeasured"]
    if not isinstance(um, list) or any(not isinstance(k, str) or k not in _Q for k in um):
        return "legacy_unverified"
    if not um:
        return "complete"
    return "unmeasured" if all(k in um for k in _Q) else "partial"


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    # Earlier m22 migrations build the table from the CURRENT ORM metadata, so on a fresh chain the column may already
    # exist; this migration is therefore idempotent (add column / index only when absent) and always backfills.
    if 'score_state' not in {c['name'] for c in insp.get_columns('m22_tool_candidates')}:
        op.add_column('m22_tool_candidates', sa.Column('score_state', sa.String(24), nullable=False, server_default='legacy_unverified'))
    if 'ix_m22_tool_candidates_tenant_state_score' not in {i['name'] for i in insp.get_indexes('m22_tool_candidates')}:
        op.create_index('ix_m22_tool_candidates_tenant_state_score', 'm22_tool_candidates', ['tenant_id', 'score_state', 'score'])
    table = sa.table('m22_tool_candidates', sa.column('pk', sa.Integer), sa.column('signals_json', sa.JSON), sa.column('score_state', sa.String))
    for pk, signals in bind.execute(sa.select(table.c.pk, table.c.signals_json)).fetchall():
        bind.execute(table.update().where(table.c.pk == pk).values(score_state=_state(signals)))


def downgrade():
    op.drop_index('ix_m22_tool_candidates_tenant_state_score', table_name='m22_tool_candidates')
    op.drop_column('m22_tool_candidates', 'score_state')
