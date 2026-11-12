"""F4-g-1 (F4-R4): migration `0027_jobs_price_alerts`: the `ck_rbjobs_kind` CHECK allows the
`price_alerts` kind; the downgrade refuses while such jobs exist, like 0020 (SQLite;
`migrations-pg` runs them on PostgreSQL 18)."""
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.job import JOB_KINDS
from tests.migration_helpers import downgrade, drift, rows, run, upgrade

BEFORE = '0026_wishlists'
KIND = '0027_jobs_price_alerts'
OLD_KINDS = ('heartbeat', 'daily_prices', 'riot_sync', 'value_snapshot', 'products_refresh')
JOB = ("INSERT INTO riftbound.rbjobs (rbjob_kind, rbjob_status, rbjob_requested_at) "
       "VALUES (:kind, :status, '2030-01-01 12:00:00')")


def kinds():
    return rows('SELECT rbjob_kind FROM riftbound.rbjobs ORDER BY rbjob_id')


def test_the_model_allows_price_alerts():
    assert JOB_KINDS == OLD_KINDS + ('price_alerts',)


def test_kind_check_accepts_price_alerts(migration_app):
    upgrade(BEFORE)
    with pytest.raises(IntegrityError):
        run(JOB, kind='price_alerts', status='queued')
    upgrade(KIND)
    run(JOB, kind='price_alerts', status='queued')
    assert kinds() == [('price_alerts',)]


@pytest.mark.parametrize('kind', OLD_KINDS)
def test_the_other_kinds_still_insert(migration_app, kind):
    upgrade(KIND)
    run(JOB, kind=kind, status='queued')
    assert kinds() == [(kind,)]


def test_an_unknown_kind_is_still_rejected(migration_app):
    upgrade(KIND)
    with pytest.raises(IntegrityError):
        run(JOB, kind='nope', status='queued')
    assert kinds() == []


def test_round_trip_and_drift(migration_app):
    upgrade()
    assert drift() == []
    downgrade(BEFORE)
    with pytest.raises(IntegrityError):
        run(JOB, kind='price_alerts', status='queued')
    run(JOB, kind='products_refresh', status='success')
    upgrade()
    assert drift() == []
    run(JOB, kind='price_alerts', status='queued')
    assert kinds() == [('products_refresh',), ('price_alerts',)]


def test_kind_downgrade_refuses_while_such_jobs_exist(migration_app):
    upgrade(KIND)
    run(JOB, kind='daily_prices', status='success')
    run(JOB, kind='price_alerts', status='success')
    run(JOB, kind='price_alerts', status='error')
    with pytest.raises(RuntimeError) as caught:
        downgrade(BEFORE)
    message = str(caught.value)
    assert "rbjobs holds 2 'price_alerts' job(s)" in message
    assert 'Nothing was changed' in message
    assert ("DELETE FROM riftbound.rbjobs WHERE rbjob_kind = 'price_alerts'" in message)
    assert kinds() == [('daily_prices',), ('price_alerts',), ('price_alerts',)]
    # The CHECK still allows the kind: nothing was changed.
    run(JOB, kind='price_alerts', status='queued')
    run("DELETE FROM riftbound.rbjobs WHERE rbjob_kind = 'price_alerts'")
    downgrade(BEFORE)
    assert kinds() == [('daily_prices',)]
    with pytest.raises(IntegrityError):
        run(JOB, kind='price_alerts', status='queued')


def test_revision_chain():
    import importlib.util
    from pathlib import Path
    versions = Path(__file__).resolve().parents[1] / 'migrations' / 'versions'
    spec = importlib.util.spec_from_file_location('m_0027', versions / f'{KIND}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert (module.revision, module.down_revision) == (KIND, BEFORE)
