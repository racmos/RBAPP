"""F4-c S3, S4 (AC2): the `value_snapshot` job and its chaining after `daily_prices`."""
from datetime import date

import pytest
import sqlalchemy as sa

from app import db
from app.jobs import daily_prices as daily_prices_job
from app.jobs import registry
from app.jobs.registry import JobFailed
from app.models import RbJob, RbValueSnapshot
from app.services import jobs as jobs_service
from tests.collection_read_helpers import seed_catalog, seed_lines


def active_snapshot_jobs():
    return db.session.execute(sa.select(RbJob).where(
        RbJob.rbjob_kind == 'value_snapshot')).scalars().all()


def test_kind_is_registered_with_a_900_second_timeout():
    kind = registry.get('value_snapshot')
    assert kind is not None and kind.timeout_seconds == 900


def test_unknown_params_fail(app):
    with pytest.raises(JobFailed) as caught:
        registry.get('value_snapshot').handler({'force': '1'})
    assert str(caught.value) == 'value_snapshot takes no params'


def test_run_stores_todays_rows_through_the_runner(app, make_user, frozen_clock):
    make_user('testuser')
    make_user('otheruser')
    seed_catalog()
    seed_lines()
    job = jobs_service.enqueue('value_snapshot')
    jobs_service.run_pending()
    db.session.expire_all()
    done = db.session.get(RbJob, job.rbjob_id)
    assert done.rbjob_status == 'success'
    assert done.rbjob_result == {'date': '2030-01-01', 'users': 2, 'rows': 2,
                                 'total_value': 215.0}
    days = db.session.execute(sa.select(RbValueSnapshot.rbvsn_date).distinct()).scalars().all()
    assert days == [date(2030, 1, 1)]


@pytest.fixture
def loaded(monkeypatch):
    """`daily_prices` with the heavy steps replaced: a successful load."""
    monkeypatch.setattr(daily_prices_job.CardmarketLoader, 'run',
                        lambda self: {'success': True, 'date': '20300101'})
    monkeypatch.setattr(daily_prices_job.daily_prices, 'validate_load',
                        lambda date_: {'date': date_})
    monkeypatch.setattr(daily_prices_job.daily_prices, 'match_clear_cases',
                        lambda date_: {'auto_match': {'linked': 0, 'proposed': 0, 'review': 0},
                                       'review': [], 'review_total': 0})


def test_daily_prices_success_queues_the_snapshot(app, loaded):
    result = daily_prices_job.run({})
    assert result['queued'] == ['value_snapshot']
    jobs = active_snapshot_jobs()
    assert [(j.rbjob_status, j.rbjob_params) for j in jobs] == [('queued', {})]


def test_an_active_snapshot_job_is_ignored(app, loaded, caplog):
    caplog.set_level('INFO')
    jobs_service.enqueue('value_snapshot')
    result = daily_prices_job.run({})
    assert result['queued'] == []
    assert len(active_snapshot_jobs()) == 1
    assert 'value_snapshot' in caplog.text


def test_a_failure_to_queue_never_fails_daily_prices(app, loaded, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError('database went away')
    monkeypatch.setattr(jobs_service, 'enqueue', boom)
    result = daily_prices_job.run({})
    assert result['queued'] == []
    assert result['validation'] == {'date': '20300101'}


def test_a_failed_load_queues_nothing(app, monkeypatch):
    monkeypatch.setattr(daily_prices_job.CardmarketLoader, 'run',
                        lambda self: {'success': False, 'errors': ['boom']})
    with pytest.raises(JobFailed):
        daily_prices_job.run({})
    assert active_snapshot_jobs() == []


def test_a_failed_validation_queues_nothing(app, monkeypatch):
    monkeypatch.setattr(daily_prices_job.CardmarketLoader, 'run',
                        lambda self: {'success': True, 'date': '20300101'})

    def invalid(date_):
        raise daily_prices_job.daily_prices.ValidationFailed('too few rows')
    monkeypatch.setattr(daily_prices_job.daily_prices, 'validate_load', invalid)
    with pytest.raises(JobFailed):
        daily_prices_job.run({})
    assert active_snapshot_jobs() == []
