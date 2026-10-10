"""Append-only human supersede authority and key versions; no auto resume."""
from alembic import op
import sqlalchemy as sa
revision='20261010_m14_wave_supersede'
down_revision='20261010_m05_m10_m15_tables'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('m14_wave_key_versions',sa.Column('id',sa.String(36),primary_key=True),sa.Column('project_key',sa.String(64),nullable=False),
        sa.Column('version',sa.Integer,nullable=False),sa.Column('prior_wave_id',sa.String(36),nullable=False),sa.Column('new_wave_id',sa.String(36),nullable=False,unique=True),
        sa.Column('admin_actor',sa.String(120),nullable=False),sa.Column('supersede_id',sa.String(36),nullable=False,unique=True),sa.Column('evidence',sa.JSON,nullable=False),sa.Column('created_at',sa.String(40),nullable=False),sa.UniqueConstraint('project_key','version'))
    op.create_index('ix_m14_wave_key_versions_project_key','m14_wave_key_versions',['project_key'])
    op.create_table('m14_wave_supersedes',sa.Column('id',sa.String(36),primary_key=True),sa.Column('tenant_id',sa.String(120),nullable=False),sa.Column('requester_actor',sa.String(120),nullable=False),
        sa.Column('payload',sa.JSON,nullable=False),sa.Column('digest',sa.String(64),nullable=False),sa.Column('approval_id',sa.String(36),nullable=False,unique=True),sa.Column('state',sa.String(40),nullable=False),
        sa.Column('approver_actor',sa.String(120)),sa.Column('approver_role',sa.String(40)),sa.Column('decided_at',sa.String(40)))

def downgrade():
    op.drop_table('m14_wave_supersedes');op.drop_table('m14_wave_key_versions')
