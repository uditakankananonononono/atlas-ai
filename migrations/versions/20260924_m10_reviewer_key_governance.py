"""M10 reviewer key governance: key table (if absent), governance columns, event log.

The key table was previously created ad hoc by create_all, so it may or may not
exist in a given database; this migration handles both.
"""
from alembic import op
import sqlalchemy as sa

revision = "20260924_m10_reviewer_keys"
down_revision = "20260924_m01_nlp_provenance"
branch_labels = None
depends_on = None

_NEW_COLUMNS = (
    ("enrolled_by", sa.String(length=200)),
    ("retired_by", sa.String(length=200)),
    ("retire_reason", sa.String(length=300)),
    ("replaced_by_key_id", sa.String(length=200)),
)


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "m10_reviewer_public_keys" not in tables:
        op.create_table(
            "m10_reviewer_public_keys",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.String(length=120), nullable=False, index=True),
            sa.Column("reviewer_id", sa.String(length=200), nullable=False),
            sa.Column("key_id", sa.String(length=200), nullable=False),
            sa.Column("public_key", sa.LargeBinary(), nullable=False),
            sa.Column("fingerprint_sha256", sa.String(length=64), nullable=False),
            sa.Column("active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
            *[sa.Column(name, kind, nullable=True) for name, kind in _NEW_COLUMNS],
            sa.UniqueConstraint("tenant_id", "reviewer_id", "key_id"),
        )
    else:
        existing = {c["name"] for c in inspector.get_columns("m10_reviewer_public_keys")}
        for name, kind in _NEW_COLUMNS:
            if name not in existing:
                op.add_column("m10_reviewer_public_keys", sa.Column(name, kind, nullable=True))
    if "m10_reviewer_key_events" not in tables:
        op.create_table(
            "m10_reviewer_key_events",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.String(length=120), nullable=False, index=True),
            sa.Column("reviewer_id", sa.String(length=200), nullable=False, index=True),
            sa.Column("key_id", sa.String(length=200), nullable=False),
            sa.Column("event", sa.String(length=60), nullable=False),
            sa.Column("actor", sa.String(length=200), nullable=False),
            sa.Column("details", sa.JSON(), nullable=False),
            sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("m10_reviewer_key_events")
    for name, _ in reversed(_NEW_COLUMNS):
        op.drop_column("m10_reviewer_public_keys", name)
