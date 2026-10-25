"""F13-b S2-S5 (AC1): sets admin API."""
from datetime import date

import pytest

from app import db
from app.models.audit import RbAdminAudit
from app.models.card import RbCard
from app.models.set import RbSet

URL = '/riftbound/api/v1/admin/sets'
JSON = {'Accept': 'application/json'}


@pytest.fixture
def catalog(app):
    db.session.add_all([
        RbSet(rbset_id='AAA', rbset_name='A first', rbset_ncard=5),
        RbSet(rbset_id='BBB', rbset_name='B dated', rbset_ncard=1,
              rbset_outdat=date(2026, 1, 1)),
        RbSet(rbset_id='CCC', rbset_name='C newer', rbset_ncard=2,
              rbset_outdat=date(2026, 6, 1)),
        RbSet(rbset_id='DDD', rbset_name='D second', rbset_ncard=0),
        RbCard(rbcar_rbset_id='BBB', rbcar_id='1', rbcar_name='B One'),
    ])
    db.session.commit()
    return app


def payload(resp):
    return resp.get_json()


class TestGuard:
    def test_anonymous_gets_a_json_401(self, client):
        resp = client.get(URL, headers=JSON)
        assert resp.status_code == 401
        assert payload(resp)['code'] == 'unauthenticated'

    def test_a_plain_user_gets_a_json_403(self, authenticated_client):
        resp = authenticated_client.get(URL, headers=JSON)
        assert resp.status_code == 403


class TestList:
    def test_order_and_counts(self, admin_client, catalog):
        body = payload(admin_client.get(URL))
        assert body['success'] is True
        assert [(i['id'], i['card_count'], i['declared_count']) for i in body['data']] == [
            ('AAA', 0, 5), ('DDD', 0, 0), ('CCC', 0, 2), ('BBB', 1, 1)]


class TestCreate:
    def test_create_uppercases_the_id(self, admin_client):
        body = payload(admin_client.post(
            URL, json={'id': 'tst', 'name': 'Test set', 'release_date': '2026-12-04'}))
        assert body['data'] == {'id': 'TST', 'name': 'Test set',
                                'release_date': '2026-12-04', 'card_count': 0,
                                'declared_count': None}

    def test_duplicate_id_is_409(self, admin_client, catalog):
        resp = admin_client.post(
            URL, json={'id': 'aaa', 'name': 'Other', 'release_date': '2026-01-01'})
        assert resp.status_code == 409
        body = payload(resp)
        assert body['code'] == 'already_exists'
        assert body['params'] == {'field': 'id'}

    def test_missing_release_date_is_400(self, admin_client):
        resp = admin_client.post(URL, json={'id': 'ZZZ', 'name': 'No date'})
        assert resp.status_code == 400
        body = payload(resp)
        assert body['code'] == 'validation_error'
        assert any(d['field'] == 'release_date' and d['code'] == 'required'
                   for d in body['details'])

    def test_bad_id_is_400(self, admin_client):
        resp = admin_client.post(
            URL, json={'id': 'X!', 'name': 'Bad', 'release_date': '2026-01-01'})
        assert resp.status_code == 400

    def test_audit_row(self, admin_client):
        admin_client.post(
            URL, json={'id': 'TST', 'name': 'Test', 'release_date': '2026-12-04'})
        row = RbAdminAudit.query.one()
        assert (row.rbaud_action, row.rbaud_target_type, row.rbaud_target_id) == (
            'set.create', 'set', 'TST')
        assert row.rbaud_details == {'name': 'Test', 'release_date': '2026-12-04'}

    def test_a_failed_create_writes_no_audit_row(self, admin_client, catalog):
        admin_client.post(
            URL, json={'id': 'AAA', 'name': 'Dup', 'release_date': '2026-01-01'})
        assert RbAdminAudit.query.count() == 0


class TestPatch:
    def test_rename_and_dates(self, admin_client, catalog):
        body = payload(admin_client.patch(
            f'{URL}/AAA', json={'name': 'Renamed', 'release_date': '2027-02-03'}))
        assert body['data']['name'] == 'Renamed'
        row = RbAdminAudit.query.one()
        assert row.rbaud_action == 'set.update'
        assert row.rbaud_details == {'name': ['A first', 'Renamed'],
                                     'release_date': [None, '2027-02-03']}

    def test_release_date_cannot_become_null(self, admin_client, catalog):
        resp = admin_client.patch(f'{URL}/BBB', json={'release_date': None})
        assert resp.status_code == 400
        assert any(d['field'] == 'release_date' and d['code'] == 'required'
                   for d in payload(resp)['details'])

    def test_id_change_with_cards_is_409(self, admin_client, catalog):
        resp = admin_client.patch(f'{URL}/BBB', json={'id': 'BBX'})
        assert resp.status_code == 409
        body = payload(resp)
        assert body['code'] == 'set_in_use'
        assert body['params'] == {'cards': 1}

    def test_id_change_without_cards(self, admin_client, catalog):
        body = payload(admin_client.patch(f'{URL}/AAA', json={'id': 'AAX'}))
        assert body['data']['id'] == 'AAX'
        assert RbSet.query.get('AAX') is not None

    def test_id_collision_is_409(self, admin_client, catalog):
        resp = admin_client.patch(f'{URL}/AAA', json={'id': 'BBB'})
        assert resp.status_code == 409
        assert payload(resp)['code'] == 'already_exists'

    def test_unknown_set_is_404(self, admin_client):
        assert admin_client.patch(f'{URL}/NOPE', json={'name': 'X'}).status_code == 404


class TestDelete:
    def test_delete_with_cards_is_409(self, admin_client, catalog):
        resp = admin_client.delete(f'{URL}/BBB')
        assert resp.status_code == 409
        assert payload(resp)['params'] == {'cards': 1}

    def test_delete(self, admin_client, catalog):
        body = payload(admin_client.delete(f'{URL}/AAA'))
        assert body['data'] == {'deleted': 'AAA'}
        assert RbSet.query.get('AAA') is None
        row = RbAdminAudit.query.one()
        assert (row.rbaud_action, row.rbaud_target_id) == ('set.delete', 'AAA')
