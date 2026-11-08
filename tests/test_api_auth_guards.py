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
