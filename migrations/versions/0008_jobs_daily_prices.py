"""jobs: allow the daily_prices kind

Spec S1 of F4-b (docs/requirements/F4/F4-b-daily-prices.md).

`ck_rbjobs_kind` grows from `('heartbeat')` to `('heartbeat', 'daily_prices')`
(the job registered in `app/jobs/daily_prices.py`). No data changes.

The downgrade restores `('heartbeat')` and therefore refuses to run while
`daily_prices` jobs exist: delete them first (runbook "Scheduled jobs").
SQLite rebuilds the table in batch mode; PostgreSQL drops and re-creates the
CHECK.

Revision ID: 0008_jobs_daily_prices
Revises: 0007_jobs
Create Date: 2026-10-24

"""
from alembic import context, op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0008_jobs_daily_prices'
down_revision = '0007_jobs'
branch_labels = None
depends_on = None

SCHEMA = 'riftbound'
CHECK_NAME = 'ck_rbjobs_kind'
KINDS_BEFORE = ('heartbeat',)
KINDS_AFTER = ('heartbeat', 'daily_prices')
ADDED_KIND = 'daily_prices'


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
