"""F13-a S1/S3 (AC1): the admin API blueprint guard and GET /admin/overview."""
from datetime import date, datetime

import pytest
from sqlalchemy import event

from app import db
from app.models.card import RbCard
from app.models.card_change import RbCardChange
from app.models.job import RbJob
from app.models.set import RbSet

URL = '/riftbound/api/v1/admin/overview'
JSON = {'Accept': 'application/json'}


@pytest.fixture
def catalog(app):
    """3 sets (2 without a release date) and 4 cards (2 without image)."""
    db.session.add_all([
        RbSet(rbset_id='OGN', rbset_name='Origen', rbset_ncard=2, rbset_outdat=date(2026, 1, 1)),
        RbSet(rbset_id='SFD', rbset_name='Segundo', rbset_ncard=2),
        RbSet(rbset_id='UNL', rbset_name='Tercero', rbset_ncard=0),
    ])
    db.session.add_all([
        RbCard(rbcar_rbset_id='OGN', rbcar_id='1', rbcar_name='A', image='ogn_1.png'),
        RbCard(rbcar_rbset_id='OGN', rbcar_id='2', rbcar_name='B', image=None),
        RbCard(rbcar_rbset_id='SFD', rbcar_id='1', rbcar_name='C', image=''),
        RbCard(rbcar_rbset_id='SFD', rbcar_id='2', rbcar_name='D', image='sfd_2.png'),
    ])
    db.session.commit()
    return app


class TestGuard:
    def test_anonymous_gets_a_json_401(self, client):
        resp = client.get(URL, headers=JSON)
        assert resp.status_code == 401
        body = resp.get_json()
        assert body['success'] is False
        assert body['code'] == 'unauthenticated'

    def test_a_plain_user_gets_a_json_403(self, authenticated_client):
        resp = authenticated_client.get(URL, headers=JSON)
        assert resp.status_code == 403
        body = resp.get_json()
        assert body['success'] is False
        assert body['error'] == 'Forbidden'

    def test_the_rule_is_classified_admin(self):
        from tests.test_authz_matrix import MATRIX
        assert MATRIX['api_admin.*'] == 'A'


class TestOverview:
    def test_the_catalog_counts(self, admin_client, catalog, frozen_clock):
        resp = admin_client.get(URL)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert body['data'] == {'catalog': {
            'sets': 3, 'sets_without_release_date': 2,
            'cards': 4, 'cards_without_image': 2},
            'riot': {'pending_changes': 0, 'active_sets': [],
                     'last_sync': None, 'placeholder_sets': []},
            'cardmarket': {'last_load': None, 'loaded_today': False, 'job_status': None,
                           'unmatched': 0, 'unmapped_expansions': 0}}

    def test_an_empty_catalog_counts_zeros(self, admin_client):
        body = admin_client.get(URL).get_json()
        assert body['data']['catalog'] == {
            'sets': 0, 'sets_without_release_date': 0, 'cards': 0, 'cards_without_image': 0}

    def test_the_riot_block(self, admin_client, app, frozen_clock):
        from datetime import datetime
        db.session.add(RbSet(rbset_id='FUT', rbset_name='Future',
                             rbset_outdat=date(2030, 1, 10)))
        db.session.add(RbSet(rbset_id='LEG', rbset_name='LEG'))
        db.session.add(RbCard(rbcar_rbset_id='FUT', rbcar_id='1',
                              rbcar_name='Future Unit'))
        db.session.add(RbCardChange(rbchg_rbset_id='FUT', rbchg_rbcar_id='1',
                                    rbchg_field='rbcar_name', rbchg_old_value='X',
                                    rbchg_new_value='Future Unit', rbchg_status='pending',
                                    rbchg_detected_at=datetime(2030, 1, 1, 10)))
        db.session.add(RbJob(rbjob_kind='riot_sync', rbjob_status='success',
                             rbjob_params={'trigger': 'schedule'},
                             rbjob_started_at=datetime(2030, 1, 1, 11),
                             rbjob_finished_at=datetime(2030, 1, 1, 12)))
        db.session.commit()
        riot = admin_client.get(URL).get_json()['data']['riot']
        assert riot['pending_changes'] == 1
        assert riot['active_sets'] == [{'id': 'FUT', 'name': 'Future',
                                        'window': 'pre_release',
                                        'next_run_at': '2030-01-01T14:00:00+01:00'}]
        assert riot['last_sync'] == {'job_id': 1, 'status': 'success',
                                     'finished_at': '2030-01-01T12:00:00',
                                     'trigger': 'schedule'}
        assert riot['placeholder_sets'] == ['LEG']

    def test_at_most_twelve_statements_beyond_the_session(self, admin_client, catalog):
        """4 catalog COUNTs + changes COUNT + sets + last riot job, then the Cardmarket
        health (CM-e): newest load day, its history rows, last `daily_prices` job,
        unmatched and unmapped COUNTs."""
        _cardmarket_load('20300101')
        counted = []

        def before(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith('SELECT') and 'rbusers' not in statement:
                counted.append(statement)

        event.listen(db.engine, 'before_cursor_execute', before)
        try:
            assert admin_client.get(URL).status_code == 200
        finally:
            event.remove(db.engine, 'before_cursor_execute', before)
        assert len(counted) <= 12, counted


def _cardmarket_load(day, status='success'):
    from app.models import RbcmLoadHistory
    for file_type in ('price_guide', 'singles', 'nonsingles'):
        db.session.add(RbcmLoadHistory(
            rblh_date=day, rblh_file_type=file_type, rblh_hash=f'h-{day}-{file_type}',
            rblh_rows=1, rblh_status=status, rblh_message='ok',
            rblh_loaded_at=datetime(int(day[:4]), int(day[4:6]), int(day[6:]), 6, 30)))
    db.session.commit()


class TestCardmarketBlock:
    """CM-e: the Cardmarket health counters, the same values as /admin/cardmarket/status."""

    def test_empty(self, admin_client, frozen_clock):
        body = admin_client.get(URL).get_json()['data']
        assert body['cardmarket'] == {'last_load': None, 'loaded_today': False,
                                      'job_status': None, 'unmatched': 0,
                                      'unmapped_expansions': 0}

    def test_populated_matches_the_status_endpoint(self, admin_client, frozen_clock):
        from app.models import RbcmExpansion, RbcmProduct
        _cardmarket_load('20300101')
        db.session.add_all([
            RbcmProduct(rbprd_date='20300101', rbprd_id_product=n, rbprd_name=f'P{n}',
                        rbprd_category_name='Riftbound Single', rbprd_type='single')
            for n in (1, 2, 3)])
        db.session.add_all([RbcmExpansion(rbexp_id=10, rbexp_rbset_id=None),
                            RbcmExpansion(rbexp_id=11, rbexp_rbset_id=None)])
        db.session.add(RbJob(rbjob_kind='daily_prices', rbjob_status='running',
                             rbjob_params={}, rbjob_started_at=datetime(2030, 1, 1, 6)))
        db.session.commit()
        block = admin_client.get(URL).get_json()['data']['cardmarket']
        assert block == {'last_load': {'date': '2030-01-01', 'status': 'success'},
                         'loaded_today': True, 'job_status': 'running',
                         'unmatched': 3, 'unmapped_expansions': 2}
        status = admin_client.get('/riftbound/api/v1/admin/cardmarket/status').get_json()
        status = status['data']
        assert block['unmatched'] == status['unmatched']
        assert block['unmapped_expansions'] == status['unmapped_expansions']
        assert block['loaded_today'] == status['loaded_today']
        assert block['last_load'] == {'date': status['last_load']['date'],
                                      'status': status['last_load']['status']}
        assert block['job_status'] == status['job']['status']

    def test_an_older_partial_load_is_not_today(self, admin_client, frozen_clock):
        _cardmarket_load('20291231', status='error')
        from app.models import RbcmLoadHistory
        db.session.add(RbcmLoadHistory(
            rblh_date='20291231', rblh_file_type='singles', rblh_hash='h2', rblh_rows=1,
            rblh_status='success', rblh_message='ok', rblh_loaded_at=datetime(2029, 12, 31, 7)))
        db.session.commit()
        block = admin_client.get(URL).get_json()['data']['cardmarket']
        assert block['last_load'] == {'date': '2029-12-31', 'status': 'partial'}
        assert block['loaded_today'] is False
