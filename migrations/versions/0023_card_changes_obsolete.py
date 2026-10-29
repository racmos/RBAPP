"""Card changes: allow the obsolete status (owner feedback 2026-10-29, S17).

`flask riot recheck-pending` marks the pending proposals the sync rules no longer
produce as `obsolete` instead of deleting them. Only `rbcardchanges_status_chk`
changes (same pattern as 0020 for the job kinds); no data changes on upgrade.

The downgrade refuses while `obsolete` rows exist: the 0022 CHECK does not allow
them and turning them into `rejected` would make the sync skip those values for
good (a rejected value is never proposed again). Decide what they become first
(for example `UPDATE riftbound.rbcardchanges SET rbchg_status = 'rejected'
WHERE rbchg_status = 'obsolete'`) and retry.

Revision ID: 0023_card_changes_obsolete
Revises: 0022_snapshot_products_value
Create Date: 2026-10-29

"""
from alembic import op
import sqlalchemy as sa
from alembic import context

# revision identifiers, used by Alembic.
revision = '0023_card_changes_obsolete'
down_revision = '0022_snapshot_products_value'
branch_labels = None
depends_on = None

SCHEMA = 'riftbound'
CHECK_NAME = 'rbcardchanges_status_chk'
STATUSES_BEFORE = ('pending', 'approved', 'rejected')
STATUSES_AFTER = ('pending', 'approved', 'rejected', 'obsolete')
ADDED_STATUS = 'obsolete'


def _check(statuses):
    return f"rbchg_status IN ({', '.join(repr(s) for s in statuses)})"


def _replace_check(statuses):
    with op.batch_alter_table('rbcardchanges', schema=SCHEMA) as batch:
        batch.drop_constraint(CHECK_NAME, type_='check')
        batch.create_check_constraint(CHECK_NAME, _check(statuses))


def upgrade():
    _replace_check(STATUSES_AFTER)


def downgrade():
    if context.is_offline_mode():
        raise RuntimeError(
            f'{revision} checks for {ADDED_STATUS} changes before the downgrade and cannot '
            'run in offline (--sql) mode. Run `flask db downgrade` against a live database.')
    found = op.get_bind().execute(
        sa.text(f'SELECT COUNT(*) FROM {SCHEMA}.rbcardchanges WHERE rbchg_status = :status'),
        {'status': ADDED_STATUS}).scalar_one()
    if found:
        raise RuntimeError(
            f"rbcardchanges holds {found} '{ADDED_STATUS}' change(s); the {down_revision} "
            'CHECK does not allow them. Nothing was changed; set their status first '
            f"(UPDATE {SCHEMA}.rbcardchanges SET rbchg_status = 'rejected' "
            f"WHERE rbchg_status = '{ADDED_STATUS}') and retry.")
    _replace_check(STATUSES_BEFORE)
