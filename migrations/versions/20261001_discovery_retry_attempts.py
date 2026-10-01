"""Versioned immutable discovery attempts, preserving legacy review history."""
from alembic import op
import sqlalchemy as sa

revision = '20261001_discovery_retry'
down_revision = '20261001_discovery_approval'
branch_labels = None
depends_on = None


def _guards():
    dialect = op.get_bind().dialect.name
    if dialect == 'postgresql':
        op.execute("""CREATE OR REPLACE FUNCTION discovery_approval_immutable() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'immutable discovery approval record' USING ERRCODE = '23000'; END;
        $$ LANGUAGE plpgsql""")
    for table in ('discovery_approval_bindings', 'discovery_approval_uses'):
        if dialect == 'sqlite':
            for operation in ('UPDATE', 'DELETE'):
                op.execute(f"CREATE TRIGGER {table}_no_{operation.lower()} BEFORE {operation} ON {table} "
                           "BEGIN SELECT RAISE(ABORT, 'immutable discovery approval record'); END")
        elif dialect == 'postgresql':
            op.execute(f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
                       "FOR EACH ROW EXECUTE FUNCTION discovery_approval_immutable()")
        else:
            raise RuntimeError('discovery approval immutability requires SQLite or PostgreSQL')


def upgrade():
    op.create_table('discovery_bindings_new',
        sa.Column('approval_id', sa.String(36), primary_key=True),
        sa.Column('candidate_id', sa.Integer(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('source_key', sa.String(300), nullable=False),
        sa.Column('target_source_id', sa.Integer(), nullable=True),
        sa.Column('tenant_id', sa.String(120), nullable=False),
        sa.Column('scope_sha256', sa.String(64), nullable=False),
        sa.UniqueConstraint('candidate_id', 'version'))
    # Old scopes lack attempt_version/operation, so remain audit history only:
    # promotion fails closed on their hash until a fresh review is requested.
    op.execute("""INSERT INTO discovery_bindings_new
        (approval_id,candidate_id,version,source_key,target_source_id,tenant_id,scope_sha256)
        SELECT b.approval_id,b.candidate_id,1,'tracked:' || c.platform,NULL,b.tenant_id,b.scope_sha256
        FROM discovery_approval_bindings b JOIN discovery_candidates c ON c.id=b.candidate_id""")
    op.create_table('discovery_uses_new',
        sa.Column('approval_id', sa.String(36), primary_key=True),
        sa.Column('candidate_id', sa.Integer(), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=False))
    op.execute('INSERT INTO discovery_uses_new SELECT * FROM discovery_approval_uses')
    op.drop_table('discovery_approval_uses')
    op.drop_table('discovery_approval_bindings')
    op.rename_table('discovery_bindings_new', 'discovery_approval_bindings')
    op.rename_table('discovery_uses_new', 'discovery_approval_uses')
    op.create_index('ix_discovery_approval_bindings_candidate_id', 'discovery_approval_bindings', ['candidate_id'])
    op.create_index('ix_discovery_approval_uses_candidate_id', 'discovery_approval_uses', ['candidate_id'])
    _guards()


def downgrade():
    # Refuse a lossy downgrade rather than deleting owner-review audit history.
    raise RuntimeError('versioned approval history requires an explicit audited rollback; restore a pre-upgrade backup')
