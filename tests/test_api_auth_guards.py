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


# --- Two-factor step at sign-in (F9-e S2-S7, S9) ---------------------------------------------

MFA = f'{API}/auth/mfa'
ME = f'{API}/me'
MFA_REQUIRED = {'success': True, 'data': {'mfa_required': True, 'methods': ['totp', 'recovery']}}
MFA_EXPIRED = {'success': False, 'error': 'Unauthorized', 'message': 'The sign-in step expired',
               'code': 'mfa_expired'}
MFA_INVALID = {'success': False, 'error': 'Unauthorized', 'message': 'The code is not valid',
               'code': 'mfa_invalid'}
MFA_UNAVAILABLE = {'success': False, 'error': 'Service Unavailable',
                   'message': 'Two-factor authentication is not available'}
WRONG_CODE = '000000'


def pending_of(client):
    """The pending step the Flask session of `client` holds (None without one)."""
    with client.session_transaction() as flask_session:
        return flask_session.get('mfa_pending')


def stored_user(username='u'):
    from app import db
    db.session.expire_all()
    return User.query.filter_by(username=username).one()


def wrong_code(secret, now):
    """A six-digit code that is not valid around `now`."""
    from tests.auth_helpers import totp_code
    valid = {totp_code(secret, now, offset) for offset in (-1, 0, 1)}
    return next(c for c in (WRONG_CODE, '111111', '222222', '333333') if c not in valid)


@pytest.fixture
def two_fa(app, make_user, frozen_clock):
    """User `u` with 2FA on; returns `(user, secret, recovery codes)`."""
    from tests.auth_helpers import turn_on_2fa
    user = make_user('u')
    secret, codes = turn_on_2fa(user, frozen_clock)
    return user, secret, codes


def code_now(two_fa, frozen_clock, offset=0):
    from tests.auth_helpers import totp_code
    return totp_code(two_fa[1], frozen_clock.now, offset)


class TestTwoFactorSignIn:
    # S2 -------------------------------------------------------------------------------------
    def test_the_right_password_asks_for_the_code_and_creates_no_session(self, app, client,
                                                                        two_fa, frozen_clock):
        from app import db
        user = two_fa[0]
        user.failed_login_count = 2
        db.session.commit()
        response = login(client, remember=True)
        assert (response.status_code, response.get_json()) == (200, MFA_REQUIRED)
        assert set_cookies(response, 'remember_token') == []
        assert session_rows() == []
        assert not authenticated(client)
        stored = stored_user()
        assert (stored.failed_login_count, stored.locked_until, stored.last_login_at) == (
            2, None, None)
        assert pending_of(client) == {'uid': user.id, 'remember': True, 'method': 'password',
                                      'started_at': frozen_clock.now.isoformat(), 'attempts': 0}
        with client.session_transaction() as flask_session:
            assert '_user_id' not in flask_session

    def test_wrong_password_locked_and_blocked_answers_are_unchanged(self, app, client, two_fa,
                                                                     frozen_clock):
        from app import db
        wrong = login(client, password='wrong-pass')
        assert (wrong.status_code, wrong.get_json()) == (401, INVALID)
        assert stored_user().failed_login_count == 1
        assert pending_of(client) is None
        two_fa[0].is_blocked = True
        db.session.commit()
        blocked = login(client)
        assert (blocked.status_code, blocked.get_json()) == (401, INVALID)
        assert pending_of(client) is None
        two_fa[0].is_blocked = False
        two_fa[0].locked_until = frozen_clock.now + __import__('datetime').timedelta(minutes=3)
        db.session.commit()
        locked = login(client)
        assert (locked.status_code, locked.get_json()['code']) == (429, 'locked')
        assert locked.headers['Retry-After'] == '180'
        assert pending_of(client) is None
        assert session_rows() == []

    def test_a_new_login_replaces_the_pending_step(self, app, client, two_fa, frozen_clock,
                                                   make_user):
        login(client, remember=True)
        client.post(MFA, json={'code': wrong_code(two_fa[1], frozen_clock.now)})
        assert pending_of(client)['attempts'] == 1
        frozen_clock.advance(minutes=1)
        assert login(client).get_json() == MFA_REQUIRED
        assert pending_of(client) == {'uid': two_fa[0].id, 'remember': False,
                                      'method': 'password',
                                      'started_at': frozen_clock.now.isoformat(), 'attempts': 0}
        make_user('plain')
        assert login(client, username='plain').status_code == 200
        assert pending_of(client) is None
        assert authenticated(client)

    def test_a_failed_login_ends_the_pending_step_too(self, app, client, two_fa):
        login(client)
        assert login(client, password='wrong-pass').status_code == 401
        assert pending_of(client) is None

    def test_a_signed_in_client_that_starts_a_2fa_login_is_signed_out(self, app, client,
                                                                      two_fa, make_user):
        make_user('plain')
        login(client, username='plain', remember=True)
        assert authenticated(client)
        response = login(client)
        assert response.get_json() == MFA_REQUIRED
        [expired] = set_cookies(response, 'remember_token')
        assert 'Expires=Thu, 01 Jan 1970' in expired
        assert not authenticated(client)
        assert client.get(ME).status_code == 401
        [row] = session_rows()
        assert row.rbses_revoked_at is not None

    def test_a_user_without_2fa_has_no_pending_step(self, app, client, make_user):
        make_user('u')
        response = login(client)
        assert list(response.get_json()['data']) == ['user']
        assert pending_of(client) is None

    def test_a_failed_login_without_2fa_writes_no_cookie(self, app, client, make_user):
        make_user('u')
        response = login(client, password='wrong-pass')
        assert response.headers.getlist('Set-Cookie') == []
        assert 'Cookie' not in response.headers.get('Vary', '')

    # S3 -------------------------------------------------------------------------------------
    def test_the_step_lasts_five_minutes(self, app, two_fa, frozen_clock):
        late, on_time = app.test_client(), app.test_client()
        login(late)
        login(on_time)
        frozen_clock.advance(minutes=4, seconds=59)
        assert on_time.post(MFA, json={'code': code_now(two_fa, frozen_clock)}).status_code == 200
        frozen_clock.advance(seconds=2)
        response = late.post(MFA, json={'code': code_now(two_fa, frozen_clock)})
        assert (response.status_code, response.get_json()) == (401, MFA_EXPIRED)
        assert pending_of(late) is None
        assert not authenticated(late)
        assert stored_user().failed_login_count == 0

    def test_five_wrong_codes_end_the_step(self, app, client, two_fa, frozen_clock):
        app.config['LOGIN_MAX_FAILURES'] = 10
        login(client)
        bad = wrong_code(two_fa[1], frozen_clock.now)
        for attempt in range(1, 5):
            response = client.post(MFA, json={'code': bad})
            assert (response.status_code, response.get_json()) == (401, MFA_INVALID)
            assert pending_of(client)['attempts'] == attempt
        fifth = client.post(MFA, json={'code': bad})
        assert (fifth.status_code, fifth.get_json()) == (401, MFA_INVALID)
        assert pending_of(client) is None
        right = client.post(MFA, json={'code': code_now(two_fa, frozen_clock)})
        assert (right.status_code, right.get_json()) == (401, MFA_EXPIRED)
        assert not authenticated(client)
        assert stored_user().failed_login_count == 5

    def test_logout_ends_the_pending_step(self, app, client, two_fa, frozen_clock):
        login(client)
        response = client.post(f'{API}/auth/logout')
        assert (response.status_code, response.get_json()) == (200, {'success': True,
                                                                     'data': {}})
        assert pending_of(client) is None
        after = client.post(MFA, json={'code': code_now(two_fa, frozen_clock)})
        assert after.get_json() == MFA_EXPIRED

    def test_logout_without_a_session_or_step_is_still_401(self, app, client):
        response = client.post(f'{API}/auth/logout')
        assert (response.status_code, response.get_json()['code']) == (401, 'unauthenticated')

    def test_the_session_endpoint_flags_a_live_step_only(self, app, client, two_fa,
                                                         frozen_clock):
        login(client)
        data = client.get(SESSION).get_json()['data']
        assert sorted(data) == ['authenticated', 'csrf_token', 'mfa_pending']
        assert (data['authenticated'], data['mfa_pending']) == (False, True)
        frozen_clock.advance(minutes=5, seconds=1)
        assert sorted(client.get(SESSION).get_json()['data']) == ['authenticated', 'csrf_token']

    @pytest.mark.parametrize('path', [ME, f'{API}/me/prefs', f'{API}/me/sessions',
                                      f'{API}/collection', f'{API}/decks'])
    def test_every_signed_in_route_is_401_during_the_step(self, app, client, two_fa, path):
        login(client, remember=True)
        response = client.get(path)
        assert (response.status_code, response.get_json()['code']) == (401, 'unauthenticated')

    # S4 -------------------------------------------------------------------------------------
    @pytest.mark.parametrize('body', [{}, {'code': '123456', 'recovery_code': 'abcde-fghjk'},
                                      {'code': None, 'recovery_code': None}, {'code': ''},
                                      {'recovery_code': ''}, {'code': 'x' * 65}])
    def test_the_body_needs_exactly_one_code(self, app, client, two_fa, body):
        login(client)
        response = client.post(MFA, json=body)
        assert response.status_code == 400
        assert response.get_json()['code'] == 'validation_error'
        assert pending_of(client)['attempts'] == 0
        assert stored_user().failed_login_count == 0

    def test_without_a_pending_step_is_mfa_expired(self, app, client, two_fa, frozen_clock):
        response = client.post(MFA, json={'code': code_now(two_fa, frozen_clock)})
        assert (response.status_code, response.get_json()) == (401, MFA_EXPIRED)
        assert session_rows() == []

    @pytest.mark.parametrize('change', ['blocked', 'deleted', '2fa_off'])
    def test_a_user_that_changed_meanwhile_is_mfa_expired(self, app, client, two_fa,
                                                          frozen_clock, change):
        from app import db
        from app.services import mfa
        login(client)
        user = two_fa[0]
        if change == 'blocked':
            user.is_blocked = True
            db.session.commit()
        elif change == 'deleted':
            db.session.delete(user)
            db.session.commit()
        else:
            assert mfa.reset(user) == 0
        response = client.post(MFA, json={'code': code_now(two_fa, frozen_clock)})
        assert (response.status_code, response.get_json()) == (401, MFA_EXPIRED)
        assert pending_of(client) is None
        assert session_rows() == []
        assert not authenticated(client)

    def test_a_lock_that_started_meanwhile_is_429(self, app, client, two_fa, frozen_clock):
        from datetime import timedelta
        from app import db
        login(client)
        two_fa[0].locked_until = frozen_clock.now + timedelta(minutes=2)
        db.session.commit()
        response = client.post(MFA, json={'code': code_now(two_fa, frozen_clock)})
        assert response.status_code == 429
        assert response.headers['Retry-After'] == '120'
        assert response.get_json() == {
            'success': False, 'error': 'Too Many Requests',
            'message': 'Invalid credentials or account temporarily locked', 'code': 'locked',
            'params': {'retry_after': 120}}
        assert pending_of(client) is None
        assert session_rows() == []

    def test_a_wrong_code_counts_one_login_failure(self, app, client, two_fa, frozen_clock):
        login(client)
        response = client.post(MFA, json={'code': wrong_code(two_fa[1], frozen_clock.now)})
        assert (response.status_code, response.get_json()) == (401, MFA_INVALID)
        assert pending_of(client)['attempts'] == 1
        assert stored_user().failed_login_count == 1
        assert session_rows() == [] and not authenticated(client)

    @pytest.mark.parametrize('bad', ['12345', 'abcdef', 'zzzzz-zzzzz'])
    def test_a_malformed_code_counts_too(self, app, client, two_fa, bad):
        login(client)
        response = client.post(MFA, json={'code': bad})
        assert (response.status_code, response.get_json()) == (401, MFA_INVALID)
        assert stored_user().failed_login_count == 1

    def test_the_right_code_signs_in(self, app, client, two_fa, frozen_clock):
        from app.services.profile import user_payload
        user = two_fa[0]
        login(client)
        frozen_clock.advance(seconds=10)
        response = client.post(MFA, json={'code': code_now(two_fa, frozen_clock)})
        assert response.status_code == 200
        assert response.get_json() == {'success': True, 'data': {
            'user': user_payload(stored_user()), 'recovery_code_used': False,
            'recovery_codes_left': 10}}
        assert response.get_json()['data']['user']['username'] == 'u'
        [row] = session_rows()
        assert (row.rbses_user_id, row.rbses_mfa, row.rbses_auth_method, row.rbses_remember) == (
            user.id, True, 'password', False)
        stored = stored_user()
        assert (stored.failed_login_count, stored.locked_until, stored.last_login_at) == (
            0, None, frozen_clock.now)
        assert pending_of(client) is None
        assert authenticated(client)
        assert client.get(ME).status_code == 200
        assert 'mfa_pending' not in client.get(SESSION).get_json()['data']

    def test_an_adjacent_code_with_spaces_works(self, app, client, two_fa, frozen_clock):
        login(client)
        given = code_now(two_fa, frozen_clock, offset=1)   # -1 is the enabling step: a replay
        response = client.post(MFA, json={'code': f'{given[:3]} {given[3:]}'})
        assert response.status_code == 200

    def test_the_same_code_is_never_accepted_twice(self, app, two_fa, frozen_clock):
        first, second = app.test_client(), app.test_client()
        code = code_now(two_fa, frozen_clock)
        login(first)
        login(second)
        assert first.post(MFA, json={'code': code}).status_code == 200
        replay = second.post(MFA, json={'code': code})
        assert (replay.status_code, replay.get_json()) == (401, MFA_INVALID)
        assert not authenticated(second)
        assert stored_user().failed_login_count == 1

    def test_a_recovery_code_signs_in_once(self, app, two_fa, frozen_clock):
        first, second = app.test_client(), app.test_client()
        recovery = two_fa[2][3]
        login(first)
        response = first.post(MFA, json={'recovery_code': recovery.upper().replace('-', ' ')})
        assert response.status_code == 200
        data = response.get_json()['data']
        assert (data['recovery_code_used'], data['recovery_codes_left']) == (True, 9)
        [row] = session_rows()
        assert row.rbses_mfa is True
        login(second)
        again = second.post(MFA, json={'recovery_code': recovery})
        assert (again.status_code, again.get_json()) == (401, MFA_INVALID)
        assert stored_user().failed_login_count == 1

    def test_an_unknown_recovery_code_is_invalid(self, app, client, two_fa):
        login(client)
        response = client.post(MFA, json={'recovery_code': 'zzzzz-zzzzz'})
        assert (response.status_code, response.get_json()) == (401, MFA_INVALID)
        assert stored_user().failed_login_count == 1

    def test_a_totp_code_sent_as_a_recovery_code_is_invalid(self, app, client, two_fa,
                                                            frozen_clock):
        login(client)
        response = client.post(MFA, json={'recovery_code': code_now(two_fa, frozen_clock)})
        assert response.get_json() == MFA_INVALID

    def test_an_undecryptable_secret_is_503_but_a_recovery_code_works(self, app, client,
                                                                      two_fa, frozen_clock,
                                                                      caplog):
        from cryptography.fernet import Fernet
        login(client)
        app.config['TOTP_ENCRYPTION_KEY'] = Fernet.generate_key().decode()
        response = client.post(MFA, json={'code': code_now(two_fa, frozen_clock)})
        assert (response.status_code, response.get_json()) == (503, MFA_UNAVAILABLE)
        assert two_fa[1] not in caplog.text
        assert pending_of(client)['attempts'] == 0
        assert stored_user().failed_login_count == 0
        assert session_rows() == []
        recovered = client.post(MFA, json={'recovery_code': two_fa[2][0]})
        assert recovered.status_code == 200
        assert recovered.get_json()['data']['recovery_codes_left'] == 9
        assert authenticated(client)

    def test_without_a_key_the_code_is_503_and_a_recovery_code_works(self, app, client,
                                                                     two_fa, frozen_clock):
        app.config['TOTP_ENCRYPTION_KEY'] = None
        assert login(client).get_json() == MFA_REQUIRED
        response = client.post(MFA, json={'code': code_now(two_fa, frozen_clock)})
        assert (response.status_code, response.get_json()) == (503, MFA_UNAVAILABLE)
        assert client.post(MFA, json={'recovery_code': two_fa[2][0]}).status_code == 200
        assert authenticated(client)

    # S5 -------------------------------------------------------------------------------------
    def test_the_eleventh_code_in_a_minute_is_429(self, limited_app, client):
        for _ in range(10):
            assert client.post(MFA, json={'code': WRONG_CODE}).get_json() == MFA_EXPIRED
        response = client.post(MFA, json={'code': WRONG_CODE})
        assert response.status_code == 429
        assert int(response.headers['Retry-After']) > 0
        assert response.get_json()['code'] == 'rate_limited'

    def test_the_code_limit_is_not_the_login_limit(self, limited_app, client):
        for i in range(10):
            assert login(client, username=f'ghost{i}').status_code == 401
        assert client.post(MFA, json={'code': WRONG_CODE}).status_code == 401

    # S6 -------------------------------------------------------------------------------------
    def test_the_lockout_example(self, app, client, two_fa, frozen_clock):
        assert login(client).get_json() == MFA_REQUIRED
        bad = wrong_code(two_fa[1], frozen_clock.now)
        for count in range(1, 5):
            response = client.post(MFA, json={'code': bad})
            assert (response.status_code, response.get_json()) == (401, MFA_INVALID)
            assert stored_user().failed_login_count == count
        fifth = client.post(MFA, json={'code': bad})
        assert fifth.status_code == 429
        assert fifth.headers['Retry-After'] == '900'
        assert (fifth.get_json()['code'], fifth.get_json()['params']) == (
            'locked', {'retry_after': 900})
        assert stored_user().locked_until == frozen_clock.now + __import__(
            'datetime').timedelta(minutes=15)
        assert pending_of(client) is None
        frozen_clock.advance(minutes=1)
        later = login(client)
        assert (later.status_code, later.get_json()['code']) == (429, 'locked')
        assert later.headers['Retry-After'] == '840'
        assert not authenticated(client) and session_rows() == []

    def test_a_right_code_after_three_wrong_ones_resets_the_count(self, app, client, two_fa,
                                                                  frozen_clock):
        login(client)
        bad = wrong_code(two_fa[1], frozen_clock.now)
        for _ in range(3):
            client.post(MFA, json={'code': bad})
        assert stored_user().failed_login_count == 3
        assert client.post(MFA, json={'code': code_now(two_fa, frozen_clock)}).status_code == 200
        assert (stored_user().failed_login_count, stored_user().locked_until) == (0, None)

    def test_wrong_passwords_and_wrong_codes_share_the_count(self, app, client, two_fa,
                                                             frozen_clock):
        for _ in range(3):
            login(client, password='wrong-pass')
        assert login(client).get_json() == MFA_REQUIRED
        assert stored_user().failed_login_count == 3
        bad = wrong_code(two_fa[1], frozen_clock.now)
        assert client.post(MFA, json={'code': bad}).status_code == 401
        assert client.post(MFA, json={'code': bad}).status_code == 429

    # S7 -------------------------------------------------------------------------------------
    @pytest.mark.parametrize('remember', [False, True])
    def test_remember_reaches_the_session(self, app, client, two_fa, frozen_clock, remember):
        from datetime import timedelta
        login(client, remember=remember)
        response = client.post(MFA, json={'code': code_now(two_fa, frozen_clock)})
        assert response.status_code == 200
        cookies = set_cookies(response, 'remember_token')
        assert len(cookies) == (1 if remember else 0)
        [row] = session_rows()
        assert row.rbses_remember is remember
        assert row.rbses_expires_at == (frozen_clock.now + timedelta(days=30) if remember
                                        else None)
        if remember:
            client.delete_cookie('session')
            assert authenticated(client)

    # CSRF -----------------------------------------------------------------------------------
    def test_the_code_needs_the_csrf_token(self, csrf_app, client, two_fa, frozen_clock):
        token = api_csrf_token(client)
        assert client.post(LOGIN, json={'username': 'u', 'password': DEFAULT_PASSWORD},
                           headers={'X-CSRFToken': token}).get_json() == MFA_REQUIRED
        refused = client.post(MFA, json={'code': code_now(two_fa, frozen_clock)})
        assert (refused.status_code, refused.get_json()['code']) == (400, 'csrf_invalid')
        assert pending_of(client)['attempts'] == 0
        accepted = client.post(MFA, json={'code': code_now(two_fa, frozen_clock)},
                               headers={'X-CSRFToken': api_csrf_token(client)})
        assert accepted.status_code == 200
        assert authenticated(client)


# --- No way around the second factor (F9-e S1, S8) --------------------------------------------

class TestNoMfaBypass:
    def test_only_the_session_service_calls_login_user(self):
        import re
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent / 'app'
        callers, identity = [], []
        for path in sorted(root.rglob('*.py')):
            text = path.read_text(encoding='utf-8')
            relative = path.relative_to(root.parent).as_posix()
            if re.search(r'\blogin_user\b', text):
                callers.append(relative)
            if re.search(r"""\[\s*['"]_user_id['"]\s*\]\s*=""", text):
                identity.append(relative)
        assert callers == ['app/services/sessions.py']
        assert identity == []
        sessions_text = (root / 'services' / 'sessions.py').read_text(encoding='utf-8')
        assert len(re.findall(r'\blogin_user\(', sessions_text)) == 1

    def test_the_password_alone_never_reaches_the_account(self, app, client, two_fa):
        assert login(client, remember=True).get_json() == MFA_REQUIRED
        assert client.get(ME).status_code == 401
        client.delete_cookie('session')
        assert client.get_cookie('remember_token') is None
        assert client.get(ME).status_code == 401
        assert session_rows() == []

    def test_a_pending_step_is_not_a_session(self, app, client, two_fa):
        login(client)
        with client.session_transaction() as flask_session:
            assert '_user_id' not in flask_session
        assert client.get(SESSION).get_json()['data']['authenticated'] is False
        assert client.post(f'{API}/me/reauth',
                           json={'password': DEFAULT_PASSWORD}).status_code == 401

    def test_sessions_from_before_2fa_was_turned_on_stay_anonymous(self, app, make_user,
                                                                   frozen_clock):
        from tests.auth_helpers import totp_code
        from tests.conftest import login_as
        make_user('u')
        before = app.test_client()
        login(before, remember=True)
        old_session = cookie_value(before, 'session')
        old_remember = cookie_value(before, 'remember_token')
        owner = login_as(app.test_client(), 'u')
        secret = owner.post(f'{API}/me/2fa/setup').get_json()['data']['secret'].replace(' ', '')
        enabled = owner.post(f'{API}/me/2fa/enable',
                             json={'code': totp_code(secret, frozen_clock.now)})
        assert enabled.get_json()['data']['revoked_sessions'] == 1
        assert not authenticated(before)
        for name, value in (('session', old_session), ('remember_token', old_remember)):
            fresh = app.test_client()
            fresh.set_cookie(name, value)
            assert not authenticated(fresh), name
            assert fresh.get(ME).status_code == 401

    def test_a_pending_step_completes_only_for_its_own_user(self, app, client, make_user,
                                                            frozen_clock):
        from tests.auth_helpers import totp_code, turn_on_2fa
        ana, bo = make_user('ana'), make_user('bo')
        turn_on_2fa(ana, frozen_clock)
        bo_secret, _ = turn_on_2fa(bo, frozen_clock)
        assert login(client, username='ana').get_json() == MFA_REQUIRED
        response = client.post(MFA, json={'code': totp_code(bo_secret, frozen_clock.now)})
        assert response.get_json() == MFA_INVALID
        assert (stored_user('ana').failed_login_count, stored_user('bo').failed_login_count) == (
            1, 0)
        assert not authenticated(client)
        assert session_rows() == []

    def test_a_copied_step_still_needs_the_code_and_shares_the_count(self, app, two_fa,
                                                                     frozen_clock):
        first, copy = app.test_client(), app.test_client()
        login(first)
        copy.set_cookie('session', cookie_value(first, 'session'))
        assert not authenticated(copy)
        assert copy.get(ME).status_code == 401
        bad = wrong_code(two_fa[1], frozen_clock.now)
        for client in (first, first, copy, copy):
            assert client.post(MFA, json={'code': bad}).get_json() == MFA_INVALID
        locked = copy.post(MFA, json={'code': bad})
        assert (locked.status_code, locked.get_json()['code']) == (429, 'locked')
        assert stored_user().failed_login_count == 5
        assert first.post(MFA, json={'code': code_now(two_fa, frozen_clock)}).status_code == 429
        assert session_rows() == []

    def test_the_session_service_refuses_a_missing_second_factor(self, app, two_fa):
        from app.services import sessions
        with app.test_request_context():
            with pytest.raises(sessions.SecondFactorRequired):
                sessions.sign_in(two_fa[0], remember=True, auth_method='password',
                                 mfa_passed=False)
            with pytest.raises(sessions.SecondFactorRequired):
                sessions.sign_in(two_fa[0], remember=False)
        assert session_rows() == []

    def test_an_admin_with_2fa_needs_the_code_for_the_admin_api(self, app, client, make_user,
                                                                 frozen_clock):
        from tests.auth_helpers import totp_code, turn_on_2fa
        admin = make_user('boss', is_admin=True)
        secret, _ = turn_on_2fa(admin, frozen_clock)
        assert login(client, username='boss').get_json() == MFA_REQUIRED
        denied = client.get(f'{API}/admin/overview')
        assert (denied.status_code, denied.get_json()['code']) == (401, 'unauthenticated')
        assert client.post(MFA, json={'code': totp_code(secret, frozen_clock.now)}
                           ).status_code == 200
        assert client.get(f'{API}/admin/overview').status_code == 200

    def test_registering_never_signs_in(self, app, client):
        response = client.post(REGISTER, json=NEW_USER)
        assert response.status_code == 201
        assert not authenticated(client)
        assert session_rows() == []
