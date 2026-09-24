"""M10 trusted timestamps: attestation timestamp tokens + retired-key validity cutoff."""
from alembic import op
import sqlalchemy as sa

revision = "20260924_m10_attestation_ts"
down_revision = "20260924_m22_install_pipeline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = {c["name"] for c in inspector.get_columns("m10_reviewer_public_keys")}
    if "signatures_valid_before" not in existing:
        op.add_column("m10_reviewer_public_keys", sa.Column("signatures_valid_before", sa.DateTime(timezone=True), nullable=True))
        # Keys retired before this migration: their retirement time is the cutoff.
        op.execute("UPDATE m10_reviewer_public_keys SET signatures_valid_before = retired_at WHERE active = false AND retired_at IS NOT NULL")
    if "m10_attestation_timestamps" not in set(inspector.get_table_names()):
        op.create_table(
            "m10_attestation_timestamps",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.String(length=120), nullable=False, index=True),
            sa.Column("reviewer_id", sa.String(length=200), nullable=False),
            sa.Column("key_id", sa.String(length=200), nullable=False),
            sa.Column("attestation_sha256", sa.String(length=64), nullable=False, index=True),
            sa.Column("scheme", sa.String(length=30), nullable=False),
            sa.Column("authority", sa.String(length=200), nullable=False),
            sa.Column("token", sa.LargeBinary(), nullable=False),
            sa.Column("gen_time", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("tenant_id", "attestation_sha256", "scheme"),
        )


def downgrade() -> None:
    op.drop_table("m10_attestation_timestamps")
    op.drop_column("m10_reviewer_public_keys", "signatures_valid_before")
