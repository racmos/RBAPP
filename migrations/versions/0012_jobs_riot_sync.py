"""Jobs: allow the riot_sync kind (F13-c, S9).

Same pattern as 0008 (F4-b): only the `ck_rbjobs_kind` CHECK changes; the
downgrade refuses while `riot_sync` jobs exist.

Revision ID: 0012_jobs_riot_sync
Revises: 0011_card_changes
Create Date: 2026-10-26

"""
from alembic import op
import sqlalchemy as sa
from alembic import context

# revision identifiers, used by Alembic.
revision = '0012_jobs_riot_sync'
down_revision = '0011_card_changes'
branch_labels = None
depends_on = None

SCHEMA = 'riftbound'
CHECK_NAME = 'ck_rbjobs_kind'
KINDS_BEFORE = ('heartbeat', 'daily_prices')
KINDS_AFTER = ('heartbeat', 'daily_prices', 'riot_sync')
ADDED_KIND = 'riot_sync'


def _check(kinds):
    return f"rbjob_kind IN ({', '.join(repr(k) for k in kinds)})"


def _replace_check(kinds):
    with op.batch_alter_table('rbjobs', schema=SCHEMA) as batch:
        batch.drop_constraint(CHECK_NAME, type_='check')
        batch.create_check_constraint(CHECK_NAME, _check(kinds))


def upgrade():
    _replace_check(KINDS_AFTER)


def downgrade():
    if context.is_offline_mode():
        raise RuntimeError(
            f'{revision} checks for {ADDED_KIND} jobs before the downgrade and cannot run '
            'in offline (--sql) mode. Run `flask db downgrade` against a live database.')
    found = op.get_bind().execute(
        sa.text(f'SELECT COUNT(*) FROM {SCHEMA}.rbjobs WHERE rbjob_kind = :kind'),
        {'kind': ADDED_KIND}).scalar_one()
    if found:
        raise RuntimeError(
            f"rbjobs holds {found} '{ADDED_KIND}' job(s); the {down_revision} CHECK does not "
            'allow them. Nothing was changed; delete them first '
            f"(DELETE FROM {SCHEMA}.rbjobs WHERE rbjob_kind = '{ADDED_KIND}') and retry.")
    _replace_check(KINDS_BEFORE)
