"""F4-b S1/S8: migration `0008_jobs_daily_prices` extends `ck_rbjobs_kind` with
`daily_prices`; round trip 0007 <-> 0008 and drift (SQLite; the `migrations-pg`
CI job runs the same revisions on PostgreSQL 18)."""
import pytest
from sqlalchemy.exc import IntegrityError

from tests.migration_helpers import downgrade, drift, inspector, rows, run, upgrade

INSERT = ("INSERT INTO riftbound.rbjobs (rbjob_kind, rbjob_status, rbjob_requested_at) "
          "VALUES (:kind, :status, '2030-01-01 12:00:00')")
COUNT = 'SELECT COUNT(*) FROM riftbound.rbjobs'


def _rejected(kind, status='queued'):
    before = rows(COUNT)
    with pytest.raises(IntegrityError):
        run(INSERT, kind=kind, status=status)
    assert rows(COUNT) == before


def test_head_accepts_daily_prices(migration_app):
    upgrade()
    assert rows('SELECT version_num FROM riftbound.alembic_version') == [
        ('0008_jobs_daily_prices',)]
    run(INSERT, kind='daily_prices', status='queued')
    run(INSERT, kind='heartbeat', status='queued')
    _rejected('nope')
    assert rows('SELECT rbjob_kind FROM riftbound.rbjobs ORDER BY rbjob_id') == [
        ('daily_prices',), ('heartbeat',)]


def test_round_trip_keeps_heartbeat_rows_and_has_no_drift(migration_app):
    upgrade()
    run(INSERT, kind='heartbeat', status='success')
    downgrade('0007_jobs')
    _rejected('daily_prices')
    run(INSERT, kind='heartbeat', status='queued')
    upgrade()
    assert rows('SELECT rbjob_kind, rbjob_status FROM riftbound.rbjobs ORDER BY rbjob_id') == [
        ('heartbeat', 'success'), ('heartbeat', 'queued')]
    assert drift() == []


def test_constraints_and_indexes_survive_the_upgrade(migration_app):
    upgrade()
    checks = {c['name'] for c in inspector().get_check_constraints('rbjobs', schema='riftbound')}
    assert {'ck_rbjobs_kind', 'ck_rbjobs_status'} <= checks
    indexes = {i['name'] for i in inspector().get_indexes('rbjobs', schema='riftbound')}
    assert {'ux_rbjobs_active_kind', 'ix_rbjobs_status_requested'} <= indexes
    run(INSERT, kind='daily_prices', status='running')
    _rejected('daily_prices', 'queued')
    _rejected('daily_prices', 'paused')


def test_downgrade_refuses_while_daily_prices_jobs_exist(migration_app):
    upgrade()
    run(INSERT, kind='daily_prices', status='success')
    with pytest.raises(RuntimeError) as caught:
        downgrade('0007_jobs')
    assert str(caught.value) == (
        "rbjobs holds 1 'daily_prices' job(s); the 0007_jobs CHECK does not allow them. "
        "Nothing was changed; delete them first "
        "(DELETE FROM riftbound.rbjobs WHERE rbjob_kind = 'daily_prices') and retry.")
    # nothing changed: still at 0008 and the row is still there
    assert rows('SELECT version_num FROM riftbound.alembic_version') == [
        ('0008_jobs_daily_prices',)]
    assert rows('SELECT rbjob_kind FROM riftbound.rbjobs') == [('daily_prices',)]
    run("DELETE FROM riftbound.rbjobs WHERE rbjob_kind = 'daily_prices'")
    downgrade('0007_jobs')
    _rejected('daily_prices')
