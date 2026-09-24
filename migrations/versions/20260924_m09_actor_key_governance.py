"""M09 revision store: actor key governance columns + event log, immutable source-byte store.

m09_contradiction_revisions / m09_actor_keys were created ad hoc by create_all,
so they may or may not exist; this migration handles both.
"""
from alembic import op
import sqlalchemy as sa

revision = "20260924_m09_key_governance"
down_revision = "20260924_m10_attestation_ts"
branch_labels = None
depends_on = None

_KEY_COLUMNS = (
    ("active", sa.Boolean()),
    ("enrolled_by", sa.String(length=120)),
    ("retired_at", sa.DateTime(timezone=True)),
    ("retired_by", sa.String(length=120)),
    ("retire_reason", sa.String(length=300)),
    ("effective_from", sa.DateTime(timezone=True)),
    ("replaced_by_key_id", sa.String(length=64)),
)


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "m09_contradiction_revisions" not in tables:
        op.create_table(
            "m09_contradiction_revisions",
            sa.Column("pk", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.String(length=120), nullable=False, index=True),
            sa.Column("claim_norm", sa.String(length=500), nullable=False, index=True),
            sa.Column("seq", sa.Integer(), nullable=False),
            sa.Column("revision_id", sa.String(length=200), nullable=False),
            sa.Column("sha256", sa.String(length=64), nullable=False),
            sa.Column("previous_sha256", sa.String(length=64), nullable=True),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("signature_b64", sa.Text(), nullable=True),
            sa.Column("key_id", sa.String(length=64), nullable=True),
            sa.Column("stored_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("tenant_id", "claim_norm", "seq", name="uq_m09_rev_seq"),
            sa.UniqueConstraint("tenant_id", "revision_id", name="uq_m09_rev_id"),
        )
    if "m09_actor_keys" not in tables:
        op.create_table(
            "m09_actor_keys",
            sa.Column("pk", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.String(length=120), nullable=False, index=True),
            sa.Column("actor_id", sa.String(length=120), nullable=False, index=True),
            sa.Column("key_id", sa.String(length=64), nullable=False),
            sa.Column("public_key_b64", sa.Text(), nullable=False),
            sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
            *[sa.Column(n, t, nullable=True) for n, t in _KEY_COLUMNS],
            sa.UniqueConstraint("tenant_id", "actor_id", "key_id", name="uq_m09_actor_key"),
        )
    else:
        existing = {c["name"] for c in inspector.get_columns("m09_actor_keys")}
        for n, t in _KEY_COLUMNS:
            if n not in existing:
                op.add_column("m09_actor_keys", sa.Column(n, t, nullable=True))
        # Keys enrolled before governance stay active (NULL is read as active) and
        # are marked as legacy enrollments without proof-of-possession.
        op.execute("UPDATE m09_actor_keys SET enrolled_by = 'legacy-no-proof' WHERE enrolled_by IS NULL")
    if "m09_actor_key_events" not in tables:
        op.create_table(
            "m09_actor_key_events",
            sa.Column("pk", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.String(length=120), nullable=False, index=True),
            sa.Column("actor_id", sa.String(length=120), nullable=False, index=True),
            sa.Column("key_id", sa.String(length=64), nullable=False),
            sa.Column("event", sa.String(length=60), nullable=False),
            sa.Column("by", sa.String(length=120), nullable=False),
            sa.Column("details", sa.JSON(), nullable=False),
            sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        )
    if "m09_source_blobs" not in tables:
        op.create_table(
            "m09_source_blobs",
            sa.Column("pk", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.String(length=120), nullable=False, index=True),
            sa.Column("sha256", sa.String(length=64), nullable=False),
            sa.Column("content", sa.LargeBinary(), nullable=False),
            sa.Column("byte_count", sa.Integer(), nullable=False),
            sa.Column("first_uri", sa.Text(), nullable=False),
            sa.Column("stored_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("tenant_id", "sha256", name="uq_m09_source_blob"),
        )


def downgrade() -> None:
    op.drop_table("m09_source_blobs")
    op.drop_table("m09_actor_key_events")
    with op.batch_alter_table("m09_actor_keys") as batch:
        for n, _ in reversed(_KEY_COLUMNS):
            batch.drop_column(n)
