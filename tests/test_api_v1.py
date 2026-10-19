"""JSON API v1 under /riftbound/api/v1 (API-1..7, unit e).

Success envelope: {"success": true, "data": {...}, "meta": {...}?}
Error envelope:   {"success": false, "error": "<name>", "message": "...", "details": [...]?}

The default test app has CSRF, the rate limiter and the captcha OFF; the
`csrf_app`, `limited_app` and `altcha_app` fixtures turn one of them on.
Request `make_user` / `admin_client` BEFORE `csrf_app` (they log in through the
form).
"""
import pytest
from sqlalchemy.exc import OperationalError

from app import db
from app.models import RbCaptchaUsed, User
from config import load_settings
from tests.test_captcha import solve

API = '/riftbound/api/v1'
PASSWORD = 'Passw0rd!x'
NEW_USER = {'username': 'newbie', 'email': 'newbie@test.com', 'password': 'longenough1'}
USER_KEYS = {'id', 'username', 'email', 'is_admin'}


def post_json(client, path, body, **headers):
    return client.post(f'{API}{path}', json=body, headers=headers)


def session_of(client, **headers):
    return client.get(f'{API}/auth/session', headers=headers).get_json()['data']


def assert_error(resp, status, error):
    assert resp.status_code == status
    assert resp.is_json
    body = resp.get_json()
    assert body['success'] is False
    assert body['error'] == error
    assert isinstance(body['message'], str) and body['message']
    return body


# ---------------------------------------------------------------------------
# API-1 blueprint and envelope
# ---------------------------------------------------------------------------

class TestEnvelope:
    def test_unknown_path_with_a_browser_accept_is_a_json_404(self, client):
        resp = client.get(f'{API}/nope', headers={
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'})
        assert_error(resp, 404, 'Not Found')
        assert resp.content_type.startswith('application/json')

    def test_unknown_path_without_accept_is_json_too(self, client):
        assert_error(client.get(f'{API}/nope'), 404, 'Not Found')

    def test_wrong_method_is_a_json_405(self, client):
        resp = client.post(f'{API}/health')
        assert_error(resp, 405, 'Method Not Allowed')
        assert 'GET' in resp.headers['Allow']

    def test_wrong_content_type_is_a_json_415_or_400_never_html(self, client):
        # A raw non-JSON body to a JSON endpoint: still the envelope.
        resp = client.post(f'{API}/auth/login', data='username=u&password=p',
                           content_type='application/x-www-form-urlencoded',
                           headers={'Accept': 'text/html'})
        assert resp.is_json
        assert resp.get_json()['success'] is False
        assert resp.status_code in (400, 415)

    def test_an_unhandled_exception_is_a_generic_500(self, app, client):
        def boom():
            raise ValueError('secret detail')
        app.add_url_rule(f'{API}/boom', 'boom_for_test', boom)
        resp = client.get(f'{API}/boom', headers={'Accept': 'text/html'})
        body = assert_error(resp, 500, 'Internal Server Error')
        assert 'secret detail' not in resp.get_data(as_text=True)
        assert 'ValueError' not in resp.get_data(as_text=True)
        assert 'Traceback' not in body['message']

    def test_the_blueprint_handler_answers_an_unhandled_exception(
            self, app, client, monkeypatch, caplog):
        """API-1: the generic 500 comes from the `api_v1` handler itself.

        The app-level handler would give the same envelope, so the test
        spies on the name the blueprint handler calls (the app-level one
        registered its own reference at startup and is not affected) and
        raises from a REAL endpoint of the blueprint.
        """
        import app.api.v1 as api_pkg
        calls = []
        real = api_pkg.unexpected_error_response

        def spy(error):
            calls.append(error)
            return real(error)

        def boom():
            raise ValueError('secret detail')

        monkeypatch.setattr(api_pkg, 'unexpected_error_response', spy)
        monkeypatch.setitem(app.view_functions, 'api_v1.health', boom)
        resp = client.get(f'{API}/health', headers={'Accept': 'text/html'})
        body = assert_error(resp, 500, 'Internal Server Error')
        assert len(calls) == 1 and isinstance(calls[0], ValueError)
        text = resp.get_data(as_text=True)
        assert 'secret detail' not in text
        assert 'ValueError' not in text
        assert 'Traceback' not in body['message']
        assert 'secret detail' in caplog.text  # logged, never shown

    def test_every_endpoint_of_the_blueprint_sits_under_the_prefix(self, app):
        rules = [r for r in app.url_map.iter_rules() if r.endpoint.startswith('api_v1.')]
        assert len(rules) == 7
        assert all(r.rule.startswith(f'{API}/') for r in rules)

    def test_landing_api_routes_do_not_collide(self, app, client):
        # landing partials live at /api/*, the API at /riftbound/api/v1/*
        landing = {r.rule for r in app.url_map.iter_rules() if r.endpoint.startswith('landing.')}
        assert '/api/noticias' in landing
        api = {r.rule for r in app.url_map.iter_rules() if r.endpoint.startswith('api_v1.')}
        assert api and not api & landing
        assert client.get(f'{API}/health').status_code == 200


# ---------------------------------------------------------------------------
# API-2 health, API-3 meta/config
# ---------------------------------------------------------------------------

class TestHealth:
    def test_healthy(self, app, client):
        resp = client.get(f'{API}/health')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert body['data'] == {'status': 'ok', 'db': 'ok', 'version': app.config['APP_VERSION']}
        assert body['data']['version']

    def test_needs_no_session(self, client):
        assert client.get(f'{API}/health').status_code == 200

    def test_db_down_is_a_503_envelope_without_details(self, client, monkeypatch):
        def broken(*args, **kwargs):
            raise OperationalError('SELECT 1', {}, Exception('postgresql://user:pw@dbhost/riftbound'))
        monkeypatch.setattr(db.session, 'execute', broken)
        resp = client.get(f'{API}/health')
        assert_error(resp, 503, 'Service Unavailable')
        text = resp.get_data(as_text=True)
        assert 'dbhost' not in text and 'postgresql' not in text

    def test_version_comes_from_rb_version(self):
        assert load_settings('testing', {'RB_VERSION': '1.2.3'})['APP_VERSION'] == '1.2.3'

    def test_version_defaults_to_dev(self):
        assert load_settings('testing', {})['APP_VERSION'] == 'dev'
        assert load_settings('testing', {'RB_VERSION': '  '})['APP_VERSION'] == 'dev'


class TestMetaConfig:
    def test_altcha_on(self, altcha_app, client):
        data = client.get(f'{API}/meta/config').get_json()['data']
        assert data['captcha'] == {'provider': 'altcha', 'required_for': ['register']}

    def test_captcha_off(self, client):
        resp = client.get(f'{API}/meta/config')
        data = resp.get_json()['data']
        assert data['captcha'] == {'provider': 'none', 'required_for': []}
        assert data['registration_open'] is True
        assert data['env'] == 'testing'
        assert data['csrf'] == {'header': 'X-CSRFToken'}

    def test_exposes_no_secret(self, altcha_app, client):
        text = client.get(f'{API}/meta/config').get_data(as_text=True)
        for needle in ('SECRET', 'DATABASE', 'HMAC', 'sqlite', altcha_app.config['SECRET_KEY']):
            assert needle not in text

    def test_is_public(self, client):
        assert client.get(f'{API}/meta/config').status_code == 200


# ---------------------------------------------------------------------------
# API-4 session
# ---------------------------------------------------------------------------

class TestSession:
    def test_anonymous(self, client):
        resp = client.get(f'{API}/auth/session')
        assert resp.status_code == 200
        data = resp.get_json()['data']
        assert data['authenticated'] is False
        assert isinstance(data['csrf_token'], str) and data['csrf_token']
        assert 'user' not in data

    def test_logged_in_user_has_exactly_the_public_fields(self, client, make_user):
        from tests.conftest import login_as
        user = make_user('alice', is_admin=True)
        login_as(client, 'alice')
        data = session_of(client)
        assert data['authenticated'] is True
        assert data['user'] == {'id': user.id, 'username': 'alice',
                                'email': 'alice@test.com', 'is_admin': True}
        assert set(data['user']) == USER_KEYS
        assert data['csrf_token']
        assert 'password' not in str(data) and 'hash' not in str(data)

    def test_a_plain_user_is_not_admin(self, authenticated_client):
        assert session_of(authenticated_client)['user']['is_admin'] is False

    def test_a_blocked_user_is_anonymous(self, app, authenticated_client):
        user = User.query.filter_by(username='testuser').one()
        user.is_blocked = True
        db.session.commit()
        data = session_of(authenticated_client)
        assert data['authenticated'] is False
        assert 'user' not in data

    def test_the_token_is_stable_inside_a_session(self, client):
        first = session_of(client)['csrf_token']
        assert session_of(client)['csrf_token'] == first

    def test_the_token_works_as_x_csrftoken(self, authenticated_client, csrf_app):
        # no token: CSRF 400; with the token from /auth/session: processed
        denied = authenticated_client.post(f'{API}/auth/logout')
        assert_error(denied, 400, 'CSRF Error')
        token = session_of(authenticated_client)['csrf_token']
        ok = authenticated_client.post(f'{API}/auth/logout', headers={'X-CSRFToken': token})
        assert ok.status_code == 200


# ---------------------------------------------------------------------------
# GET /auth/captcha
# ---------------------------------------------------------------------------

class TestCaptchaEndpoint:
    def test_provider_none_has_no_challenge(self, client):
        resp = client.get(f'{API}/auth/captcha')
        assert resp.status_code == 200
        assert resp.get_json()['data'] == {'provider': 'none', 'challenge': None}

    def test_altcha_returns_a_solvable_challenge(self, altcha_app, client):
        data = client.get(f'{API}/auth/captcha').get_json()['data']
        assert data['provider'] == 'altcha'
        assert set(data['challenge']) == {'algorithm', 'challenge', 'maxNumber', 'salt', 'signature'}
        assert data['challenge']['maxNumber'] == 1000
        assert solve(data['challenge'])          # the widget could solve it

    def test_every_call_issues_a_new_challenge(self, altcha_app, client):
        first = client.get(f'{API}/auth/captcha').get_json()['data']['challenge']
        second = client.get(f'{API}/auth/captcha').get_json()['data']['challenge']
        assert first['challenge'] != second['challenge']

    def test_no_secret_key_in_the_answer(self, altcha_app, client):
        text = client.get(f'{API}/auth/captcha').get_data(as_text=True)
        assert altcha_app.config['SECRET_KEY'] not in text


# ---------------------------------------------------------------------------
# API-5 login
# ---------------------------------------------------------------------------

class TestLogin:
    def test_success_creates_a_session(self, client, make_user):
        user = make_user('u', password=PASSWORD)
        resp = post_json(client, '/auth/login', {'username': 'u', 'password': PASSWORD})
        assert resp.status_code == 200
        assert resp.get_json() == {'success': True, 'data': {
            'user': {'id': user.id, 'username': 'u', 'email': 'u@test.com', 'is_admin': False}}}
        assert 'session=' in resp.headers['Set-Cookie']
        assert session_of(client)['authenticated'] is True
        assert client.get('/riftbound/').status_code == 200

    def test_the_admin_flag_is_reported(self, client, make_user):
        make_user('boss', password=PASSWORD, is_admin=True)
        resp = post_json(client, '/auth/login', {'username': 'boss', 'password': PASSWORD})
        assert resp.get_json()['data']['user']['is_admin'] is True

    @pytest.mark.parametrize('username,password', [('u', 'wrong-password'), ('ghost', PASSWORD)])
    def test_invalid_credentials_are_a_401(self, client, make_user, username, password):
        make_user('u', password=PASSWORD)
        resp = post_json(client, '/auth/login', {'username': username, 'password': password})
        body = assert_error(resp, 401, 'Unauthorized')
        assert body['message'] == 'Invalid credentials'
        assert session_of(client)['authenticated'] is False

    def test_a_blocked_user_looks_exactly_like_a_wrong_password(self, client, make_user):
        make_user('b', password=PASSWORD, is_blocked=True)
        make_user('u', password=PASSWORD)
        blocked = post_json(client, '/auth/login', {'username': 'b', 'password': PASSWORD})
        wrong = post_json(client, '/auth/login', {'username': 'u', 'password': 'nope-nope'})
        assert blocked.status_code == wrong.status_code == 401
        assert blocked.get_json() == wrong.get_json()
        assert session_of(client)['authenticated'] is False

    def test_five_wrong_passwords_then_the_lock(self, client, make_user, frozen_clock):
        make_user('u', password=PASSWORD)
        for _ in range(5):
            wrong = post_json(client, '/auth/login', {'username': 'u', 'password': 'nope-nope'})
            assert wrong.status_code == 401
        locked = post_json(client, '/auth/login', {'username': 'u', 'password': PASSWORD})
        body = assert_error(locked, 429, 'Too Many Requests')
        assert locked.headers['Retry-After'].isdigit()
        assert 1 <= int(locked.headers['Retry-After']) <= 900
        assert body['message'] == 'Invalid credentials or account temporarily locked'
        assert session_of(client)['authenticated'] is False

    def test_the_lock_ends_and_login_works_again(self, client, make_user, frozen_clock):
        make_user('u', password=PASSWORD)
        for _ in range(5):
            post_json(client, '/auth/login', {'username': 'u', 'password': 'nope-nope'})
        frozen_clock.advance(minutes=16)
        resp = post_json(client, '/auth/login', {'username': 'u', 'password': PASSWORD})
        assert resp.status_code == 200

    def test_the_lock_is_shared_with_the_form(self, client, make_user, frozen_clock):
        make_user('u', password=PASSWORD)
        for _ in range(5):
            client.post('/riftbound/login', data={'username': 'u', 'password': 'nope-nope'})
        locked = post_json(client, '/auth/login', {'username': 'u', 'password': PASSWORD})
        assert locked.status_code == 429

    def test_missing_fields_are_a_400_naming_the_field(self, client):
        resp = post_json(client, '/auth/login', {'username': 'u'})
        body = assert_error(resp, 400, 'Validation Error')
        assert [d['field'] for d in body['details']] == ['password']

    def test_empty_fields_are_a_400(self, client):
        resp = post_json(client, '/auth/login', {'username': '', 'password': ''})
        body = assert_error(resp, 400, 'Validation Error')
        assert {d['field'] for d in body['details']} == {'username', 'password'}

    def test_a_non_json_body_is_a_400(self, client):
        resp = client.post(f'{API}/auth/login', data={'username': 'u', 'password': 'p'})
        assert_error(resp, 400, 'Bad Request')

    def test_csrf_is_required_then_accepted(self, csrf_app, client, make_user):
        make_user('u', password=PASSWORD)
        body = {'username': 'u', 'password': PASSWORD}
        assert_error(post_json(client, '/auth/login', body), 400, 'CSRF Error')
        token = session_of(client)['csrf_token']
        resp = post_json(client, '/auth/login', body, **{'X-CSRFToken': token})
        assert resp.status_code == 200
        assert session_of(client)['authenticated'] is True

    def test_the_eleventh_login_in_a_minute_is_a_json_429(self, limited_app, client, monkeypatch):
        from werkzeug.security import generate_password_hash
        from app.services import auth
        cheap = generate_password_hash('dummy', method='pbkdf2:sha256:1000')
        monkeypatch.setattr(auth, '_dummy_hash', lambda: cheap)
        for i in range(10):
            resp = post_json(client, '/auth/login', {'username': f'ghost{i}', 'password': 'nope-nope'})
            assert resp.status_code == 401
        resp = post_json(client, '/auth/login', {'username': 'ghost', 'password': 'nope-nope'})
        assert_error(resp, 429, 'Too Many Requests')
        assert resp.headers['Retry-After'].isdigit()

    def test_form_and_api_logins_share_one_budget(self, limited_app, client, monkeypatch):
        from werkzeug.security import generate_password_hash
        from app.services import auth
        cheap = generate_password_hash('dummy', method='pbkdf2:sha256:1000')
        monkeypatch.setattr(auth, '_dummy_hash', lambda: cheap)
        for i in range(10):
            client.post('/riftbound/login', data={'username': f'ghost{i}', 'password': 'nope-nope'})
        resp = post_json(client, '/auth/login', {'username': 'ghost', 'password': 'nope-nope'})
        assert resp.status_code == 429


# ---------------------------------------------------------------------------
# API-6 logout
# ---------------------------------------------------------------------------

class TestLogout:
    def test_logout_ends_the_session(self, authenticated_client):
        resp = authenticated_client.post(f'{API}/auth/logout')
        assert resp.status_code == 200
        assert resp.get_json() == {'success': True, 'data': {}}
        assert session_of(authenticated_client)['authenticated'] is False
        assert authenticated_client.get('/riftbound/').status_code == 302

    def test_anonymous_logout_is_a_json_401_not_a_redirect(self, client):
        resp = client.post(f'{API}/auth/logout')
        assert_error(resp, 401, 'Unauthorized')
        assert 'Location' not in resp.headers

    def test_get_is_not_allowed(self, authenticated_client):
        assert_error(authenticated_client.get(f'{API}/auth/logout'), 405, 'Method Not Allowed')
        assert session_of(authenticated_client)['authenticated'] is True


# ---------------------------------------------------------------------------
# API-7 register
# ---------------------------------------------------------------------------

class TestRegister:
    def test_created_without_a_session(self, client):
        resp = post_json(client, '/auth/register', NEW_USER)
        assert resp.status_code == 201
        user = User.query.filter_by(username='newbie').one()
        assert resp.get_json() == {'success': True, 'data': {
            'user': {'id': user.id, 'username': 'newbie'}}}
        assert user.is_admin is False
        assert user.check_password('longenough1')
        assert session_of(client)['authenticated'] is False

    def test_the_new_user_can_log_in(self, client):
        post_json(client, '/auth/register', NEW_USER)
        resp = post_json(client, '/auth/login', {'username': 'newbie', 'password': 'longenough1'})
        assert resp.status_code == 200

    def test_is_admin_in_the_body_is_ignored(self, client):
        resp = post_json(client, '/auth/register', {**NEW_USER, 'is_admin': True})
        assert resp.status_code == 201
        assert User.query.filter_by(username='newbie').one().is_admin is False

    @pytest.mark.parametrize('field,value', [
        ('username', 'ab'), ('username', 'bad name!'), ('password', 'short7!'),
        ('email', 'not-an-email'),
    ])
    def test_invalid_fields_are_a_400_with_details(self, client, field, value):
        resp = post_json(client, '/auth/register', {**NEW_USER, field: value})
        body = assert_error(resp, 400, 'Validation Error')
        assert [d['field'] for d in body['details']] == [field]
        assert User.query.count() == 0

    def test_duplicate_username_is_a_409(self, client, make_user):
        make_user('dup')
        resp = post_json(client, '/auth/register', {**NEW_USER, 'username': 'dup'})
        body = assert_error(resp, 409, 'Conflict')
        assert 'Username' in body['message']
        assert User.query.count() == 1

    def test_duplicate_email_is_a_409_ignoring_case(self, client, make_user):
        make_user('other', email='Newbie@Test.com')
        resp = post_json(client, '/auth/register', NEW_USER)
        body = assert_error(resp, 409, 'Conflict')
        assert 'Email' in body['message']
        assert User.query.count() == 1

    def test_missing_captcha_is_a_captcha_error_and_no_row(self, altcha_app, client):
        resp = post_json(client, '/auth/register', NEW_USER)
        assert_error(resp, 400, 'Captcha Error')
        assert User.query.count() == 0

    def test_a_solved_captcha_creates_the_user_once(self, altcha_app, client):
        challenge = client.get(f'{API}/auth/captcha').get_json()['data']['challenge']
        payload = solve(challenge)
        resp = post_json(client, '/auth/register', {**NEW_USER, 'altcha': payload})
        assert resp.status_code == 201
        assert RbCaptchaUsed.query.count() == 1
        replay = post_json(client, '/auth/register',
                           {**NEW_USER, 'username': 'second', 'email': 'second@test.com',
                            'altcha': payload})
        assert_error(replay, 400, 'Captcha Error')
        assert User.query.filter_by(username='second').first() is None

    def test_a_bad_field_does_not_burn_the_payload(self, altcha_app, client):
        payload = solve(client.get(f'{API}/auth/captcha').get_json()['data']['challenge'])
        bad = post_json(client, '/auth/register', {**NEW_USER, 'username': 'ab', 'altcha': payload})
        assert_error(bad, 400, 'Validation Error')
        good = post_json(client, '/auth/register', {**NEW_USER, 'altcha': payload})
        assert good.status_code == 201

    def test_a_non_string_captcha_is_refused_not_a_500(self, altcha_app, client):
        resp = post_json(client, '/auth/register', {**NEW_USER, 'altcha': {'a': 1}})
        assert_error(resp, 400, 'Captcha Error')

    def test_csrf_is_required(self, csrf_app, client):
        assert_error(post_json(client, '/auth/register', NEW_USER), 400, 'CSRF Error')
        token = session_of(client)['csrf_token']
        resp = post_json(client, '/auth/register', NEW_USER, **{'X-CSRFToken': token})
        assert resp.status_code == 201

    def test_the_sixth_register_in_an_hour_is_a_json_429(self, limited_app, client):
        for _ in range(5):
            assert post_json(client, '/auth/register', {**NEW_USER, 'username': 'ab'}).status_code == 400
        resp = post_json(client, '/auth/register', {**NEW_USER, 'username': 'ab'})
        assert_error(resp, 429, 'Too Many Requests')
        assert resp.headers['Retry-After'].isdigit()
