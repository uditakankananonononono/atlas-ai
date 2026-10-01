"""Immutable discovery review binding and one-shot promotion receipts."""
from alembic import op
import sqlalchemy as sa

revision = '20261001_discovery_approval'
down_revision = '20260927_m21_owner_journal'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('discovery_approval_bindings',
        sa.Column('candidate_id', sa.Integer(), primary_key=True),
        sa.Column('approval_id', sa.String(36), nullable=False, unique=True),
        sa.Column('tenant_id', sa.String(120), nullable=False),
        sa.Column('scope_sha256', sa.String(64), nullable=False))
    op.create_table('discovery_approval_uses',
        sa.Column('approval_id', sa.String(36), primary_key=True),
        sa.Column('candidate_id', sa.Integer(), nullable=False, unique=True),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=False))
    dialect = op.get_bind().dialect.name
    if dialect == 'sqlite':
        for table in ('discovery_approval_bindings', 'discovery_approval_uses'):
            for operation in ('UPDATE', 'DELETE'):
                op.execute(f"CREATE TRIGGER {table}_no_{operation.lower()} BEFORE {operation} ON {table} "
                           "BEGIN SELECT RAISE(ABORT, 'immutable discovery approval record'); END")
    elif dialect == 'postgresql':
        op.execute("""CREATE FUNCTION discovery_approval_immutable() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'immutable discovery approval record'; END;
        $$ LANGUAGE plpgsql""")
        for table in ('discovery_approval_bindings', 'discovery_approval_uses'):
            op.execute(f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
                       "FOR EACH ROW EXECUTE FUNCTION discovery_approval_immutable()")
    else:
        raise RuntimeError('discovery approval immutability requires SQLite or PostgreSQL')


def downgrade():
    op.drop_table('discovery_approval_uses')
    op.drop_table('discovery_approval_bindings')
    if op.get_bind().dialect.name == 'postgresql':
        op.execute('DROP FUNCTION discovery_approval_immutable()')
