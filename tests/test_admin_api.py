"""F13-a S1/S3 (AC1): the admin API blueprint guard and GET /admin/overview."""
from datetime import date

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
                     'last_sync': None, 'placeholder_sets': []}}

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

    def test_at_most_eight_statements_beyond_the_session(self, admin_client, catalog):
        """The handler issues 4 catalog COUNTs + changes COUNT + sets + last job."""
        counted = []

        def before(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith('SELECT') and 'rbusers' not in statement:
                counted.append(statement)

        event.listen(db.engine, 'before_cursor_execute', before)
        try:
            assert admin_client.get(URL).status_code == 200
        finally:
            event.remove(db.engine, 'before_cursor_execute', before)
        assert len(counted) <= 8, counted
