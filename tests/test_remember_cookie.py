"""Remember cookie on API login (API-5, SESS-1; unit c of f1-app-shell).

HTTPS is simulated with `base_url='https://localhost'` on a production-config
app (same builder as `test_session_cookies`).
"""
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import pytest

import config
from app import create_app, db
from app.models import User
from tests.auth_helpers import Browser, api_login as login

KEY = 'remember-test-secret-key-' + 'k' * 24
PASSWORD = 'Passw0rd!x'
API = '/riftbound/api/v1'
DAYS_30 = 30 * 24 * 3600


def build_app(clean_env, env='production'):
    clean_env.setenv('RB_ENV', env)
    clean_env.setenv('SECRET_KEY', KEY)
    clean_env.setenv('DATABASE_URL', 'sqlite:///:memory:')
    clean_env.setenv('WTF_CSRF_ENABLED', 'false')       # cookies are the subject here
    clean_env.setenv('RATELIMIT_ENABLED', 'false')
    clean_env.setenv('CAPTCHA_PROVIDER', 'none')
    app = create_app()
    with app.app_context():
        db.create_all()
        user = User(username='remuser', email='rem@test.com')
        user.set_password(PASSWORD)
        db.session.add(user)
        db.session.commit()
    return app


def cookie_headers(resp, name):
    return [c for c in resp.headers.getlist('Set-Cookie') if c.startswith(f'{name}=')]


def lifetime(header):
    """Seconds until the cookie expires, from `Max-Age` or else `Expires`
    (Flask-Login sets `Expires`)."""
    found = re.search(r'Max-Age=(\d+)', header)
    if found:
        return int(found.group(1))
    found = re.search(r'Expires=([^;]+)', header)
    assert found, header
    return (parsedate_to_datetime(found.group(1)) - datetime.now(timezone.utc)).total_seconds()


def authenticated(browser):
    return browser.get(f'{API}/auth/session').get_json()['data']['authenticated']


@pytest.fixture
def prod(clean_env):
    return build_app(clean_env, 'production')


# --- 3.23 issuing the cookie ---------------------------------------------------

class TestIssuing:
    def test_remember_true_sets_a_secure_httponly_lax_30_day_cookie(self, prod):
        resp = login(Browser(prod), remember=True)
        assert resp.status_code == 200
        [header] = cookie_headers(resp, 'remember_token')
        assert 'HttpOnly' in header
        assert 'SameSite=Lax' in header
        assert 'Secure' in header
        assert abs(lifetime(header) - DAYS_30) <= 60
        assert 'Expires=' in header

    @pytest.mark.parametrize('extra', [{'remember': False}, {}], ids=['false', 'absent'])
    def test_remember_false_or_absent_sets_none(self, prod, extra):
        resp = login(Browser(prod), **extra)
        assert resp.status_code == 200
        assert cookie_headers(resp, 'remember_token') == []
        assert cookie_headers(resp, 'session') != []

    @pytest.mark.parametrize('bad', ['yes', 1, 'true', None, 0])
    def test_a_non_boolean_remember_is_a_400_naming_the_field_and_no_session(self, prod, bad):
        client = Browser(prod)
        resp = login(client, remember=bad)
        body = resp.get_json()
        assert resp.status_code == 400
        assert body['error'] == 'Validation Error'
        assert [d['field'] for d in body['details']] == ['remember']
        assert cookie_headers(resp, 'remember_token') == []
        assert cookie_headers(resp, 'session') == []
        assert authenticated(client) is False

    def test_development_cookie_has_no_secure_flag(self, clean_env):
        app = build_app(clean_env, 'development')
        resp = login(Browser(app, base_url='http://localhost'), remember=True)
        [header] = cookie_headers(resp, 'remember_token')
        assert 'HttpOnly' in header and 'SameSite=Lax' in header
        assert 'Secure' not in header
        assert abs(lifetime(header) - DAYS_30) <= 60

    def test_the_jinja_form_login_still_issues_no_remember_cookie(self, prod):
        client = Browser(prod)
        resp = client.post('/riftbound/login', data={'username': 'remuser', 'password': PASSWORD})
        assert resp.status_code == 302
        assert cookie_headers(resp, 'session') != []
        assert cookie_headers(resp, 'remember_token') == []

    @pytest.mark.parametrize('value', ['on', 'true', 'yes'])
    def test_a_stray_remember_field_in_the_form_does_not_break_the_login(self, prod, value):
        client = Browser(prod)
        resp = client.post('/riftbound/login', data={
            'username': 'remuser', 'password': PASSWORD, 'remember': value})
        assert resp.status_code == 302
        assert resp.headers['Location'].endswith('/riftbound/')
        assert cookie_headers(resp, 'remember_token') == []


class TestConfig:
    @pytest.mark.parametrize('env', ['production', 'development', 'testing'])
    def test_duration_is_30_days_in_every_environment(self, env):
        assert config.load_settings(env, {})['REMEMBER_COOKIE_DURATION'] == timedelta(days=30)

    def test_production_remember_flags_and_duration_on_the_app(self, prod):
        assert prod.config['REMEMBER_COOKIE_HTTPONLY'] is True
        assert prod.config['REMEMBER_COOKIE_SAMESITE'] == 'Lax'
        assert prod.config['REMEMBER_COOKIE_SECURE'] is True
        assert prod.config['REMEMBER_COOKIE_DURATION'] == timedelta(days=30)

    def test_the_expiry_is_absolute_not_sliding(self, prod):
        assert not prod.config.get('REMEMBER_COOKIE_REFRESH_EACH_REQUEST', False)


# --- 3.24 restoring a session from the cookie -----------------------------------

class TestRestoring:
    def test_a_client_with_only_the_remember_cookie_is_authenticated(self, prod):
        client = Browser(prod)
        login(client, remember=True)
        assert client.has_cookie('session') and client.has_cookie('remember_token')
        client.drop_cookie('session')
        assert not client.has_cookie('session')
        assert authenticated(client) is True

    def test_without_the_remember_cookie_dropping_the_session_logs_out(self, prod):
        client = Browser(prod)
        login(client)                                    # no remember
        client.drop_cookie('session')
        assert authenticated(client) is False

    def test_logout_expires_the_remember_cookie_and_the_next_session_is_anonymous(self, prod):
        client = Browser(prod)
        login(client, remember=True)
        resp = client.post(f'{API}/auth/logout')
        assert resp.status_code == 200
        [header] = cookie_headers(resp, 'remember_token')
        assert lifetime(header) <= 0
        assert authenticated(client) is False
        assert not client.has_cookie('remember_token')

    def test_a_user_blocked_after_login_is_anonymous_with_a_valid_remember_cookie(self, prod):
        client = Browser(prod)
        login(client, remember=True)
        with prod.app_context():
            user = User.query.filter_by(username='remuser').one()
            user.is_blocked = True
            db.session.commit()
        client.drop_cookie('session')
        assert client.has_cookie('remember_token')
        assert authenticated(client) is False

    def test_a_blocked_user_with_both_cookies_is_anonymous(self, prod):
        client = Browser(prod)
        login(client, remember=True)
        with prod.app_context():
            user = User.query.filter_by(username='remuser').one()
            user.is_blocked = True
            db.session.commit()
        assert authenticated(client) is False
