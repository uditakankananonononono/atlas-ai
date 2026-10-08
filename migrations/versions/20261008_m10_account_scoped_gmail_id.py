"""M10: Gmail ids unique per (tenant, account); drafts bound to source account.

State-aware in both directions (inspects what exists), so up -> down -> up works.
Downgrade restores the old (tenant_id, gmail_id) uniqueness and refuses, with a
clear error, if per-account rows now collide on it."""
from alembic import op
import sqlalchemy as sa

revision = '20261008_m10_account_scope'
down_revision = '20261008_m16_identity_forward'
branch_labels = None
depends_on = None

MSG = 'm10_email_messages'
DRAFT = 'm10_email_drafts'
OLD_COLS = ['tenant_id', 'gmail_id']
NEW_COLS = ['tenant_id', 'account_id', 'gmail_id']
OLD_NAME = 'uq_m10_email_messages_tenant_id'
NEW_NAME = 'uq_m10_email_messages_tenant_account_gmail'
_NC = {"uq": "uq_%(table_name)s_%(column_0_name)s"}


def _uniques():
    insp = sa.inspect(op.get_bind())
    return {tuple(u['column_names']): u.get('name') for u in insp.get_unique_constraints(MSG)}


def _draft_cols():
    return {c['name'] for c in sa.inspect(op.get_bind()).get_columns(DRAFT)}


def _draft_indexes():
    return {i['name'] for i in sa.inspect(op.get_bind()).get_indexes(DRAFT)}


def _swap(drop_cols, add_cols, add_name):
    """Drop the unique over drop_cols (if present) and create add_cols (if absent)."""
    uniques = _uniques()
    drop_name = uniques.get(tuple(drop_cols), 'MISSING')
    create = tuple(add_cols) not in uniques
    drop = drop_name != 'MISSING'
    if not drop and not create:
        return
    if op.get_bind().dialect.name == 'sqlite':
        with op.batch_alter_table(MSG, recreate='always', naming_convention=_NC) as b:
            if drop:
                b.drop_constraint(drop_name or 'uq_m10_email_messages_tenant_id', type_='unique')
            if create:
                b.create_unique_constraint(add_name, add_cols)
    else:
        if drop:
            op.drop_constraint(drop_name or 'm10_email_messages_tenant_id_gmail_id_key',
                               MSG, type_='unique')
        if create:
            op.create_unique_constraint(add_name, MSG, add_cols)


def upgrade():
    _swap(OLD_COLS, NEW_COLS, NEW_NAME)
    if 'account_id' not in _draft_cols():
        op.add_column(DRAFT, sa.Column('account_id', sa.String(length=36), nullable=True))
    if op.f('ix_m10_email_drafts_account_id') not in _draft_indexes():
        op.create_index(op.f('ix_m10_email_drafts_account_id'), DRAFT, ['account_id'])
    # Backfill only rows not yet bound (re-upgrade after downgrade is idempotent).
    op.execute(
        f"UPDATE {DRAFT} SET account_id = (SELECT m.account_id FROM {MSG} m "
        f"WHERE m.tenant_id = {DRAFT}.tenant_id AND m.id = {DRAFT}.message_id) "
        f"WHERE account_id IS NULL")


def downgrade():
    bind = op.get_bind()
    dup = bind.execute(sa.text(
        f"SELECT tenant_id, gmail_id FROM {MSG} GROUP BY tenant_id, gmail_id "
        f"HAVING COUNT(*) > 1 LIMIT 1")).fetchone()
    if dup is not None:
        raise RuntimeError(
            "Cannot downgrade: the same gmail_id exists in more than one account of a "
            f"tenant (e.g. tenant={dup[0]!r}, gmail_id={dup[1]!r}); old (tenant_id, gmail_id) "
            "uniqueness cannot be restored without deleting mail. Resolve manually.")
    _swap(NEW_COLS, OLD_COLS, OLD_NAME)
    if op.f('ix_m10_email_drafts_account_id') in _draft_indexes():
        op.drop_index(op.f('ix_m10_email_drafts_account_id'), table_name=DRAFT)
    if 'account_id' in _draft_cols():
        with op.batch_alter_table(DRAFT) as b:
            b.drop_column('account_id')
