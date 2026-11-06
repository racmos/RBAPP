"""CM-a: the admin log of the daily Cardmarket load (API only).

`GET /admin/cardmarket/loads`, `GET /admin/cardmarket/loads/<date>`,
`GET /admin/cardmarket/status` and `POST /admin/cardmarket/load`, computed on
read from `rbcm_load_history`, `rbcm_products`, `rbcm_price`, the matching
tables and the `daily_prices` jobs."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import event

from app import db
from app.models import (RbcmExpansion, RbcmIgnored, RbcmLoadHistory, RbcmPrice, RbcmProduct,
                        RbcmProductCardMap, RbJob)
from app.models.audit import RbAdminAudit
from tests.test_authz_matrix import classify

BASE = '/riftbound/api/v1/admin/cardmarket'
LOADS = f'{BASE}/loads'
STATUS = f'{BASE}/status'
LOAD = f'{BASE}/load'
D1, D2, D3 = '20291230', '20291231', '20300101'      # D3 = today under `frozen_clock`


def iso(day):
    return f'{day[:4]}-{day[4:6]}-{day[6:]}'


def at(day, hour=6, minute=30, second=0):
    return datetime(int(day[:4]), int(day[4:6]), int(day[6:]), hour, minute, second)


def history(day, file_type, status='success', rows=10, message=None, loaded_at=None):
    db.session.add(RbcmLoadHistory(
        rblh_date=day, rblh_file_type=file_type, rblh_hash=f'h-{day}-{file_type}',
        rblh_rows=rows, rblh_status=status, rblh_message=message or f'{file_type} {status}',
        rblh_loaded_at=loaded_at or at(day)))


def full_load(day, loaded_at=None):
    for file_type in ('price_guide', 'singles', 'nonsingles'):
        history(day, file_type, loaded_at=loaded_at)


def product(day, product_id, name=None, type_='single', category='Riftbound Single'):
    db.session.add(RbcmProduct(rbprd_date=day, rbprd_id_product=product_id,
                               rbprd_name=name or f'Product {product_id}',
                               rbprd_category_name=category, rbprd_type=type_))


def price(day, product_id, low):
    db.session.add(RbcmPrice(rbprc_date=day, rbprc_id_product=product_id, rbprc_low=low))


def job(status='success', started=None, finished=None, result=None, kind='daily_prices',
        requested=None):
    row = RbJob(rbjob_kind=kind, rbjob_status=status, rbjob_params={},
                rbjob_requested_at=requested or started or at(D3),
                rbjob_started_at=started, rbjob_finished_at=finished, rbjob_result=result)
    db.session.add(row)
    db.session.commit()
    return row


def data(resp, status=200):
    assert resp.status_code == status, resp.get_json()
    return resp.get_json()['data']


def items(client, query=''):
    return data(client.get(f'{LOADS}{query}'))['items']


def by_date(client, query=''):
    return {item['date']: item for item in items(client, query)}


@pytest.fixture
def three_days(app):
    """D1 {1, 2, 3}; D2 {2, 3, 4, 5} (1 removed, 4 and 5 new); D3 {2, 3, 4, 5, 6} (6 new)."""
    for day in (D1, D2, D3):
        full_load(day)
    for pid in (1, 2, 3):
        product(D1, pid)
    for pid in (2, 3, 4, 5):
        product(D2, pid)
    for pid in (2, 3, 4, 5, 6):
        product(D3, pid)
    db.session.commit()
    return app


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------

class TestAuthorization:
    @pytest.mark.parametrize('url', [LOADS, f'{LOADS}/2030-01-01', STATUS])
    def test_reads_anonymous_401_user_403_admin_passes(self, app, authenticated_client,
                                                       admin_client, three_days, url):
        assert app.test_client().get(url).status_code == 401
        assert authenticated_client.get(url).status_code == 403
        assert admin_client.get(url).status_code == 200

    def test_load_anonymous_401_user_403(self, app, authenticated_client):
        assert app.test_client().post(LOAD).status_code == 401
        assert authenticated_client.post(LOAD).status_code == 403
        assert RbJob.query.count() == 0

    def test_the_four_rules_are_admin_in_the_matrix(self, app):
        wanted = {('/riftbound/api/v1/admin/cardmarket/loads', 'GET'),
                  ('/riftbound/api/v1/admin/cardmarket/loads/<date>', 'GET'),
                  ('/riftbound/api/v1/admin/cardmarket/status', 'GET'),
                  ('/riftbound/api/v1/admin/cardmarket/load', 'POST')}
        found = {(rule.rule, method) for rule in app.url_map.iter_rules()
                 for method in rule.methods if rule.rule.startswith(BASE)
                 and method not in ('HEAD', 'OPTIONS')}
        assert found == wanted
        assert {classify(rule) for rule in app.url_map.iter_rules()
                if rule.rule.startswith(BASE)} == {'A'}


# ---------------------------------------------------------------------------
# GET /admin/cardmarket/loads
# ---------------------------------------------------------------------------

class TestLoadsList:
    def test_empty_history_is_an_empty_list(self, admin_client):
        assert items(admin_client) == []

    def test_one_item_per_date_newest_first_with_the_files(self, admin_client, three_days):
        listed = items(admin_client)
        assert [item['date'] for item in listed] == [iso(D3), iso(D2), iso(D1)]
        first = listed[0]
        assert first['files'] == [
            {'type': 'price_guide', 'rows': 10, 'status': 'success',
             'message': 'price_guide success', 'loaded_at': at(D3).isoformat()},
            {'type': 'singles', 'rows': 10, 'status': 'success',
             'message': 'singles success', 'loaded_at': at(D3).isoformat()},
            {'type': 'nonsingles', 'rows': 10, 'status': 'success',
             'message': 'nonsingles success', 'loaded_at': at(D3).isoformat()},
        ]
        assert set(first) == {'date', 'files', 'status', 'products_total', 'new_products',
                              'new_products_sample', 'unmatched_singles',
                              'duration_seconds', 'job_id'}

    def test_a_rerun_shows_the_latest_row_of_each_file(self, admin_client, app):
        full_load(D3)
        history(D3, 'singles', status='skipped', rows=0, message='No changes',
                loaded_at=at(D3, 8))
        history(D3, 'nonsingles', status='skipped', rows=0, message='No changes',
                loaded_at=at(D3, 8))
        history(D3, 'price_guide', rows=12, loaded_at=at(D3, 8))
        db.session.commit()
        item = items(admin_client)[0]
        assert [(f['type'], f['status'], f['rows']) for f in item['files']] == [
            ('price_guide', 'success', 12), ('singles', 'skipped', 0),
            ('nonsingles', 'skipped', 0)]
        assert item['status'] == 'success'

    @pytest.mark.parametrize('statuses, expected', [
        (('success', 'success', 'success'), 'success'),
        (('success', 'skipped', 'skipped'), 'success'),
        (('skipped', 'skipped', 'skipped'), 'skipped'),
        (('error', 'error', 'error'), 'error'),
        (('error', 'skipped', 'skipped'), 'error'),
        (('success', 'error', 'skipped'), 'partial'),
        (('success', None, None), 'partial'),           # files missing from the load
        ((None, 'error', None), 'error'),
    ])
    def test_status_is_derived_from_the_files(self, admin_client, app, statuses, expected):
        for file_type, status in zip(('price_guide', 'singles', 'nonsingles'), statuses):
            if status is not None:
                history(D3, file_type, status=status)
        db.session.commit()
        assert items(admin_client)[0]['status'] == expected

    def test_products_total_and_new_products_set_difference(self, admin_client, three_days):
        loads = by_date(admin_client)
        assert loads[iso(D1)]['products_total'] == 3
        assert loads[iso(D1)]['new_products'] is None            # first date: nothing to compare
        assert loads[iso(D1)]['new_products_sample'] == []
        assert loads[iso(D2)]['products_total'] == 4
        assert loads[iso(D2)]['new_products'] == 2               # 4 and 5; 1 removed is not counted
        assert [p['id_product'] for p in loads[iso(D2)]['new_products_sample']] == [4, 5]
        assert loads[iso(D3)]['new_products'] == 1
        assert [p['id_product'] for p in loads[iso(D3)]['new_products_sample']] == [6]

    def test_a_product_that_comes_back_is_new_again(self, admin_client, three_days):
        product('20300102', 1)                     # absent on D2 and D3, back on the next day
        product('20300102', 6)
        full_load('20300102')
        db.session.commit()
        assert by_date(admin_client)['2030-01-02']['new_products'] == 1

    def test_the_previous_date_is_the_previous_loaded_date_even_beyond_the_limit(
            self, admin_client, three_days):
        loads = items(admin_client, '?limit=1')
        assert [item['date'] for item in loads] == [iso(D3)]
        assert loads[0]['new_products'] == 1

    def test_a_date_without_products_has_no_new_products(self, admin_client, three_days):
        history('20300102', 'price_guide')
        db.session.commit()
        item = by_date(admin_client)['2030-01-02']
        assert item['products_total'] == 0
        assert item['new_products'] is None
        assert item['new_products_sample'] == []

    def test_the_sample_item_shape_and_low_price(self, admin_client, three_days):
        db.session.query(RbcmProduct).filter_by(rbprd_date=D3, rbprd_id_product=6).delete()
        product(D3, 6, name='Origins Booster', type_='nonsingle', category='Riftbound Booster')
        product(D3, 7, name='A Single')
        price(D3, 6, 4.25)
        db.session.commit()
        sample = by_date(admin_client)[iso(D3)]['new_products_sample']
        assert sample == [
            {'id_product': 7, 'name': 'A Single', 'category': 'Riftbound Single',
             'type': 'single', 'low_price': None},
            {'id_product': 6, 'name': 'Origins Booster', 'category': 'Riftbound Booster',
             'type': 'nonsingle', 'low_price': 4.25},
        ]

    def test_the_sample_is_capped_at_20(self, admin_client, three_days):
        for n in range(25):
            product(D3, 100 + n, name=f'New {n:02d}')
        db.session.commit()
        item = by_date(admin_client)[iso(D3)]
        assert item['new_products'] == 26
        assert len(item['new_products_sample']) == 20
        assert item['new_products_sample'][0]['name'] == 'New 00'

    def test_unmatched_singles_only_for_the_latest_date(self, admin_client, three_days):
        # D3 singles: 2, 3, 4, 5, 6. 2 mapped, 3 ignored (same id and name), 4 ignored under
        # another name (still unmatched); plus a non-single that is never counted.
        db.session.add(RbcmProductCardMap(rbpcm_id_product=2, rbpcm_rbset_id='OGN',
                                          rbpcm_rbcar_id='001'))
        db.session.add(RbcmIgnored(rbig_id_product=3, rbig_name='Product 3'))
        db.session.add(RbcmIgnored(rbig_id_product=4, rbig_name='Old name'))
        product(D3, 50, type_='nonsingle')
        db.session.commit()
        loads = by_date(admin_client)
        assert loads[iso(D3)]['unmatched_singles'] == 3
        assert loads[iso(D2)]['unmatched_singles'] is None
        assert loads[iso(D1)]['unmatched_singles'] is None

    def test_limit_default_30_and_custom(self, admin_client, app):
        first = datetime(2029, 11, 1)
        for n in range(35):
            history((first + timedelta(days=n)).strftime('%Y%m%d'), 'price_guide')
        db.session.commit()
        listed = items(admin_client)
        assert len(listed) == 30
        assert listed[0]['date'] == '2029-12-05'
        assert len(items(admin_client, '?limit=120')) == 35
        assert [i['date'] for i in items(admin_client, '?limit=2')] == ['2029-12-05',
                                                                         '2029-12-04']

    @pytest.mark.parametrize('query', ['?limit=0', '?limit=121', '?limit=abc', '?other=1'])
    def test_a_bad_query_is_400(self, admin_client, query):
        resp = admin_client.get(f'{LOADS}{query}')
        assert resp.status_code == 400
        body = resp.get_json()
        assert body['code'] == 'validation_error'
        assert body['message'] == 'Invalid query parameters'

    def test_job_link_and_duration(self, admin_client, three_days):
        linked = job(started=at(D3, 6, 30, 0), finished=at(D3, 6, 31, 15),
                     result={'validation': {'date': D3}})
        job(started=at(D2, 6, 30), finished=at(D2, 6, 30, 5), result={'other': 1},
            requested=at(D2, 6, 30))                            # no date in the result
        loads = by_date(admin_client)
        assert loads[iso(D3)]['job_id'] == linked.rbjob_id
        assert loads[iso(D3)]['duration_seconds'] == 75
        assert loads[iso(D1)]['job_id'] is None
        assert loads[iso(D1)]['duration_seconds'] is None

    def test_a_job_without_result_is_linked_by_time(self, admin_client, three_days):
        failed = job(status='error', started=at(D2, 6, 0), finished=at(D2, 7, 0))
        job(kind='heartbeat', started=at(D1, 6, 0), finished=at(D1, 7, 0))
        loads = by_date(admin_client)
        assert loads[iso(D2)]['job_id'] == failed.rbjob_id
        assert loads[iso(D2)]['duration_seconds'] == 3600
        assert loads[iso(D1)]['job_id'] is None

    def test_the_newest_job_with_the_date_wins(self, admin_client, three_days):
        job(started=at(D3, 6, 30), finished=at(D3, 6, 31), result={'validation': {'date': D3}})
        rerun = job(started=at(D3, 8, 0), finished=at(D3, 8, 0, 30),
                    result={'validation': {'date': D3}})
        item = by_date(admin_client)[iso(D3)]
        assert (item['job_id'], item['duration_seconds']) == (rerun.rbjob_id, 30)

    def _statements(self, client, url):
        counted = []

        def before(conn, cursor, statement, params, context, executemany):
            counted.append(statement)

        event.listen(db.engine, 'before_cursor_execute', before)
        try:
            assert client.get(url).status_code == 200
        finally:
            event.remove(db.engine, 'before_cursor_execute', before)
        return counted

    def test_bounded_statements_whatever_the_number_of_dates(self, admin_client, app):
        first = datetime(2029, 11, 1)
        days = [(first + timedelta(days=n)).strftime('%Y%m%d') for n in range(31)]
        def add(some):
            for n, day in enumerate(some):
                full_load(day)
                product(day, 1)
                product(day, 100 + n)
                price(day, 100 + n, 1.5)
            db.session.commit()
            for day in some:
                job(started=at(day), finished=at(day, 7), result={'validation': {'date': day}})

        add(days[:2])
        two = self._statements(admin_client, LOADS)
        add(days[2:])
        many = self._statements(admin_client, LOADS)
        assert len(items(admin_client)) == 30
        assert len(many) == len(two), many
        assert len(many) <= 8, many


# ---------------------------------------------------------------------------
# GET /admin/cardmarket/loads/<date>
# ---------------------------------------------------------------------------

class TestLoadDay:
    def test_unknown_or_malformed_date_is_404(self, admin_client, three_days):
        for value in ('2030-01-05', '20300101', 'x', '2030-13-01'):
            resp = admin_client.get(f'{LOADS}/{value}')
            assert resp.status_code == 404, value
            assert resp.get_json()['error'] == 'Not Found'

    def test_the_day_in_full(self, admin_client, three_days):
        result = {'validation': {'date': D3, 'new_products': 1},
                  'auto_match': {'linked': 2, 'proposed': 3, 'review': 1},
                  'review': [{'product_id': 6, 'reason': 'ambiguous'}], 'review_total': 1,
                  'queued': ['value_snapshot']}
        linked = job(started=at(D3, 6, 30), finished=at(D3, 6, 32), result=result)
        history(D3, 'price_guide', rows=12, message='again', loaded_at=at(D3, 8))
        db.session.commit()
        day = data(admin_client.get(f'{LOADS}/2030-01-01'))
        assert day['date'] == '2030-01-01'
        assert [(f['type'], f['rows'], f['loaded_at']) for f in day['files']] == [
            ('price_guide', 10, at(D3).isoformat()), ('singles', 10, at(D3).isoformat()),
            ('nonsingles', 10, at(D3).isoformat()), ('price_guide', 12, at(D3, 8).isoformat())]
        assert day['status'] == 'success'
        assert day['products_total'] == 5
        assert day['new_products'] == 1
        assert [p['id_product'] for p in day['new_products_list']] == [6]
        assert day['truncated'] is False
        assert day['unmatched_singles'] == 5
        assert day['duration_seconds'] == 120
        assert day['job_id'] == linked.rbjob_id
        assert day['job'] == {'id': linked.rbjob_id, 'status': 'success',
                              'queued_at': at(D3, 6, 30).isoformat(),
                              'started_at': at(D3, 6, 30).isoformat(),
                              'finished_at': at(D3, 6, 32).isoformat(),
                              'message': None, 'result': result}

    def test_an_older_day_without_job(self, admin_client, three_days):
        day = data(admin_client.get(f'{LOADS}/2029-12-30'))
        assert day['new_products'] is None
        assert day['new_products_list'] == []
        assert day['truncated'] is False
        assert day['unmatched_singles'] is None
        assert day['job'] is None
        assert day['job_id'] is None

    def test_the_full_list_is_capped_at_500(self, admin_client, three_days):
        db.session.add_all([RbcmProduct(rbprd_date=D3, rbprd_id_product=1000 + n,
                                        rbprd_name=f'New {n:04d}', rbprd_type='single')
                            for n in range(500)])
        db.session.commit()
        day = data(admin_client.get(f'{LOADS}/2030-01-01'))
        assert day['new_products'] == 501
        assert len(day['new_products_list']) == 500
        assert day['truncated'] is True


# ---------------------------------------------------------------------------
# GET /admin/cardmarket/status
# ---------------------------------------------------------------------------

class TestStatus:
    def test_empty(self, admin_client, frozen_clock):
        assert data(admin_client.get(STATUS)) == {
            'last_load': None, 'loaded_today': False, 'job': None, 'unmatched': 0,
            'unmapped_expansions': 0, 'prices_as_of': None}

    def test_populated(self, admin_client, three_days, frozen_clock):
        history(D3, 'singles', status='skipped', loaded_at=at(D3, 8))
        price(D2, 2, 1.0)
        db.session.add_all([RbcmExpansion(rbexp_id=1, rbexp_rbset_id='OGN'),
                            RbcmExpansion(rbexp_id=2, rbexp_rbset_id=None),
                            RbcmExpansion(rbexp_id=3, rbexp_rbset_id=None)])
        db.session.add(RbcmProductCardMap(rbpcm_id_product=2, rbpcm_rbset_id='OGN',
                                          rbpcm_rbcar_id='001'))
        db.session.commit()
        job(started=at(D3, 6, 30), finished=at(D3, 6, 31), result={'validation': {'date': D3}})
        latest = job(status='running', started=at(D3, 8), requested=at(D3, 8))
        body = data(admin_client.get(STATUS))
        assert body['last_load'] == {'date': '2030-01-01', 'status': 'success',
                                     'loaded_at': at(D3, 8).isoformat()}
        assert body['loaded_today'] is True
        assert body['job'] == {'id': latest.rbjob_id, 'status': 'running',
                               'queued_at': at(D3, 8).isoformat(),
                               'started_at': at(D3, 8).isoformat(), 'finished_at': None,
                               'message': None}
        assert body['unmatched'] == 4
        assert body['unmapped_expansions'] == 2
        assert body['prices_as_of'] == '2029-12-31'

    def test_not_loaded_today(self, admin_client, frozen_clock):
        full_load(D2)
        db.session.commit()
        body = data(admin_client.get(STATUS))
        assert body['last_load']['date'] == '2029-12-31'
        assert body['loaded_today'] is False


# ---------------------------------------------------------------------------
# POST /admin/cardmarket/load
# ---------------------------------------------------------------------------

class TestLoadNow:
    def test_queues_daily_prices_and_audits(self, admin_client, frozen_clock):
        from app.models import User
        resp = admin_client.post(LOAD)
        body = data(resp, 202)
        queued = db.session.get(RbJob, body['job_id'])
        assert queued.rbjob_kind == 'daily_prices'
        assert queued.rbjob_params == {}
        assert queued.rbjob_status == 'queued'
        admin = User.query.filter_by(username='admin').one()
        assert queued.rbjob_requested_by == admin.id
        assert body['job'] == {'id': queued.rbjob_id, 'status': 'queued',
                               'queued_at': frozen_clock().isoformat(),
                               'started_at': None, 'finished_at': None, 'message': None}
        row = RbAdminAudit.query.filter_by(rbaud_action='cardmarket.load').one()
        assert (row.rbaud_target_type, row.rbaud_target_id) == ('job', str(queued.rbjob_id))
        assert row.rbaud_actor_id == admin.id

    def test_an_active_job_is_409_and_nothing_is_added(self, admin_client):
        running = job(status='running', started=at(D3))
        resp = admin_client.post(LOAD)
        assert resp.status_code == 409
        assert resp.get_json()['code'] == 'job_running'
        assert [j.rbjob_id for j in RbJob.query.all()] == [running.rbjob_id]
        assert RbAdminAudit.query.count() == 0

    def test_a_second_post_while_queued_is_409(self, admin_client):
        assert admin_client.post(LOAD).status_code == 202
        assert admin_client.post(LOAD).status_code == 409
        assert RbJob.query.count() == 1
        assert RbAdminAudit.query.count() == 1
