"""F4-b S2-S5/S8: the `daily_prices` job (loader, validation, clear-case
auto-match, review list), run through
`app.services.jobs` and `flask jobs run-pending`.

No network: `requests.get` inside the loader is replaced by `cardmarket_files`,
which serves the small files under tests/fixtures/cardmarket/ by URL."""
import json
from pathlib import Path

import pytest
import requests
import sqlalchemy as sa

from app import db
from app.models import (RbCard, RbJob, RbSet, RbcmIgnored, RbcmLoadHistory, RbcmPrice,
                        RbcmProduct, RbcmProductCardMap)
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


@pytest.fixture(autouse=True)
def no_follow_ups(monkeypatch):
    """This file is about the load and the matching; the job that follows a success is
    tested in test_value_snapshot_job.py (`queued` is [] here)."""
    from app.jobs import daily_prices as job
    monkeypatch.setattr(job, '_queue_follow_ups', lambda: [])


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


def seed_catalog():
    """Cards for the fixture products (tests/fixtures/cardmarket/singles.json):
    1001 matches 'Exact Card' by exact name (loader rule), 1002 is the only
    clear matcher case, 1003/1004 share a metacard, 1005 has no card, 1006 is
    ignored, 1007's slot is taken by product 999, 1008/1009 both want 008."""
    db.session.add(RbSet(rbset_id='OGN', rbset_name='Origins', rbset_ncard=10))
    for car_id, name, rarity in [('001', 'Exact Card', 'common'), ('002', 'Clear Hero', 'rare'),
                                 ('003', 'Twin Blade', 'common'),
                                 ('006', 'Ignored Thing', 'rare'), ('007', 'Taken Spot', 'rare'),
                                 ('008', 'Mirror Image', 'rare')]:
        db.session.add(RbCard(rbcar_rbset_id='OGN', rbcar_id=car_id, rbcar_name=name,
                              rbcar_type='Unit', rbcar_rarity=rarity))
    db.session.add(RbcmProductCardMap(rbpcm_id_product=999, rbpcm_rbset_id='OGN',
                                      rbpcm_rbcar_id='007', rbpcm_match_type='manual'))
    db.session.add(RbcmIgnored(rbig_id_product=1006, rbig_name='Ignored Thing (Promo)'))
    db.session.commit()


def mappings():
    db.session.expire_all()
    return [(m.rbpcm_id_product, m.rbpcm_rbset_id, m.rbpcm_rbcar_id, m.rbpcm_foil,
             m.rbpcm_match_type, float(m.rbpcm_confidence) if m.rbpcm_confidence else None)
            for m in db.session.execute(sa.select(RbcmProductCardMap)
                                        .order_by(RbcmProductCardMap.rbpcm_id_product)).scalars()]


SEEDED_MAP = [(999, 'OGN', '007', None, 'manual', None)]
EXACT_MAP = (1001, 'OGN', '001', None, 'auto', 1.0)
CLEAR_MAP = (1002, 'OGN', '002', None, 'auto', 0.7)


def _review(product_id, name, reason, *cards):
    return {'product_id': product_id, 'name': name, 'expansion_id': 6286, 'reason': reason,
            'candidates': [{'set': 'OGN', 'id': car_id, 'name': card_name}
                           for car_id, card_name in cards]}


REVIEW = [
    _review(1003, 'Twin Blade V.1', 'ambiguous', ('003', 'Twin Blade')),
    _review(1004, 'Twin Blade V.2', 'ambiguous', ('003', 'Twin Blade')),
    _review(1005, 'Nobody Known', 'no_candidates'),
    _review(1006, 'Ignored Thing (Promo)', 'ignored_pair', ('006', 'Ignored Thing')),
    _review(1007, 'Taken Spot (Showcase)', 'conflict', ('007', 'Taken Spot')),
    _review(1008, 'Mirror Image (Showcase)', 'conflict', ('008', 'Mirror Image')),
    _review(1009, 'Mirror Image (Promo)', 'conflict', ('008', 'Mirror Image')),
]


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


def test_success_links_the_clear_cases_and_lists_the_rest(app, cli, cardmarket_files):
    seed_yesterday()
    seed_catalog()
    job = run_job(cli)
    assert job.rbjob_result == {
        'validation': VALIDATION,
        # proposed: 1002, 1003, 1004, 1008, 1009 (1007 has no free slot)
        'auto_match': {'linked': 1, 'proposed': 5, 'review': 7},
        'review': REVIEW,
        'review_total': 7,
        'queued': [],
    }
    assert mappings() == [*SEEDED_MAP, EXACT_MAP, CLEAR_MAP]


def test_a_second_run_links_nothing_new_and_keeps_the_review(app, cli, cardmarket_files,
                                                             frozen_clock):
    seed_yesterday()
    seed_catalog()
    run_job(cli)
    frozen_clock.advance(hours=1)
    job = run_job(cli, job_id=2)
    assert job.rbjob_result['auto_match'] == {'linked': 0, 'proposed': 4, 'review': 7}
    assert job.rbjob_result['review'] == REVIEW
    assert mappings() == [*SEEDED_MAP, EXACT_MAP, CLEAR_MAP]


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


def test_a_loader_failure_runs_no_auto_match(app, cli, cardmarket_files, frozen_clock):
    seed_catalog()
    run_job(cli)                                   # first load of the day links 1001, 1002
    db.session.execute(sa.delete(RbcmProductCardMap).where(
        RbcmProductCardMap.rbpcm_id_product == 1002))
    db.session.commit()
    frozen_clock.advance(hours=1)
    cardmarket_files['price_guide'] = requests.Timeout('read timed out')
    job = run_job(cli, job_id=2, expected='error')
    assert job.rbjob_message == 'Download failed for price_guide: read timed out'
    # 1002 is still a clear case of today's products, but nothing linked it
    assert mappings() == [*SEEDED_MAP, EXACT_MAP]


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


def test_a_failed_validation_runs_no_auto_match(app, cli, cardmarket_files):
    seed_catalog()
    cardmarket_files['price_guide'] = {'priceGuides': []}
    run_job(cli, expected='error')
    # only the loader's exact-name rule linked a product; 1002 was not linked
    assert mappings() == [*SEEDED_MAP, EXACT_MAP]


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
    assert ran.rbjob_result['auto_match'] == {'linked': 0, 'proposed': 0, 'review': 9}
    assert {item['reason'] for item in ran.rbjob_result['review']} == {'no_candidates'}
    assert ran.rbjob_result['review_total'] == 9
