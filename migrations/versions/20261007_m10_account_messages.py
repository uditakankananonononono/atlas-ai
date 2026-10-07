"""Scope provider message IDs to the connected Gmail account."""
from alembic import op
import sqlalchemy as sa
revision = '20261007_m10_account_messages'
down_revision = '20261007_m05_delivery_claims'
branch_labels = None
depends_on = None


def upgrade():
    constraints = sa.inspect(op.get_bind()).get_unique_constraints('m10_email_messages')
    if any(set(c['column_names']) == {'tenant_id', 'account_id', 'gmail_id'} for c in constraints):
        return
    # Naming convention permits SQLite's historical unnamed constraint to be removed.
    with op.batch_alter_table('m10_email_messages', naming_convention={'uq': 'uq_%(table_name)s_%(column_0_name)s_%(column_1_name)s'}) as batch:
        for c in constraints:
            if set(c['column_names']) == {'tenant_id', 'gmail_id'}:
                batch.drop_constraint(c['name'] or 'uq_m10_email_messages_tenant_id_gmail_id', type_='unique')
        batch.create_unique_constraint('uq_m10_account_message', ['tenant_id', 'account_id', 'gmail_id'])


def downgrade():
    duplicates = op.get_bind().execute(sa.text('SELECT tenant_id, gmail_id FROM m10_email_messages GROUP BY tenant_id, gmail_id HAVING count(*) > 1 LIMIT 1')).first()
    if duplicates:
        raise RuntimeError('Cannot downgrade account-scoped messages without losing account data')
    with op.batch_alter_table('m10_email_messages') as batch:
        batch.drop_constraint('uq_m10_account_message', type_='unique')
        batch.create_unique_constraint('uq_m10_email_messages_tenant_id_gmail_id', ['tenant_id', 'gmail_id'])
