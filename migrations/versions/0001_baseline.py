"""Baseline marker for databases created before Alembic adoption.

Production bootstrap uses `alembic upgrade head`; a first clean deployment is
created from the checked SQLAlchemy metadata by the bootstrap script, then
stamped here. Subsequent schema edits must be explicit revisions.
"""
revision="0001_baseline";down_revision=None;branch_labels=None;depends_on=None
def upgrade(): pass
def downgrade(): pass
