"""M10: Gmail ids unique per (tenant, account); drafts bound to source account."""
from alembic import op
import sqlalchemy as sa

revision = '20261008_m10_account_scope'
down_revision = '20261007_m20_model_unknown'
branch_labels = None
depends_on = None

_NC = {"uq": "uq_%(table_name)s_%(column_0_name)s"}


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == 'sqlite':
        with op.batch_alter_table('m10_email_messages', recreate='always',
                                  naming_convention=_NC) as b:
            b.drop_constraint('uq_m10_email_messages_tenant_id', type_='unique')
            b.create_unique_constraint('uq_m10_email_messages_tenant_account_gmail',
                                       ['tenant_id', 'account_id', 'gmail_id'])
    else:
        op.drop_constraint('m10_email_messages_tenant_id_gmail_id_key',
                           'm10_email_messages', type_='unique')
        op.create_unique_constraint('uq_m10_email_messages_tenant_account_gmail',
                                    'm10_email_messages', ['tenant_id', 'account_id', 'gmail_id'])
    op.add_column('m10_email_drafts', sa.Column('account_id', sa.String(length=36), nullable=True))
    op.create_index(op.f('ix_m10_email_drafts_account_id'), 'm10_email_drafts', ['account_id'])
    op.execute(
        "UPDATE m10_email_drafts SET account_id = (SELECT m.account_id FROM m10_email_messages m "
        "WHERE m.tenant_id = m10_email_drafts.tenant_id AND m.id = m10_email_drafts.message_id)")


def downgrade():
    op.drop_index(op.f('ix_m10_email_drafts_account_id'), table_name='m10_email_drafts')
    with op.batch_alter_table('m10_email_drafts') as b:
        b.drop_column('account_id')
    # Not restoring (tenant, gmail_id) uniqueness: per-account rows may now legitimately collide.
