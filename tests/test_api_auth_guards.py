"""Login protection, sessions and CSRF through the JSON API (LOGIN-2..9, API-4..7, CSRF-1).

The Jinja login and register forms are gone (PR 3/3 of the Jinja retirement); the
React app signs in through /riftbound/api/v1/auth/*. These are the smallest guards
of what still applies there: the lockout, the blocked user, the per-IP rate limits,
the remember cookie, the captcha replay store, and the CSRF token on every unsafe
method.
"""
import base64
import json

import pytest
from altcha import solve_challenge_v1

from app.models import RbCaptchaUsed, User
from tests.auth_helpers import token_payload
from tests.conftest import DEFAULT_PASSWORD, api_csrf_token

API = '/riftbound/api/v1'
LOGIN = f'{API}/auth/login'
SESSION = f'{API}/auth/session'
REGISTER = f'{API}/auth/register'
INVALID = {'success': False, 'error': 'Unauthorized', 'message': 'Invalid credentials',
           'code': 'invalid_credentials'}
NEW_USER = {'username': 'newbie', 'email': 'newbie@test.com', 'password': 'longenough1'}
UNSAFE = {'POST', 'PUT', 'PATCH', 'DELETE'}


def login(client, username='u', password=DEFAULT_PASSWORD, **extra):
    return client.post(LOGIN, json={'username': username, 'password': password, **extra})


def authenticated(client):
    return client.get(SESSION).get_json()['data']['authenticated']


def set_cookies(response, name):
    return [c for c in response.headers.getlist('Set-Cookie') if c.startswith(f'{name}=')]


# --- Lockout (LOGIN-3, R3) ------------------------------------------------------------

class TestLockout:
    def test_the_fifth_failure_locks_for_fifteen_minutes(self, app, client, make_user,
                                                         frozen_clock):
        make_user('u')
        for _ in range(5):
            response = login(client, password='wrong-pass')
            assert (response.status_code, response.get_json()) == (401, INVALID)

        locked = login(client)
        assert locked.status_code == 429
        assert locked.headers['Retry-After'] == '900'
        body = locked.get_json()
        assert (body['code'], body['params']) == ('locked', {'retry_after': 900})
        assert not authenticated(client)

        frozen_clock.advance(minutes=15, seconds=1)
        assert login(client).status_code == 200
        assert authenticated(client)

    def test_failures_below_the_threshold_do_not_lock(self, app, client, make_user, frozen_clock):
        make_user('u')
        for _ in range(4):
            login(client, password='wrong-pass')
        assert login(client).status_code == 200


# --- Blocked users (R4) ---------------------------------------------------------------

class TestBlockedUser:
    def test_the_right_password_is_answered_like_a_wrong_one(self, app, client, make_user):
        make_user('u', is_blocked=True)
        right = login(client)
        wrong = login(client, password='wrong-pass')
        unknown = login(client, username='ghost')
        assert right.status_code == wrong.status_code == unknown.status_code == 401
        assert right.get_json() == wrong.get_json() == unknown.get_json() == INVALID
        assert not authenticated(client)

    def test_a_user_blocked_after_login_is_anonymous(self, app, client, make_user):
        user = make_user('u')
        assert login(client).status_code == 200
        user.is_blocked = True
        from app import db
        db.session.commit()
        assert not authenticated(client)


# --- Per-IP rate limits (LOGIN-7) -----------------------------------------------------

class TestRateLimits:
    def test_the_eleventh_login_in_a_minute_is_429(self, limited_app, client):
        for i in range(10):
            assert login(client, username=f'ghost{i}').status_code == 401
        response = login(client, username='ghost')
        assert response.status_code == 429
        assert int(response.headers['Retry-After']) > 0
        assert response.get_json()['code'] == 'rate_limited'

    def test_the_sixth_register_in_an_hour_is_429(self, limited_app, client):
        for i in range(5):
            assert client.post(REGISTER, json={**NEW_USER, 'username': 'ab'}).status_code == 400
        response = client.post(REGISTER, json=NEW_USER)
        assert response.status_code == 429
        assert response.get_json()['code'] == 'rate_limited'
        assert User.query.filter_by(username='newbie').count() == 0


# --- Remember cookie (API-5, SESS-1) --------------------------------------------------

class TestRememberCookie:
    def test_only_remember_true_issues_it(self, app, make_user):
        make_user('u')
        assert set_cookies(login(app.test_client()), 'remember_token') == []
        assert set_cookies(login(app.test_client(), remember=False), 'remember_token') == []
        [cookie] = set_cookies(login(app.test_client(), remember=True), 'remember_token')
        assert 'HttpOnly' in cookie

    def test_a_non_boolean_remember_is_a_400_and_no_session(self, app, client, make_user):
        make_user('u')
        response = login(client, remember='yes')
        assert response.status_code == 400
        assert response.get_json()['code'] == 'validation_error'
        assert not authenticated(client)

    def test_the_cookie_alone_signs_in_and_logout_expires_it(self, app, client, make_user):
        make_user('u')
        login(client, remember=True)
        client.delete_cookie('session')
        assert authenticated(client)
        logout = client.post(f'{API}/auth/logout')
        assert logout.status_code == 200
        [expired] = set_cookies(logout, 'remember_token')
        assert 'Expires=Thu, 01 Jan 1970' in expired
        assert not authenticated(client)

    def test_a_blocked_user_with_the_cookie_is_anonymous(self, app, client, make_user):
        user = make_user('u')
        login(client, remember=True)
        client.delete_cookie('session')
        user.is_blocked = True
        from app import db
        db.session.commit()
        assert not authenticated(client)


# --- Captcha replay (LOGIN-8) ---------------------------------------------------------

def solved_payload(client):
    issued = client.get(f'{API}/auth/captcha').get_json()['data']['challenge']
    solution = solve_challenge_v1(issued['challenge'], issued['salt'], issued['algorithm'],
                                  issued['maxNumber'])
    payload = {'algorithm': issued['algorithm'], 'challenge': issued['challenge'],
               'number': solution.number, 'salt': issued['salt'],
               'signature': issued['signature']}
    return base64.b64encode(json.dumps(payload).encode()).decode()


class TestCaptcha:
    def test_a_solved_payload_works_once(self, altcha_app, client):
        payload = solved_payload(client)
        first = client.post(REGISTER, json={**NEW_USER, 'altcha': payload})
        assert first.status_code == 201
        replay = client.post(REGISTER, json={'username': 'second', 'email': 'second@test.com',
                                             'password': 'longenough1', 'altcha': payload})
        assert replay.status_code == 400
        assert replay.get_json()['code'] == 'captcha_failed'
        assert User.query.filter_by(username='second').count() == 0
        assert RbCaptchaUsed.query.count() == 1

    def test_no_payload_is_captcha_failed(self, altcha_app, client):
        response = client.post(REGISTER, json=NEW_USER)
        assert response.status_code == 400
        assert response.get_json()['code'] == 'captcha_failed'
        assert User.query.count() == 0


# --- CSRF on every unsafe method (CSRF-1) ---------------------------------------------

def _sample(rule):
    import re
    return re.sub(r'<[^>]+>', lambda m: '1' if m.group(0).startswith('<int:') else 'x',
                  rule.rule)


class TestCsrf:
    def test_every_unsafe_rule_refuses_a_request_without_the_token(self, app, csrf_app, client):
        unsafe = [(method, rule) for rule in app.url_map.iter_rules()
                  for method in sorted(rule.methods & UNSAFE)]
        assert len(unsafe) > 50
        failed = []
        for method, rule in unsafe:
            response = client.open(_sample(rule), method=method, json={})
            body = response.get_json(silent=True) or {}
            if response.status_code != 400 or body.get('code') != 'csrf_invalid':
                failed.append(f'{method} {rule.rule}: {response.status_code} {body.get("code")}')
        assert not failed, '\n'.join(failed)

    @pytest.mark.parametrize('method, path, body', [
        ('PATCH', f'{API}/me/prefs', {'density': 'compact'}),
        ('PUT', f'{API}/locations/order', {'ids': []}),
        ('DELETE', f'{API}/collection/999', None),
        ('POST', f'{API}/auth/logout', None),
    ])
    def test_the_session_token_is_accepted(self, csrf_app, authenticated_client, method, path,
                                           body):
        token = api_csrf_token(authenticated_client)
        response = authenticated_client.open(path, method=method, json=body,
                                             headers={'X-CSRFToken': token})
        assert (response.get_json(silent=True) or {}).get('code') != 'csrf_invalid'
        assert response.status_code in (200, 400, 404)

    def test_the_token_of_another_session_is_refused(self, csrf_app, authenticated_client,
                                                     other_user_client):
        stolen = api_csrf_token(other_user_client)
        assert token_payload(stolen) != token_payload(api_csrf_token(authenticated_client))
        response = authenticated_client.patch(f'{API}/me/prefs', json={'density': 'compact'},
                                              headers={'X-CSRFToken': stolen})
        assert response.status_code == 400
        assert response.get_json()['code'] == 'csrf_invalid'

    def test_login_needs_the_token_too(self, csrf_app, client, make_user):
        make_user('u')
        assert login(client).get_json()['code'] == 'csrf_invalid'
        assert not authenticated(client)
        response = client.post(LOGIN, json={'username': 'u', 'password': DEFAULT_PASSWORD},
                               headers={'X-CSRFToken': api_csrf_token(client)})
        assert response.status_code == 200
        assert authenticated(client)


# --- Unchanged contracts (F9-a S16, CHAR: written and passing before server-side sessions) --

class TestUnchangedContracts:
    def test_the_login_body_is_the_user(self, app, client, make_user):
        user = make_user('u')
        response = login(client)
        assert response.status_code == 200
        assert response.get_json() == {
            'success': True,
            'data': {'user': {'id': user.id, 'username': 'u', 'email': 'u@test.com',
                              'is_admin': False,
                              # F9-b S6: additive keys (the profile's display name, F9-c avatar)
                              'display_name': None, 'avatar_url': None}}}

    def test_the_anonymous_session_body(self, app, client):
        data = client.get(SESSION).get_json()['data']
        assert sorted(data) == ['authenticated', 'csrf_token']
        assert data['authenticated'] is False

    def test_the_signed_in_session_body(self, app, client, make_user):
        user = make_user('u')
        login(client)
        data = client.get(SESSION).get_json()['data']
        assert sorted(data) == ['authenticated', 'csrf_token', 'prefs', 'user']
        assert data['authenticated'] is True
        assert data['user'] == {'id': user.id, 'username': 'u', 'email': 'u@test.com',
                                'is_admin': False, 'display_name': None,   # F9-b S6
                                'avatar_url': None}
        assert sorted(data['prefs']) == ['accent', 'bg_intensity', 'collection_view',
                                         'density', 'playset_size']

    def test_cookie_flags_without_secure_outside_production(self, app, client, make_user):
        make_user('u')
        response = login(client, remember=True)
        for name in ('session', 'remember_token'):
            [cookie] = set_cookies(response, name)
            assert 'HttpOnly' in cookie, name
            assert 'SameSite=Lax' in cookie, name
            assert 'Secure' not in cookie, name

    def test_cookie_flags_with_secure_when_configured(self, app, client, make_user):
        app.config['SESSION_COOKIE_SECURE'] = True
        app.config['REMEMBER_COOKIE_SECURE'] = True
        make_user('u')
        response = login(client, remember=True)
        for name in ('session', 'remember_token'):
            [cookie] = set_cookies(response, name)
            assert 'Secure' in cookie, name
            assert 'HttpOnly' in cookie and 'SameSite=Lax' in cookie, name

    def test_the_remember_cookie_lasts_thirty_days(self, app, client, make_user):
        make_user('u')
        [cookie] = set_cookies(login(client, remember=True), 'remember_token')
        expires = cookie.split('Expires=', 1)[1].split(';', 1)[0]
        from datetime import datetime, timezone
        from email.utils import parsedate_to_datetime
        left = parsedate_to_datetime(expires) - datetime.now(timezone.utc)
        assert 29 < left.total_seconds() / 86400 <= 30


# --- Server-side sessions (F9-a S5, S8, S9, S15) ----------------------------------------------

UA = 'Mozilla/5.0 (X11; Linux x86_64; rv:132.0) Gecko/20100101 Firefox/132.0'


def session_rows():
    import sqlalchemy as sa
    from app import db
    from app.models import RbSession
    db.session.expire_all()
    return db.session.execute(sa.select(RbSession).order_by(RbSession.rbses_id)).scalars().all()


def cookie_value(client, name):
    cookie = client.get_cookie(name)
    return cookie.value if cookie is not None else None


class TestServerSideSessions:
    @pytest.mark.parametrize('remember', [False, True])
    def test_login_creates_one_session_row(self, app, make_user, frozen_clock, remember):
        from datetime import timedelta
        user = make_user('u')
        client = app.test_client()
        response = client.post(LOGIN, json={'username': 'u', 'password': DEFAULT_PASSWORD,
                                            'remember': remember},
                               headers={'User-Agent': UA},
                               environ_base={'REMOTE_ADDR': '198.51.100.23'})
        assert response.status_code == 200
        [row] = session_rows()
        now = frozen_clock.now
        assert (row.rbses_user_id, row.rbses_remember, row.rbses_auth_method, row.rbses_mfa) == (
            user.id, remember, 'password', False)
        assert row.rbses_expires_at == (now + timedelta(days=30) if remember else None)
        assert row.rbses_created_at == row.rbses_last_seen_at == row.rbses_reauth_at == now
        assert (row.rbses_user_agent, row.rbses_ip_prefix) == (UA, '198.51.100.0/24')
        assert row.rbses_revoked_at is None
        assert authenticated(client)

    def test_a_failed_login_creates_no_row(self, app, client, make_user):
        make_user('u')
        assert login(client, password='wrong-pass').status_code == 401
        make_user('b', is_blocked=True)
        assert login(client, username='b').status_code == 401
        assert session_rows() == []

    def test_the_cookies_carry_the_session_identity_not_the_user_id(self, app, client,
                                                                   make_user):
        from flask_login.utils import decode_cookie
        user = make_user('u')
        login(client, remember=True)
        with client.session_transaction() as flask_session:
            identity = flask_session['_user_id']
        assert identity.startswith('s:') and identity != str(user.id)
        assert decode_cookie(cookie_value(client, 'remember_token')) == identity

    def test_logout_revokes_the_session_and_the_old_cookie_is_anonymous(self, app, client,
                                                                        make_user):
        make_user('u')
        login(client)
        old = cookie_value(client, 'session')
        assert client.post(f'{API}/auth/logout').status_code == 200
        [row] = session_rows()
        assert row.rbses_revoked_at is not None
        client.set_cookie('session', old)
        assert not authenticated(client)
        assert client.get(f'{API}/me/prefs').status_code == 401

    def test_the_remember_cookie_signs_in_through_its_row_until_logout(self, app, client,
                                                                       make_user):
        make_user('u')
        login(client, remember=True)
        remember = cookie_value(client, 'remember_token')
        client.delete_cookie('session')
        assert authenticated(client)
        assert len(session_rows()) == 1            # the cookie reused the row, made none
        client.post(f'{API}/auth/logout')
        fresh = app.test_client()
        fresh.set_cookie('remember_token', remember)
        assert not authenticated(fresh)

    def test_the_remember_cookie_stops_after_30_days(self, app, client, make_user,
                                                     frozen_clock):
        make_user('u')
        login(client, remember=True)
        client.delete_cookie('session')
        frozen_clock.advance(days=29, hours=23)
        assert authenticated(client)
        client.delete_cookie('session')
        frozen_clock.advance(hours=1)
        assert not authenticated(client)

    def test_a_session_idle_for_12_hours_is_anonymous(self, app, client, make_user,
                                                      frozen_clock):
        make_user('u')
        login(client)
        frozen_clock.advance(hours=11, minutes=59)
        assert authenticated(client)
        frozen_clock.advance(hours=12)
        assert not authenticated(client)

    def test_a_pre_f9_session_cookie_is_anonymous(self, app, client, make_user):
        user = make_user('u')
        with client.session_transaction() as flask_session:
            flask_session['_user_id'] = str(user.id)
            flask_session['_fresh'] = True
        assert not authenticated(client)
        response = client.get(f'{API}/me/prefs')
        assert (response.status_code, response.get_json()['code']) == (401, 'unauthenticated')
        assert session_rows() == []

    def test_a_pre_f9_remember_cookie_is_anonymous(self, app, client, make_user):
        from flask_login.utils import encode_cookie
        user = make_user('u')
        client.set_cookie('remember_token', encode_cookie(str(user.id)))
        assert not authenticated(client)
        assert client.get(f'{API}/me/prefs').status_code == 401
        assert session_rows() == []

    def test_a_password_change_ends_the_other_sessions_and_keeps_this_one(self, app,
                                                                         make_user):
        make_user('u')
        here, there = app.test_client(), app.test_client()
        login(here)
        login(there, remember=True)
        response = here.patch(f'{API}/me/account', json={
            'current_password': DEFAULT_PASSWORD, 'password': 'brand-new-pass'})
        assert response.status_code == 200
        assert authenticated(here)
        there.delete_cookie('session')            # the remember cookie alone, too
        assert not authenticated(there)
        assert [r.rbses_revoked_at is None for r in session_rows()] == [True, False]

    def test_an_email_change_ends_nothing(self, app, make_user):
        make_user('u')
        here, there = app.test_client(), app.test_client()
        login(here)
        login(there)
        assert here.patch(f'{API}/me/account', json={'email': 'new@test.com'}).status_code == 200
        assert authenticated(here) and authenticated(there)
        assert [r.rbses_revoked_at for r in session_rows()] == [None, None]

    def test_a_wrong_current_password_ends_nothing(self, app, make_user):
        make_user('u')
        here, there = app.test_client(), app.test_client()
        login(here)
        login(there)
        response = here.patch(f'{API}/me/account', json={
            'current_password': 'not-it', 'password': 'brand-new-pass'})
        assert response.status_code == 400
        assert authenticated(there)

    def test_a_lost_email_race_with_a_password_change_ends_nothing(self, app, make_user,
                                                                   monkeypatch):
        import sqlalchemy as sa
        from app.services import account
        make_user('u')
        make_user('taken', email='taken@test.com')
        here, there = app.test_client(), app.test_client()
        login(here)
        login(there)
        # The pre-check misses the other account, as when it registers at the same moment.
        monkeypatch.setattr(account, 'func', type('F', (), {
            'lower': staticmethod(lambda column: sa.literal('never-matches'))}))
        response = here.patch(f'{API}/me/account', json={
            'email': 'taken@test.com', 'current_password': DEFAULT_PASSWORD,
            'password': 'brand-new-pass'})
        assert (response.status_code, response.get_json()['code']) == (409, 'email_taken')
        assert authenticated(here) and authenticated(there)
        assert [r.rbses_revoked_at for r in session_rows()] == [None, None]


# --- Accounts without a password or an e-mail (F9-b S2, S3, S4) --------------------------------

def _no_password(user):
    from app import db
    user.password_hash = None
    db.session.commit()
    return user


def _stored(username):
    from app import db
    db.session.expire_all()
    return User.query.filter_by(username=username).one()


class TestAccountWithoutPassword:
    def test_login_is_answered_like_a_wrong_password(self, app, client, make_user):
        _no_password(make_user('u'))
        for password in (DEFAULT_PASSWORD, 'anything-else'):
            response = login(client, password=password)
            assert (response.status_code, response.get_json()) == (401, INVALID)
        assert not authenticated(client)

    def test_login_runs_the_dummy_check_once(self, app, client, make_user, monkeypatch):
        from app.services import auth
        _no_password(make_user('u'))
        checked = []
        real = auth.check_password_hash
        monkeypatch.setattr(auth, 'check_password_hash',
                            lambda stored, given: checked.append(stored) or real(stored, given))
        assert login(client).status_code == 401
        assert checked == [auth._dummy_hash()]

    def test_login_counts_no_failure_and_never_locks(self, app, client, make_user,
                                                    frozen_clock):
        _no_password(make_user('u'))
        for _ in range(7):
            assert login(client).get_json() == INVALID
        user = _stored('u')
        assert (user.failed_login_count, user.locked_until) == (0, None)

    def test_the_model_helpers(self, app, make_user):
        user = make_user('u')
        assert user.has_password is True
        _no_password(user)
        assert user.has_password is False
        assert user.check_password('') is False
        assert user.check_password(DEFAULT_PASSWORD) is False


class TestRegisterWithoutEmail:
    @pytest.mark.parametrize('email', ['absent', None, '', '   '])
    def test_stores_no_email(self, app, client, email):
        body = {k: v for k, v in NEW_USER.items() if k != 'email'}
        if email != 'absent':
            body['email'] = email
        response = client.post(REGISTER, json=body)
        assert response.status_code == 201, response.get_json()
        assert _stored('newbie').email is None

    def test_two_accounts_without_email_coexist(self, app, client):
        for name in ('first', 'second'):
            response = client.post(REGISTER, json={'username': name, 'password': 'longenough1'})
            assert response.status_code == 201
        assert [u.email for u in User.query.order_by(User.username)] == [None, None]

    def test_a_present_email_keeps_its_rules(self, app, client, make_user):
        make_user('taken', email='Taken@Test.com')
        bad = client.post(REGISTER, json={**NEW_USER, 'email': 'no-at-sign'})
        assert (bad.status_code, bad.get_json()['details'][0]['field']) == (400, 'email')
        long = client.post(REGISTER, json={**NEW_USER, 'email': 'a' * 112 + '@test.com'})
        assert long.get_json()['details'][0]['code'] == 'too_long'
        taken = client.post(REGISTER, json={**NEW_USER, 'email': ' taken@TEST.com '})
        assert (taken.status_code, taken.get_json()['code']) == (409, 'email_taken')
        ok = client.post(REGISTER, json={**NEW_USER, 'email': ' Newbie@Test.com '})
        assert ok.status_code == 201
        assert _stored('newbie').email == 'Newbie@Test.com'

    def test_registration_stamps_password_changed_at(self, app, client, frozen_clock):
        assert client.post(REGISTER, json=NEW_USER).status_code == 201
        assert _stored('newbie').password_changed_at == frozen_clock.now
