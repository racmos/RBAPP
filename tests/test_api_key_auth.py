"""F9-h S7-S12 (AC3): bearer authentication with a personal API key.

A request under /riftbound/api/v1/ with `Authorization: Bearer ...` is authenticated only by the
key (cookies ignored); a bad key is a 401 `api_key_invalid`, an unsafe method or a deny-list path
a 403 `api_key_read_only` (both before the CSRF check); it never creates or touches a session,
never sets a cookie and never grants admin rights. 60 requests a minute per key.
"""
import logging

import pytest
import sqlalchemy as sa
from flask import jsonify
from flask_login import current_user
from sqlalchemy import event

from app import db
from app.models import RbApiKey, RbCollection, RbSession, User
from app.services import api_keys
from tests.auth_helpers import turn_on_2fa
from tests.conftest import api_csrf_token, login_as

API = '/riftbound/api/v1'
COLLECTION = f'{API}/collection'
WHOAMI = f'{API}/test-only/whoami'
OUTSIDE_WHOAMI = '/riftbound/test-only/whoami'
UNKNOWN_KEY = 'rb_live_' + '0' * 40
INVALID = {'success': False, 'error': 'Unauthorized', 'message': 'The API key is not valid',
           'code': 'api_key_invalid'}
READ_ONLY = {'success': False, 'error': 'Forbidden', 'message': 'API keys can only read data',
             'code': 'api_key_read_only'}


@pytest.fixture
def whoami(app):
    """Test-only routes that answer the caller's username (or null), inside and outside the API
    prefix; added before the first request."""
    def who():
        return jsonify({'user': current_user.username if current_user.is_authenticated
                        else None})

    app.add_url_rule(WHOAMI, 'whoami_api', who)
    app.add_url_rule(OUTSIDE_WHOAMI, 'whoami_outside', who)
    return WHOAMI


@pytest.fixture
def ana(app, whoami, make_user, frozen_clock):
    """`ana` and her key; returns the key."""
    user = make_user('ana')
    key, _ = api_keys.create(user.id)
    return key


def auth(key):
    return {'Authorization': f'Bearer {key}'}


def fresh(app):
    return app.test_client()


def stored_key(username='ana'):
    db.session.expire_all()
    return db.session.execute(
        sa.select(RbApiKey).join(User, User.id == RbApiKey.rbapk_user_id)
        .where(User.username == username)).scalar_one()


def session_rows():
    db.session.expire_all()
    return db.session.execute(sa.select(RbSession).order_by(RbSession.rbses_id)).scalars().all()


def set_cookies(response):
    return response.headers.getlist('Set-Cookie')


def refused(response, expected):
    assert response.get_json() == expected, (response.status_code, response.get_data())
    assert response.status_code == (401 if expected is INVALID else 403)


def cli(app, *args, input=None):
    result = app.test_cli_runner().invoke(args=list(args), input=input)
    assert result.exit_code == 0, result.output
    return result


# --- S8 examples ----------------------------------------------------------------------------

class TestTheExamples:
    def test_a_valid_key_reads_the_users_collection(self, app, ana, sample_card, make_user):
        db.session.add_all([
            RbCollection(rbcol_rbset_id='TEST1', rbcol_rbcar_id='001', rbcol_user='ana',
                         rbcol_quantity=2),
            RbCollection(rbcol_rbset_id='TEST1', rbcol_rbcar_id='001', rbcol_user='bo',
                         rbcol_quantity=5, rbcol_foil='S'),
        ])
        db.session.commit()
        response = fresh(app).get(COLLECTION, headers=auth(ana))
        assert response.status_code == 200
        groups = response.get_json()['data']['items']
        assert [(g['lines'][0]['qty'], g['foil']) for g in groups] == [(2, False)]

    def test_a_post_with_a_valid_key_is_read_only(self, app, ana):
        response = fresh(app).post(COLLECTION, json={'set_id': 'TEST1', 'card_id': '001'},
                                   headers=auth(ana))
        refused(response, READ_ONLY)
        assert db.session.execute(sa.select(sa.func.count()).select_from(RbCollection)
                                  ).scalar_one() == 0

    def test_an_admins_key_is_refused_on_the_admin_api(self, app, whoami, make_user):
        admin = make_user('root', is_admin=True)
        key, _ = api_keys.create(admin.id)
        refused(fresh(app).get(f'{API}/admin/overview', headers=auth(key)), READ_ONLY)

    @pytest.mark.parametrize('path', ['/me/products', '/me/prefs'])
    def test_my_products_and_prefs_are_readable(self, app, ana, path):
        assert fresh(app).get(f'{API}{path}', headers=auth(ana)).status_code == 200

    def test_a_bad_key_on_health_is_invalid(self, app, ana):
        refused(fresh(app).get(f'{API}/health', headers=auth(UNKNOWN_KEY)), INVALID)


# --- S7, S8.1: recognition and validity -----------------------------------------------------

class TestRecognition:
    @pytest.mark.parametrize('scheme', ['Bearer', 'bearer', 'BEARER', 'BeArEr'])
    def test_the_scheme_is_case_insensitive(self, app, ana, scheme):
        response = fresh(app).get(WHOAMI, headers={'Authorization': f'{scheme} {ana}'})
        assert response.get_json() == {'user': 'ana'}

    def test_head_is_allowed(self, app, ana):
        assert fresh(app).head(WHOAMI, headers=auth(ana)).status_code == 200

    @pytest.mark.parametrize('value', [
        '', 'rb_live_', UNKNOWN_KEY, 'rb_live_' + 'a' * 39, 'rb_live_' + 'a' * 41,
        'rb_live_' + 'A' * 40, 'rb_test_' + 'a' * 40, 'rb_live_' + 'g' * 40,
    ])
    def test_a_malformed_or_unknown_key_is_invalid(self, app, ana, value):
        refused(fresh(app).get(WHOAMI, headers={'Authorization': f'Bearer {value}'}), INVALID)

    def test_the_uppercase_form_of_a_real_key_is_invalid(self, app, ana):
        upper = 'rb_live_' + ana[len('rb_live_'):].upper()
        if upper != ana:
            refused(fresh(app).get(WHOAMI, headers=auth(upper)), INVALID)

    def test_another_scheme_is_not_a_key(self, app, ana):
        response = fresh(app).get(COLLECTION, headers={'Authorization': f'Basic {ana}'})
        assert (response.status_code, response.get_json()['code']) == (401, 'unauthenticated')

    def test_no_header_is_the_usual_anonymous_401(self, app, ana):
        response = fresh(app).get(COLLECTION)
        assert (response.status_code, response.get_json()['code']) == (401, 'unauthenticated')

    def test_the_key_wins_over_another_users_cookies(self, app, ana, make_user):
        make_user('bo')
        bo = fresh(app)
        login_as(bo, 'bo')
        bo.post(f'{API}/auth/login', json={'username': 'bo', 'password': 'testpass123',
                                           'remember': True})
        assert bo.get_cookie('remember_token') is not None
        assert bo.get(WHOAMI).get_json() == {'user': 'bo'}
        assert bo.get(WHOAMI, headers=auth(ana)).get_json() == {'user': 'ana'}

    def test_a_bad_key_never_falls_back_to_the_cookie_session(self, app, ana, make_user):
        make_user('bo')
        bo = login_as(fresh(app), 'bo')
        refused(bo.get(WHOAMI, headers=auth(UNKNOWN_KEY)), INVALID)
        refused(bo.get(COLLECTION, headers=auth('nonsense')), INVALID)
        assert bo.get(WHOAMI).get_json() == {'user': 'bo'}

    def test_a_key_with_a_cookie_session_still_cannot_write(self, csrf_app, ana, make_user):
        make_user('bo')
        bo = login_as(fresh(csrf_app), 'bo')
        token = api_csrf_token(bo)
        response = bo.patch(f'{API}/me/prefs', json={'density': 'compact'},
                            headers={**auth(ana), 'X-CSRFToken': token})
        refused(response, READ_ONLY)

    def test_outside_the_api_prefix_the_header_is_ignored(self, app, ana, make_user):
        make_user('bo')
        bo = login_as(fresh(app), 'bo')
        assert bo.get(OUTSIDE_WHOAMI, headers=auth(ana)).get_json() == {'user': 'bo'}
        assert bo.get(OUTSIDE_WHOAMI, headers=auth('nonsense')).get_json() == {'user': 'bo'}
        assert fresh(app).get(OUTSIDE_WHOAMI, headers=auth(ana)).get_json() == {'user': None}
        redirect = fresh(app).get('/riftbound/', headers=auth('nonsense'))
        assert redirect.status_code == 302

    def test_the_api_root_without_a_slash_is_outside(self, app, ana):
        response = fresh(app).get(API, headers=auth('nonsense'))
        assert (response.get_json(silent=True) or {}).get('code') != 'api_key_invalid'


# --- S8 order and the read-only rule --------------------------------------------------------

class TestOrder:
    @pytest.mark.parametrize('method', ['POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'])
    def test_invalid_comes_before_read_only(self, app, ana, method):
        refused(fresh(app).open(COLLECTION, method=method, headers=auth(UNKNOWN_KEY)), INVALID)

    @pytest.mark.parametrize('method', ['POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'])
    def test_any_method_but_get_and_head_is_read_only(self, app, ana, method):
        refused(fresh(app).open(COLLECTION, method=method, headers=auth(ana)), READ_ONLY)

    def test_read_only_comes_before_csrf(self, csrf_app, ana):
        response = fresh(csrf_app).post(COLLECTION, json={}, headers=auth(ana))
        refused(response, READ_ONLY)

    def test_invalid_comes_before_csrf(self, csrf_app, ana):
        refused(fresh(csrf_app).post(COLLECTION, json={}, headers=auth('x')), INVALID)

    def test_read_only_comes_before_the_deny_list(self, app, ana):
        refused(fresh(app).post(f'{API}/me/api-key', headers=auth(ana)), READ_ONLY)

    @pytest.mark.parametrize('path', [
        '/auth/session', '/auth/captcha', '/admin/overview', '/admin/sets', '/me/account',
        '/me/reauth', '/me/sessions', '/me/sessions/1', '/me/2fa/setup', '/me/api-key',
        '/me/avatar', '/me/connections', '/me', '/me/', '//admin/overview', '/me/sessions/',
    ])
    def test_the_deny_list(self, app, ana, path):
        refused(fresh(app).get(f'{API}{path}', headers=auth(ana)), READ_ONLY)

    def test_the_deny_list_is_checked_after_validity(self, app, ana):
        refused(fresh(app).get(f'{API}/admin/overview', headers=auth(UNKNOWN_KEY)), INVALID)

    @pytest.mark.parametrize('path', ['/me/prefs', '/me/products', '/collection', '/decks',
                                      '/bans', '/cards', '/products', '/locations',
                                      '/wishlist-alerts', '/meta/game', '/health'])
    def test_reading_paths_pass(self, app, ana, path):
        assert fresh(app).get(f'{API}{path}', headers=auth(ana)).status_code == 200


# --- S9: no session, no cookie, no admin ----------------------------------------------------

class TestNoSession:
    def test_no_set_cookie_on_any_answer(self, app, ana, make_user):
        make_user('bo')
        bo = login_as(fresh(app), 'bo')
        for client in (fresh(app), bo):
            for method, path, key in (('GET', WHOAMI, ana), ('GET', COLLECTION, ana),
                                      ('GET', f'{API}/auth/session', ana),
                                      ('POST', COLLECTION, ana), ('GET', WHOAMI, UNKNOWN_KEY)):
                response = client.open(path, method=method, headers=auth(key))
                assert set_cookies(response) == [], (method, path, response.status_code)

    def test_no_session_row_is_created_or_touched(self, app, ana, make_user, frozen_clock):
        make_user('bo')
        bo = login_as(fresh(app), 'bo')
        [before] = [(r.rbses_id, r.rbses_last_seen_at) for r in session_rows()]
        frozen_clock.advance(minutes=30)
        for client in (fresh(app), bo):
            assert client.get(WHOAMI, headers=auth(ana)).get_json() == {'user': 'ana'}
        assert [(r.rbses_id, r.rbses_last_seen_at) for r in session_rows()] == [before]

    def test_require_admin_never_passes_through_a_key(self, app, whoami, make_user,
                                                      monkeypatch):
        admin = make_user('root', is_admin=True)
        key, _ = api_keys.create(admin.id)
        monkeypatch.setattr(api_keys, 'DENIED_PREFIXES',
                            tuple(p for p in api_keys.DENIED_PREFIXES if p != '/admin/'))
        response = fresh(app).get(f'{API}/admin/overview', headers=auth(key))
        assert response.status_code == 403
        assert response.get_json()['error'] == 'Forbidden'

    def test_the_key_is_never_logged(self, app, ana, caplog):
        caplog.set_level(logging.DEBUG)
        fresh(app).get(WHOAMI, headers=auth(ana))
        fresh(app).post(COLLECTION, headers=auth(ana))
        fresh(app).get(WHOAMI, headers=auth(ana[:-1] + 'x'))
        assert ana[len('rb_live_'):] not in caplog.text


# --- S10: 2FA, password, sessions, block ----------------------------------------------------

class TestIndependence:
    def test_two_factor_does_not_apply(self, app, ana, frozen_clock):
        turn_on_2fa(User.query.filter_by(username='ana').one(), frozen_clock)
        assert fresh(app).get(WHOAMI, headers=auth(ana)).get_json() == {'user': 'ana'}

    def test_a_password_change_and_ending_every_session_keep_the_key(self, app, ana):
        client = login_as(fresh(app), 'ana')
        assert client.patch(f'{API}/me/account', json={
            'password': 'a-new-password', 'current_password': 'testpass123'}).status_code == 200
        assert client.delete(f'{API}/me/sessions').status_code == 200
        cli(app, 'users', 'set-password', 'ana', input='another-password\nanother-password\n')
        assert fresh(app).get(WHOAMI, headers=auth(ana)).get_json() == {'user': 'ana'}

    def test_block_makes_the_key_invalid_and_unblock_makes_it_work(self, app, ana):
        cli(app, 'users', 'block', 'ana')
        refused(fresh(app).get(WHOAMI, headers=auth(ana)), INVALID)
        cli(app, 'users', 'unblock', 'ana')
        assert fresh(app).get(WHOAMI, headers=auth(ana)).get_json() == {'user': 'ana'}


# --- S11: rate limit ------------------------------------------------------------------------

class TestRateLimit:
    def test_sixty_a_minute_per_key(self, limited_app, ana, make_user):
        other = make_user('bo')
        other_key, _ = api_keys.create(other.id)
        client = fresh(limited_app)
        for _ in range(60):
            assert client.get(WHOAMI, headers=auth(ana)).status_code == 200
        response = client.get(WHOAMI, headers=auth(ana))
        assert response.status_code == 429
        body = response.get_json()
        assert (body['code'], body['error']) == ('rate_limited', 'Too Many Requests')
        assert 1 <= int(response.headers['Retry-After']) <= 60
        assert body['params']['retry_after'] == int(response.headers['Retry-After'])
        assert set_cookies(response) == []
        assert client.get(WHOAMI, headers=auth(other_key)).status_code == 200
        assert login_as(fresh(limited_app), 'ana').get(WHOAMI).get_json() == {'user': 'ana'}

    def test_refused_requests_count_too(self, limited_app, ana):
        client = fresh(limited_app)
        for _ in range(60):
            client.post(COLLECTION, headers=auth(ana))
        assert client.get(WHOAMI, headers=auth(ana)).status_code == 429

    def test_the_limit_is_off_with_the_limiter(self, app, ana):
        client = fresh(app)
        for _ in range(61):
            assert client.get(WHOAMI, headers=auth(ana)).status_code == 200


# --- S12: last_used_at and the cost of a key load -------------------------------------------

class TestLastUsed:
    def test_written_at_most_once_a_minute(self, app, ana, frozen_clock):
        start = frozen_clock.now
        assert stored_key().rbapk_last_used_at is None
        fresh(app).get(WHOAMI, headers=auth(ana))
        assert stored_key().rbapk_last_used_at == start
        frozen_clock.advance(seconds=59)
        fresh(app).get(WHOAMI, headers=auth(ana))
        assert stored_key().rbapk_last_used_at == start
        moment = frozen_clock.advance(seconds=1)
        fresh(app).get(WHOAMI, headers=auth(ana))
        assert stored_key().rbapk_last_used_at == moment

    def test_a_refused_key_is_not_marked(self, app, ana, frozen_clock):
        cli(app, 'users', 'block', 'ana')
        fresh(app).get(WHOAMI, headers=auth(ana))
        assert stored_key().rbapk_last_used_at is None

    def _statements(self, app, key):
        db.session.expire_all()
        seen = []

        def record(conn, cursor, statement, parameters, context, executemany):
            seen.append(' '.join(statement.split()))

        event.listen(db.engine, 'before_cursor_execute', record)
        try:
            assert fresh(app).get(WHOAMI, headers=auth(key)).status_code == 200
        finally:
            event.remove(db.engine, 'before_cursor_execute', record)
        return seen

    def test_one_select_per_key_load_and_one_update_when_due(self, app, ana, frozen_clock):
        first = self._statements(app, ana)
        assert first[0].startswith('SELECT') and 'rbapikeys' in first[0] and 'rbusers' in first[0]
        assert first[1].startswith('UPDATE') and 'rbapikeys' in first[1]
        # The commit of the UPDATE expires the user; the route reads it again (as with a
        # session, F9-a). Nothing else touches the key.
        assert [s for s in first[2:] if 'rbapikeys' in s] == [], first
        assert len(first) <= 3, first
        frozen_clock.advance(seconds=30)
        second = self._statements(app, ana)
        assert len(second) == 1, second
        assert second[0].startswith('SELECT') and 'rbapikeys' in second[0]

    def test_a_malformed_key_costs_no_statement(self, app, ana):
        db.session.expire_all()
        seen = []

        def record(conn, cursor, statement, parameters, context, executemany):
            seen.append(statement)

        event.listen(db.engine, 'before_cursor_execute', record)
        try:
            refused(fresh(app).get(WHOAMI, headers=auth('rb_live_short')), INVALID)
        finally:
            event.remove(db.engine, 'before_cursor_execute', record)
        assert seen == []


# --- The service helpers --------------------------------------------------------------------

class TestKeyFormat:
    def test_new_keys(self):
        keys = {api_keys.new_key() for _ in range(50)}
        assert len(keys) == 50
        assert all(api_keys.KEY_FORMAT.fullmatch(k) for k in keys)
        assert all(len(k) == 48 for k in keys)

    def test_the_prefix_is_14_characters(self):
        key = api_keys.new_key()
        assert api_keys.key_prefix(key) == key[:14]
