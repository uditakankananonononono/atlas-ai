"""Atomic tenant-key reservation, separate use deadline, append-only audit.

Runtime PostgreSQL role must be non-owner and must not inherit an owner role.
ATLAS_M00_RUNTIME_ROLE optionally revokes existing mutation grants at upgrade.
"""
import os
from alembic import op
import sqlalchemy as sa

revision = "20261001_m00_atomic_permits"
down_revision = "20260927_m21_owner_journal"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    orphan = bind.execute(sa.text("SELECT COUNT(*) FROM m00_approval_idempotency i LEFT JOIN m00_approval_requests r ON r.id=i.approval_id WHERE r.id IS NULL")).scalar()
    if orphan:
        raise RuntimeError("orphan idempotency rows require operator reconciliation")
    op.add_column("m00_approval_requests", sa.Column("approved_use_by", sa.DateTime(timezone=True), nullable=True))
    op.add_column("m00_approval_requests", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
    # Existing approvals intentionally remain non-consumable until re-reviewed.
    # A migration cannot silently grant fresh authority to historical approvals.
    op.create_table("m00_approval_idempotency_v2",
        sa.Column("tenant_id", sa.String(120), primary_key=True),
        sa.Column("key", sa.String(200), primary_key=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("approval_id", sa.String(36), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    bind.execute(sa.text("INSERT INTO m00_approval_idempotency_v2 (tenant_id,key,request_hash,approval_id,created_at) SELECT r.user_id,i.key,i.request_hash,i.approval_id,i.created_at FROM m00_approval_idempotency i JOIN m00_approval_requests r ON r.id=i.approval_id"))
    op.drop_table("m00_approval_idempotency")
    op.rename_table("m00_approval_idempotency_v2", "m00_approval_idempotency")
    op.create_index("ix_m00_approval_idempotency_approval_id", "m00_approval_idempotency", ["approval_id"])
    if bind.dialect.name == "sqlite":
        for operation in ("UPDATE", "DELETE"):
            bind.execute(sa.text(f"CREATE TRIGGER m00_events_no_{operation.lower()} BEFORE {operation} ON m00_approval_events BEGIN SELECT RAISE(ABORT, 'approval audit is append-only'); END"))
    elif bind.dialect.name == "postgresql":
        bind.execute(sa.text("CREATE OR REPLACE FUNCTION m00_audit_append_only() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'approval audit is append-only'; END $$"))
        bind.execute(sa.text("CREATE TRIGGER m00_audit_no_mutation BEFORE UPDATE OR DELETE OR TRUNCATE ON m00_approval_events FOR EACH STATEMENT EXECUTE FUNCTION m00_audit_append_only()"))
        bind.execute(sa.text("REVOKE UPDATE, DELETE, TRUNCATE ON m00_approval_events FROM PUBLIC"))
        role = os.getenv("ATLAS_M00_RUNTIME_ROLE")
        if role:
            quoted = bind.dialect.identifier_preparer.quote_identifier(role)
            bind.execute(sa.text(f"REVOKE UPDATE, DELETE, TRUNCATE ON m00_approval_events FROM {quoted}"))
            bind.execute(sa.text(f"GRANT SELECT, INSERT ON m00_approval_events TO {quoted}"))


def downgrade():
    # Colliding per-tenant keys cannot be merged back into a global key safely.
    raise RuntimeError("security migration is forward-only; restore a reviewed backup for rollback")
