"""Jobs: allow the price_alerts kind (F4-g-1, F4-R4).

Same pattern as 0008, 0012, 0017 and 0020: only the `ck_rbjobs_kind` CHECK changes; the
downgrade refuses while `price_alerts` jobs exist. The handler is registered by F4-g-2.

Revision ID: 0027_jobs_price_alerts
Revises: 0026_wishlists
Create Date: 2026-11-12

"""
from alembic import op
import sqlalchemy as sa
from alembic import context

# revision identifiers, used by Alembic.
revision = '0027_jobs_price_alerts'
down_revision = '0026_wishlists'
branch_labels = None
depends_on = None

SCHEMA = 'riftbound'
CHECK_NAME = 'ck_rbjobs_kind'
KINDS_BEFORE = ('heartbeat', 'daily_prices', 'riot_sync', 'value_snapshot', 'products_refresh')
KINDS_AFTER = ('heartbeat', 'daily_prices', 'riot_sync', 'value_snapshot', 'products_refresh',
               'price_alerts')
ADDED_KIND = 'price_alerts'


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
