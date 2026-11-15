"""F9-h S2-S6 (AC2): the personal API key of the signed-in user: GET, POST (create or replace,
re-auth, shown once) and DELETE /me/api-key, and `security.api_key` of GET /me."""
import hashlib
import re

import pytest
import sqlalchemy as sa

from app import db
from app.models import RbApiKey, User
from tests.conftest import login_as

API = '/riftbound/api/v1'
KEY_URL = f'{API}/me/api-key'
ME = f'{API}/me'
COLLECTION = f'{API}/collection'
NOW = '2030-01-01T12:00:00Z'
KEY_FORMAT = re.compile(r'rb_live_[0-9a-f]{40}')


@pytest.fixture
def ana(app, make_user, frozen_clock):
    """`ana` signed in at the frozen time (2030-01-01 12:00 UTC): re-authenticated until 12:10."""
    make_user('ana')
    return login_as(app.test_client(), 'ana')


def ana_id():
    return User.query.filter_by(username='ana').one().id


def stored_keys():
    db.session.expire_all()
    return db.session.execute(sa.select(RbApiKey).order_by(RbApiKey.rbapk_id)).scalars().all()


def bearer(app, key, url=COLLECTION):
    """A fresh client (no cookie) reading `url` with the key."""
    return app.test_client().get(url, headers={'Authorization': f'Bearer {key}'})


def create(client):
    response = client.post(KEY_URL)
    assert response.status_code == 201, response.get_json()
    return response


class TestCreate:
    def test_201_the_key_once_and_its_info(self, ana):
        response = create(ana)
        assert response.headers['Cache-Control'] == 'no-store'
        data = response.get_json()['data']
        assert set(data) == {'key', 'api_key'}
        key = data['key']
        assert KEY_FORMAT.fullmatch(key)
        assert data['api_key'] == {'prefix': key[:14], 'created_at': NOW, 'last_used_at': None}
        assert data['api_key']['prefix'].startswith('rb_live_')
        assert len(data['api_key']['prefix']) == 14

    def test_only_the_hash_and_the_prefix_are_stored(self, ana):
        key = create(ana).get_json()['data']['key']
        [row] = stored_keys()
        assert row.rbapk_user_id == ana_id()
        assert row.rbapk_key_hash == hashlib.sha256(key.encode()).hexdigest()
        assert row.rbapk_prefix == key[:14]
        values = db.session.execute(sa.text('SELECT * FROM riftbound.rbapikeys')).one()
        assert key not in [str(v) for v in values]

    def test_two_keys_are_different(self, ana):
        first = create(ana).get_json()['data']['key']
        second = create(ana).get_json()['data']['key']
        assert first != second

    def test_the_key_is_never_shown_again(self, ana):
        key = create(ana).get_json()['data']['key']
        assert key not in ana.get(KEY_URL).get_data(as_text=True)
        assert key not in ana.get(ME).get_data(as_text=True)

    def test_a_replacement_kills_the_old_key_at_once(self, app, ana, frozen_clock):
        old = create(ana).get_json()['data']['key']
        assert bearer(app, old).status_code == 200
        frozen_clock.advance(minutes=1)
        new = create(ana).get_json()['data']
        assert len(stored_keys()) == 1
        assert new['api_key'] == {'prefix': new['key'][:14], 'created_at': '2030-01-01T12:01:00Z',
                                  'last_used_at': None}
        refused = bearer(app, old)
        assert (refused.status_code, refused.get_json()['code']) == (401, 'api_key_invalid')
        assert bearer(app, new['key']).status_code == 200

    def test_needs_a_recent_reauthentication(self, ana, frozen_clock):
        frozen_clock.advance(minutes=10, seconds=1)
        response = ana.post(KEY_URL)
        assert response.status_code == 403
        assert response.get_json() == {
            'success': False, 'error': 'Forbidden',
            'message': 'Confirm your identity to continue', 'code': 'reauth_required',
            'params': {'methods': ['password']}}
        assert stored_keys() == []

    def test_a_refused_replacement_keeps_the_old_key(self, app, ana, frozen_clock):
        key = create(ana).get_json()['data']['key']
        frozen_clock.advance(minutes=11)
        assert ana.post(KEY_URL).status_code == 403
        assert bearer(app, key).status_code == 200

    def test_anonymous_is_401(self, client):
        response = client.post(KEY_URL)
        assert (response.status_code, response.get_json()['code']) == (401, 'unauthenticated')


class TestRead:
    def test_null_without_a_key(self, ana):
        response = ana.get(KEY_URL)
        assert (response.status_code, response.get_json()['data']) == (200, {'api_key': None})

    def test_the_info_never_the_key(self, ana):
        key = create(ana).get_json()['data']['key']
        assert ana.get(KEY_URL).get_json()['data'] == {
            'api_key': {'prefix': key[:14], 'created_at': NOW, 'last_used_at': None}}

    def test_last_used_at_after_a_bearer_request(self, app, ana, frozen_clock):
        key = create(ana).get_json()['data']['key']
        frozen_clock.advance(minutes=3)
        assert bearer(app, key).status_code == 200
        assert ana.get(KEY_URL).get_json()['data']['api_key']['last_used_at'] == \
            '2030-01-01T12:03:00Z'

    def test_only_the_callers_key(self, app, ana, make_user):
        create(ana)
        make_user('bo')
        bo = login_as(app.test_client(), 'bo')
        assert bo.get(KEY_URL).get_json()['data'] == {'api_key': None}

    def test_anonymous_is_401(self, client):
        assert client.get(KEY_URL).status_code == 401


class TestDelete:
    def test_revokes_the_key_and_is_idempotent(self, app, ana, frozen_clock):
        key = create(ana).get_json()['data']['key']
        frozen_clock.advance(minutes=30)                 # no re-authentication needed
        for _ in range(2):
            response = ana.delete(KEY_URL)
            assert (response.status_code, response.get_json()['data']) == (200, {'api_key': None})
        assert stored_keys() == []
        refused = bearer(app, key)
        assert (refused.status_code, refused.get_json()['code']) == (401, 'api_key_invalid')

    def test_only_the_callers_key(self, app, ana, make_user):
        key = create(ana).get_json()['data']['key']
        make_user('bo')
        login_as(app.test_client(), 'bo').delete(KEY_URL)
        assert bearer(app, key).status_code == 200

    def test_anonymous_is_401(self, client):
        assert client.delete(KEY_URL).status_code == 401


class TestMe:
    def test_security_api_key_is_the_info_or_null(self, ana):
        assert ana.get(ME).get_json()['data']['security']['api_key'] is None
        key = create(ana).get_json()['data']['key']
        assert ana.get(ME).get_json()['data']['security']['api_key'] == {
            'prefix': key[:14], 'created_at': NOW, 'last_used_at': None}
        ana.delete(KEY_URL)
        assert ana.get(ME).get_json()['data']['security']['api_key'] is None
