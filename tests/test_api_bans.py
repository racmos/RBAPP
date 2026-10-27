"""F2-a S8: GET /riftbound/api/v1/bans (U), optional `mode` filter."""
from datetime import date

import pytest

from app import db
from app.models import RbCard, RbSet
from app.services import bans

URL = '/riftbound/api/v1/bans'
JINX = 'Jinx, Loose Cannon'
INVALID_MODE = {
    'success': False, 'error': 'Validation Error', 'message': 'Invalid query parameters',
    'code': 'validation_error',
    'details': [{'field': 'mode', 'message': 'mode must be 1v1 or 2v2', 'type': 'literal_error',
                 'code': 'invalid_value'}],
}


@pytest.fixture
def seeded(app):
    db.session.add_all([RbSet(rbset_id='OGN', rbset_name='Origins'),
                        RbSet(rbset_id='OGNX', rbset_name='Origins promos')])
    db.session.add_all([
        RbCard(rbcar_rbset_id='OGNX', rbcar_id='257', rbcar_name=JINX),
        RbCard(rbcar_rbset_id='OGN', rbcar_id='79', rbcar_name=JINX),
        RbCard(rbcar_rbset_id='OGN', rbcar_id='1', rbcar_name='Called Shot'),
    ])
    db.session.commit()
    bans.add_ban(JINX, ['1v1', '2v2'], since=date(2026, 9, 1), reason='Too strong')
    bans.add_ban('Called Shot', ['2v2'], since=date(2026, 9, 18))
    bans.add_ban('Future Card', ['1v1'], since=date(2026, 10, 24), force=True)


def _jinx(mode):
    return {'name': JINX, 'mode': mode, 'since': '2026-09-01', 'reason': 'Too strong',
            'printings': [{'set_id': 'OGN', 'card_id': '79'},
                          {'set_id': 'OGNX', 'card_id': '257'}]}


FUTURE = {'name': 'Future Card', 'mode': '1v1', 'since': '2026-10-24', 'reason': None,
          'printings': []}
CALLED_SHOT = {'name': 'Called Shot', 'mode': '2v2', 'since': '2026-09-18', 'reason': None,
               'printings': [{'set_id': 'OGN', 'card_id': '1'}]}


def test_lists_every_ban_in_order(authenticated_client, seeded):
    resp = authenticated_client.get(URL)
    assert resp.status_code == 200
    assert resp.get_json() == {'success': True, 'data': {'items': [
        FUTURE, _jinx('1v1'), CALLED_SHOT, _jinx('2v2')]}}


@pytest.mark.parametrize('mode, items', [
    ('1v1', [FUTURE, _jinx('1v1')]),
    ('2v2', [CALLED_SHOT, _jinx('2v2')]),
])
def test_mode_filter(authenticated_client, seeded, mode, items):
    resp = authenticated_client.get(URL, query_string={'mode': mode})
    assert resp.status_code == 200
    assert resp.get_json() == {'success': True, 'data': {'items': items}}


def test_no_bans_is_an_empty_list(authenticated_client):
    resp = authenticated_client.get(URL, query_string={'mode': '2v2'})
    assert (resp.status_code, resp.get_json()) == (200, {'success': True, 'data': {'items': []}})


@pytest.mark.parametrize('mode', ['3v3', 'all', '1V1', ' 1v1'])
def test_invalid_mode_is_a_400(authenticated_client, seeded, mode):
    resp = authenticated_client.get(URL, query_string={'mode': mode})
    assert (resp.status_code, resp.get_json()) == (400, INVALID_MODE)


def test_empty_mode_is_absent_and_returns_all_bans(authenticated_client, seeded):
    """S1: sent-but-empty counts as absent -> no mode filter -> every ban."""
    resp = authenticated_client.get(URL, query_string={'mode': ''})
    assert resp.status_code == 200
    assert resp.get_json() == {'success': True, 'data': {'items': [
        FUTURE, _jinx('1v1'), CALLED_SHOT, _jinx('2v2')]}}


def test_anonymous_gets_a_json_401(client, seeded):
    resp = client.get(URL)
    assert resp.status_code == 401
    assert 'Location' not in resp.headers
    body = resp.get_json()
    assert (body['success'], body['error'], body['code']) == (False, 'Unauthorized',
                                                               'unauthenticated')
    assert 'items' not in str(body)


def test_endpoint_name(app):
    rules = [r for r in app.url_map.iter_rules() if r.rule == URL]
    assert [(r.endpoint, sorted(r.methods - {'HEAD', 'OPTIONS'})) for r in rules] == [
        ('api_v1.list_bans', ['GET'])]
