"""F4-g-2: the `price_alerts` job, its CLI enqueue and its queueing after `daily_prices`."""
import pytest
import sqlalchemy as sa

from app import db
from app.jobs import daily_prices as daily_prices_job
from app.jobs import registry
from app.jobs.registry import JobFailed
from app.models import RbJob, RbWishlistAlert
from app.services import jobs as jobs_service
from tests.test_wishlist_alerts_service import make_line, make_list
from tests.wishlist_helpers import seed_catalog


def kinds_queued():
    db.session.expire_all()
    return [(j.rbjob_kind, j.rbjob_status, j.rbjob_params) for j in db.session.execute(
        sa.select(RbJob).order_by(RbJob.rbjob_id)).scalars()]


def test_kind_is_registered_with_a_900_second_timeout():
    kind = registry.get('price_alerts')
    assert kind is not None and kind.timeout_seconds == 900


def test_params_fail(app):
    with pytest.raises(JobFailed) as caught:
        registry.get('price_alerts').handler({'date': '20261020'})
    assert str(caught.value) == 'price_alerts takes no params'


def test_run_raises_the_alerts_through_the_runner(app, make_user, frozen_clock):
    make_user('testuser')
    seed_catalog()
    make_line(make_list(), '1', foil='N', max_price=10)
    job = jobs_service.enqueue('price_alerts')
    jobs_service.run_pending()
    db.session.expire_all()
    done = db.session.get(RbJob, job.rbjob_id)
    assert done.rbjob_status == 'success'
    assert done.rbjob_result == {'price_date': '2026-10-20', 'lines_checked': 1,
                                 'cards_checked': 1, 'alerts_created': 1,
                                 'skipped_no_price': 0}
    assert db.session.execute(sa.select(sa.func.count()).select_from(
        RbWishlistAlert)).scalar_one() == 1


def test_a_second_run_the_same_price_date_creates_nothing(app, make_user, frozen_clock):
    make_user('testuser')
    seed_catalog()
    make_line(make_list(), '1', foil='N', max_price=10)
    for _ in range(2):
        job = jobs_service.enqueue('price_alerts')
        jobs_service.run_pending()
    db.session.expire_all()
    assert db.session.get(RbJob, job.rbjob_id).rbjob_result['alerts_created'] == 0
    assert db.session.execute(sa.select(sa.func.count()).select_from(
        RbWishlistAlert)).scalar_one() == 1


def test_no_price_load_fails_the_job(app):
    job = jobs_service.enqueue('price_alerts')
    jobs_service.run_pending()
    db.session.expire_all()
    done = db.session.get(RbJob, job.rbjob_id)
    assert (done.rbjob_status, done.rbjob_message) == (
        'error', 'price_alerts: no Cardmarket prices loaded')


def test_the_cli_queues_it(app):
    runner = app.test_cli_runner(mix_stderr=False)
    result = runner.invoke(args=['jobs', 'enqueue', 'price_alerts'])
    assert (result.exit_code, result.stdout, result.stderr) == (
        0, 'Queued job 1 (price_alerts).\n', '')
    assert kinds_queued() == [('price_alerts', 'queued', {})]


# --- chaining after daily_prices ---------------------------------------------------------

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


def test_daily_prices_queues_the_alerts_last(app, loaded):
    result = daily_prices_job.run({})
    assert result['queued'] == ['value_snapshot', 'products_refresh', 'price_alerts']
    assert kinds_queued() == [('value_snapshot', 'queued', {}),
                              ('products_refresh', 'queued', {}),
                              ('price_alerts', 'queued', {})]


def test_an_active_alerts_job_is_skipped_and_the_others_still_queued(app, loaded, caplog):
    caplog.set_level('INFO')
    jobs_service.enqueue('price_alerts')
    result = daily_prices_job.run({})
    assert result['queued'] == ['value_snapshot', 'products_refresh']
    assert [kind for kind, _, _ in kinds_queued()].count('price_alerts') == 1
    assert 'price_alerts not queued' in caplog.text


def test_alerts_that_cannot_be_queued_never_fail_the_load(app, loaded, monkeypatch):
    real = jobs_service.enqueue

    def flaky(kind, *args, **kwargs):
        if kind == 'price_alerts':
            raise RuntimeError('database went away')
        return real(kind, *args, **kwargs)
    monkeypatch.setattr(jobs_service, 'enqueue', flaky)
    result = daily_prices_job.run({})
    assert result['queued'] == ['value_snapshot', 'products_refresh']
    assert result['validation'] == {'date': '20300101'}


def test_a_failed_load_queues_no_alerts(app, monkeypatch):
    monkeypatch.setattr(daily_prices_job.CardmarketLoader, 'run',
                        lambda self: {'success': False, 'errors': ['boom']})
    with pytest.raises(JobFailed):
        daily_prices_job.run({})
    assert kinds_queued() == []
