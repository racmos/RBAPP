"""F4-b S2/S3/S8: the `daily_prices` job (loader, validation), run through
`app.services.jobs` and `flask jobs run-pending`.

No network: `requests.get` inside the loader is replaced by `cardmarket_files`,
which serves the small files under tests/fixtures/cardmarket/ by URL."""
import json
from pathlib import Path

import pytest
import requests
import sqlalchemy as sa

from app import db
from app.models import (RbJob, RbcmLoadHistory, RbcmPrice, RbcmProduct,
                        RbcmProductCardMap)
from app.services import cardmarket_loader, jobs
from app.services.cardmarket_loader import CARDMARKET_URLS

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'cardmarket'
TODAY = '20300101'          # loader date under `frozen_clock`
YESTERDAY = '20291231'


def load_fixture(file_type):
    return json.loads((FIXTURES / f'{file_type}.json').read_text(encoding='utf-8'))


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


@pytest.fixture
def cardmarket_files(monkeypatch, frozen_clock):
    """Serve the fixture files by URL. `files[<file_type>]` can be replaced by a
    dict (served as JSON) or an exception (raised by `requests.get`).
    `files.calls` lists the requested URLs."""
    by_url = {url: file_type for file_type, url in CARDMARKET_URLS.items()}

    class Files(dict):
        calls = []

    files = Files({file_type: load_fixture(file_type) for file_type in CARDMARKET_URLS})
    files.calls = []

    def fake_get(url, timeout=None):
        files.calls.append(url)
        served = files[by_url[url]]
        if isinstance(served, Exception):
            raise served
        return _Response(served)

    monkeypatch.setattr(cardmarket_loader.requests, 'get', fake_get)
    return files


@pytest.fixture
def cli(app):
    runner = app.test_cli_runner(mix_stderr=False)

    def _invoke(*args):
        return runner.invoke(args=list(args))

    return _invoke


def seed_yesterday():
    """Product 1001 already existed yesterday, so it is not a new product today."""
    db.session.add(RbcmProduct(rbprd_date=YESTERDAY, rbprd_id_product=1001,
                               rbprd_name='Exact Card', rbprd_type='single'))
    db.session.commit()


def stored_job(job_id=1):
    db.session.expire_all()
    return db.session.get(RbJob, job_id)


def count(model, **filters):
    return db.session.execute(
        sa.select(sa.func.count()).select_from(model).filter_by(**filters)).scalar_one()


def run_job(cli, job_id=1, expected='success'):
    """Queue and run one daily_prices job through the CLI; returns the stored job."""
    assert cli('jobs', 'enqueue', 'daily_prices').stdout == f'Queued job {job_id} (daily_prices).\n'
    result = cli('jobs', 'run-pending')
    job = stored_job(job_id)
    outcome = expected if expected == 'success' else f'error: {job.rbjob_message}'
    assert (result.exit_code, result.stdout, result.stderr) == (
        0, f'Job {job_id} (daily_prices): {outcome}\nRan 1 job(s).\n', '')
    assert job.rbjob_status == expected
    return job


VALIDATION = {
    'date': TODAY,
    'files': {
        'price_guide': {'status': 'success', 'rows': 10},
        'singles': {'status': 'success', 'rows': 9},
        'nonsingles': {'status': 'success', 'rows': 1},
    },
    'price_rows': 10,
    'products_today': 10,
    'new_products': 9,
}


# --- success -----------------------------------------------------------------------

def test_success_loads_the_default_files_and_records_the_validation(app, cli,
                                                                    cardmarket_files):
    seed_yesterday()
    job = run_job(cli)
    assert cardmarket_files.calls == [CARDMARKET_URLS['price_guide'],
                                      CARDMARKET_URLS['singles'],
                                      CARDMARKET_URLS['nonsingles']]
    assert job.rbjob_result['validation'] == VALIDATION
    assert job.rbjob_message is None
    assert count(RbcmPrice, rbprc_date=TODAY) == 10
    assert count(RbcmProduct, rbprd_date=TODAY) == 10
    assert count(RbcmLoadHistory, rblh_date=TODAY) == 3


def test_a_second_run_the_same_day_reports_the_skipped_product_files(app, cli,
                                                                     cardmarket_files,
                                                                     frozen_clock):
    seed_yesterday()
    run_job(cli)
    frozen_clock.advance(hours=1)
    job = run_job(cli, job_id=2)
    assert job.rbjob_result['validation'] == {
        **VALIDATION,
        'files': {
            'price_guide': {'status': 'success', 'rows': 10},
            'singles': {'status': 'skipped', 'rows': 0},
            'nonsingles': {'status': 'skipped', 'rows': 0},
        },
    }
    assert count(RbcmPrice, rbprc_date=TODAY) == 10


# --- rejected input and loader failure ---------------------------------------------

def test_an_unknown_param_is_an_error_and_loads_nothing(app, cli, cardmarket_files):
    result = cli('jobs', 'enqueue', 'daily_prices', '--param', 'force=1')
    assert result.stdout == 'Queued job 1 (daily_prices).\n'
    result = cli('jobs', 'run-pending')
    assert (result.exit_code, result.stdout, result.stderr) == (
        0, 'Job 1 (daily_prices): error: daily_prices takes no params\nRan 1 job(s).\n', '')
    job = stored_job()
    assert (job.rbjob_status, job.rbjob_message, job.rbjob_result) == (
        'error', 'daily_prices takes no params', None)
    assert cardmarket_files.calls == []
    assert count(RbcmLoadHistory) == count(RbcmPrice) == count(RbcmProduct) == 0


def test_a_download_failure_is_an_error_with_the_loader_message(app, cli, cardmarket_files):
    cardmarket_files['singles'] = requests.ConnectionError('connection refused')
    job = run_job(cli, expected='error')
    assert job.rbjob_message == 'Download failed for singles: connection refused'
    assert job.rbjob_result is None
    assert count(RbcmLoadHistory) == count(RbcmPrice) == count(RbcmProduct) == 0


def test_a_loader_failure_without_an_error_text_still_fails(app, cli, cardmarket_files):
    cardmarket_files['nonsingles'] = {}       # empty file: the loader reports no error text
    job = run_job(cli, expected='error')
    assert job.rbjob_message == 'Cardmarket load failed'
    assert count(RbcmLoadHistory) == count(RbcmPrice) == 0


# --- validation failures -----------------------------------------------------------

def test_no_price_rows_fails_the_validation(app, cli, cardmarket_files):
    cardmarket_files['price_guide'] = {'priceGuides': []}
    job = run_job(cli, expected='error')
    assert job.rbjob_message == f'Validation failed: no price rows for {TODAY}'
    assert job.rbjob_result is None
    # the loader's own rows stay: the failure is about what it loaded
    assert count(RbcmProduct, rbprd_date=TODAY) == 10
    assert count(RbcmPrice) == 0


@pytest.mark.parametrize('missing', ['price_guide', 'singles', 'nonsingles'])
def test_a_file_without_a_history_row_fails_the_validation(app, cli, cardmarket_files,
                                                           monkeypatch, missing):
    record = cardmarket_loader.CardmarketLoader._record_history

    def record_all_but_one(loader, file_type, *args, **kwargs):
        if file_type != missing:
            record(loader, file_type, *args, **kwargs)

    monkeypatch.setattr(cardmarket_loader.CardmarketLoader, '_record_history',
                        record_all_but_one)
    job = run_job(cli, expected='error')
    assert job.rbjob_message == f'Validation failed: {missing} missing for {TODAY}'
    assert job.rbjob_result is None
    assert count(RbcmLoadHistory, rblh_file_type=missing) == 0


def test_a_history_row_of_another_day_does_not_count(app, cli, cardmarket_files, monkeypatch,
                                                     frozen_clock):
    db.session.add(RbcmLoadHistory(rblh_date=YESTERDAY, rblh_file_type='nonsingles',
                                   rblh_hash='x', rblh_rows=1, rblh_status='success'))
    db.session.commit()
    record = cardmarket_loader.CardmarketLoader._record_history
    monkeypatch.setattr(cardmarket_loader.CardmarketLoader, '_record_history',
                        lambda loader, file_type, *a, **k:
                        None if file_type == 'nonsingles' else record(loader, file_type, *a, **k))
    job = run_job(cli, expected='error')
    assert job.rbjob_message == f'Validation failed: nonsingles missing for {TODAY}'


def test_jobs_list_shows_one_row_per_job(app, cli, cardmarket_files):
    run_job(cli)
    lines = cli('jobs', 'list').stdout.splitlines()
    assert lines[1:] == ['1  daily_prices  success  2030-01-01 12:00:00  2030-01-01 12:00:00  -']


def test_service_level_run(app, cardmarket_files):
    jobs.enqueue('daily_prices')
    [ran] = jobs.run_pending()
    assert ran.rbjob_status == 'success'
    assert count(RbcmProductCardMap) == 0      # no cards in the catalog: nothing to link
