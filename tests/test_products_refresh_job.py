"""F14-a S5 (AC4): the `products_refresh` job, its params and its chaining after
`daily_prices` (after `value_snapshot`)."""
import pytest
import sqlalchemy as sa

from app import db
from app.jobs import daily_prices as daily_prices_job
from app.jobs import registry
from app.jobs.registry import JobFailed
from app.models import RbcmProduct, RbJob, RbProducts
from app.models.job import JOB_KINDS
from app.services import jobs as jobs_service


def cm(day, product_id, type_='nonsingle'):
    db.session.add(RbcmProduct(rbprd_date=day, rbprd_id_product=product_id,
                               rbprd_name=f'Product {product_id}',
                               rbprd_category_name='Riftbound Booster', rbprd_type=type_))


def catalog():
    db.session.expire_all()
    return db.session.execute(sa.select(RbProducts.rbpdt_id_product, RbProducts.rbpdt_listed)
                              .order_by(RbProducts.rbpdt_id_product)).all()


def kinds_queued():
    return [(j.rbjob_kind, j.rbjob_status, j.rbjob_params) for j in db.session.execute(
        sa.select(RbJob).order_by(RbJob.rbjob_id)).scalars()]


@pytest.fixture
def two_days(app):
    cm('20300101', 1)
    cm('20300101', 2)
    cm('20300102', 2)
    cm('20300102', 3)
    cm('20300103', 9, type_='single')     # the latest date holds only a single
    db.session.commit()


def handler(params):
    return registry.get('products_refresh').handler(params)


def test_kind_is_registered_with_a_600_second_timeout():
    kind = registry.get('products_refresh')
    assert kind is not None and kind.timeout_seconds == 600
    assert 'products_refresh' in JOB_KINDS


def test_the_default_date_is_the_latest_cardmarket_date(app, frozen_clock):
    cm('20300101', 1)
    cm('20300102', 2)
    db.session.commit()
    assert handler({}) == {'date': '20300102', 'new': 1, 'updated': 0, 'not_listed': 0,
                           'total': 1}
    assert catalog() == [(2, True)]


def test_the_latest_date_without_non_singles_fails_and_changes_nothing(two_days, frozen_clock):
    handler({'date': '20300101'})
    with pytest.raises(JobFailed) as caught:
        handler({})
    assert str(caught.value) == 'products_refresh: no non-single products for 20300103'
    assert catalog() == [(1, True), (2, True)]


def test_a_date_param_picks_that_day(two_days, frozen_clock):
    handler({'date': '20300101'})
    assert handler({'date': '20300102'}) == {'date': '20300102', 'new': 1, 'updated': 0,
                                             'not_listed': 1, 'total': 3}
    assert catalog() == [(1, False), (2, True), (3, True)]


def test_nothing_loaded_fails(app):
    with pytest.raises(JobFailed) as caught:
        handler({})
    assert str(caught.value) == 'products_refresh: no Cardmarket products loaded'


@pytest.mark.parametrize('params, message', [
    ({'date': '2030-01-01'}, 'products_refresh: date must be YYYYMMDD'),
    ({'date': '20301301'}, 'products_refresh: date must be YYYYMMDD'),
    ({'date': ''}, 'products_refresh: date must be YYYYMMDD'),
    ({'date': 20300101}, 'products_refresh: date must be YYYYMMDD'),
    ({'force': '1'}, 'products_refresh: unknown params: force'),
    ({'date': '20300101', 'a': '1', 'b': '2'}, 'products_refresh: unknown params: a, b'),
])
def test_bad_params_fail_and_change_nothing(two_days, params, message):
    with pytest.raises(JobFailed) as caught:
        handler(params)
    assert str(caught.value) == message
    assert catalog() == []


def test_run_through_the_runner(two_days, frozen_clock):
    job = jobs_service.enqueue('products_refresh', {'date': '20300102'})
    jobs_service.run_pending()
    db.session.expire_all()
    done = db.session.get(RbJob, job.rbjob_id)
    assert (done.rbjob_status, done.rbjob_result) == (
        'success', {'date': '20300102', 'new': 2, 'updated': 0, 'not_listed': 0, 'total': 2})


def test_the_cli_queues_it_with_a_date(app):
    runner = app.test_cli_runner(mix_stderr=False)
    result = runner.invoke(args=['jobs', 'enqueue', 'products_refresh', '--param',
                                 'date=20300102'])
    assert (result.exit_code, result.stdout, result.stderr) == (
        0, 'Queued job 1 (products_refresh).\n', '')
    assert kinds_queued() == [('products_refresh', 'queued', {'date': '20300102'})]


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


def test_daily_prices_queues_the_snapshot_then_the_refresh(app, loaded):
    result = daily_prices_job.run({})
    assert result['queued'] == ['value_snapshot', 'products_refresh']
    assert kinds_queued() == [('value_snapshot', 'queued', {}),
                              ('products_refresh', 'queued', {})]


def test_an_active_refresh_is_skipped_and_the_snapshot_still_queued(app, loaded, caplog):
    caplog.set_level('INFO')
    jobs_service.enqueue('products_refresh')
    result = daily_prices_job.run({})
    assert result['queued'] == ['value_snapshot']
    assert kinds_queued() == [('products_refresh', 'queued', {}),
                              ('value_snapshot', 'queued', {})]
    assert 'products_refresh not queued' in caplog.text


def test_an_active_snapshot_does_not_stop_the_refresh(app, loaded):
    jobs_service.enqueue('value_snapshot')
    result = daily_prices_job.run({})
    assert result['queued'] == ['products_refresh']
    assert kinds_queued() == [('value_snapshot', 'queued', {}),
                              ('products_refresh', 'queued', {})]


def test_a_snapshot_that_cannot_be_queued_does_not_stop_the_refresh(app, loaded, monkeypatch):
    real = jobs_service.enqueue

    def flaky(kind, *args, **kwargs):
        if kind == 'value_snapshot':
            raise RuntimeError('database went away')
        return real(kind, *args, **kwargs)
    monkeypatch.setattr(jobs_service, 'enqueue', flaky)
    result = daily_prices_job.run({})
    assert result['queued'] == ['products_refresh']
    assert result['validation'] == {'date': '20300101'}
    assert kinds_queued() == [('products_refresh', 'queued', {})]


def test_a_refresh_that_cannot_be_queued_never_fails_the_load(app, loaded, monkeypatch):
    real = jobs_service.enqueue

    def flaky(kind, *args, **kwargs):
        if kind == 'products_refresh':
            raise RuntimeError('database went away')
        return real(kind, *args, **kwargs)
    monkeypatch.setattr(jobs_service, 'enqueue', flaky)
    result = daily_prices_job.run({})
    assert result['queued'] == ['value_snapshot']
    assert kinds_queued() == [('value_snapshot', 'queued', {})]


def test_a_failed_load_queues_no_refresh(app, monkeypatch):
    monkeypatch.setattr(daily_prices_job.CardmarketLoader, 'run',
                        lambda self: {'success': False, 'errors': ['boom']})
    with pytest.raises(JobFailed):
        daily_prices_job.run({})
    assert kinds_queued() == []
