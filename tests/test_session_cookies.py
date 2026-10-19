"""Session / remember cookie flags and the unit-d kill switches (SESS-1, CSRF-5).

`load_settings` is a pure function of (env, environ), so most of this is
table-driven. The two scenarios that need a real login build an app with
`RB_ENV` set through the environment (the way a deployment does) and an SQLite
URL, so no test override can hide a wrong default.
"""
import logging
import re

import pytest

import config
from app import create_app, db
from app.models import User

KEY = 'cookie-test-secret-key-' + 'k' * 24
PASSWORD = 'cookiepass123'


def settings(env, **environ):
    return config.load_settings(env, environ)


# --- pure settings ---------------------------------------------------------------

class TestCookieSettings:
    @pytest.mark.parametrize('env, secure', [
        ('production', True), ('development', False), ('testing', False)])
    def test_session_and_remember_cookie_flags(self, env, secure):
        cfg = settings(env)
        for prefix in ('SESSION', 'REMEMBER'):
            assert cfg[f'{prefix}_COOKIE_HTTPONLY'] is True, prefix
            assert cfg[f'{prefix}_COOKIE_SAMESITE'] == 'Lax', prefix
            assert cfg[f'{prefix}_COOKIE_SECURE'] is secure, (prefix, env)

    @pytest.mark.parametrize('env, value, expected', [
        ('production', 'false', False), ('production', '0', False),
        ('development', 'true', True), ('development', '1', True),
        ('testing', 'yes', True), ('production', 'OFF', False),
    ])
    def test_secure_flag_can_be_overridden_by_env(self, env, value, expected):
        cfg = settings(env, SESSION_COOKIE_SECURE=value, REMEMBER_COOKIE_SECURE=value)
        assert cfg['SESSION_COOKIE_SECURE'] is expected
        assert cfg['REMEMBER_COOKIE_SECURE'] is expected

    def test_session_and_remember_overrides_are_independent(self):
        cfg = settings('production', REMEMBER_COOKIE_SECURE='false')
        assert (cfg['SESSION_COOKIE_SECURE'], cfg['REMEMBER_COOKIE_SECURE']) == (True, False)

    def test_samesite_is_never_strict(self):
        # Future OAuth callbacks are cross-site top-level GETs.
        assert all(settings(env)['SESSION_COOKIE_SAMESITE'] != 'Strict'
                   for env in config.ENVIRONMENTS)

    def test_a_non_boolean_value_is_refused_naming_the_variable_only(self):
        with pytest.raises(config.ConfigError) as exc:
            settings('production', SESSION_COOKIE_SECURE='maybe-so')
        assert 'SESSION_COOKIE_SECURE' in str(exc.value)
        assert 'maybe-so' not in str(exc.value)


class TestUnitDDefaults:
    @pytest.mark.parametrize('env', ['production', 'development'])
    def test_protections_are_on_outside_testing(self, env):
        cfg = settings(env)
        assert cfg['WTF_CSRF_ENABLED'] is True
        assert cfg['RATELIMIT_ENABLED'] is True
        assert cfg['CAPTCHA_PROVIDER'] == 'altcha'

    def test_testing_has_csrf_limiter_off_and_captcha_none(self):
        cfg = settings('testing')
        assert cfg['WTF_CSRF_ENABLED'] is False
        assert cfg['RATELIMIT_ENABLED'] is False
        assert cfg['CAPTCHA_PROVIDER'] == 'none'

    def test_csrf_token_never_expires(self):
        assert all(settings(env)['WTF_CSRF_TIME_LIMIT'] is None for env in config.ENVIRONMENTS)

    def test_numeric_and_storage_defaults(self):
        cfg = settings('production')
        assert cfg['LOGIN_MAX_FAILURES'] == 5
        assert cfg['LOGIN_LOCK_BASE_MINUTES'] == 15
        assert cfg['LOGIN_LOCK_MAX_MINUTES'] == 1440
        assert cfg['ALTCHA_EXPIRE_SECONDS'] == 300          # R11
        assert cfg['ALTCHA_MAX_NUMBER'] == 1_000_000
        assert cfg['ALTCHA_HMAC_KEY'] is None
        assert cfg['LANDING_CACHE_TTL'] == 300              # R12
        assert cfg['RATELIMIT_STORAGE_URI'] == 'memory://'

    def test_env_overrides(self):
        cfg = settings('production', RATELIMIT_STORAGE_URI='redis://localhost:6379',
                       LANDING_CACHE_TTL='60', ALTCHA_HMAC_KEY='explicit-hmac-key',
                       CAPTCHA_PROVIDER='none', WTF_CSRF_ENABLED='false',
                       RATELIMIT_ENABLED='false')
        assert cfg['RATELIMIT_STORAGE_URI'] == 'redis://localhost:6379'
        assert cfg['LANDING_CACHE_TTL'] == 60
        assert cfg['ALTCHA_HMAC_KEY'] == 'explicit-hmac-key'
        assert cfg['CAPTCHA_PROVIDER'] == 'none'
        assert cfg['WTF_CSRF_ENABLED'] is False
        assert cfg['RATELIMIT_ENABLED'] is False

    def test_unknown_captcha_provider_is_refused(self):
        with pytest.raises(config.ConfigError) as exc:
            settings('production', CAPTCHA_PROVIDER='recaptcha')
        assert 'CAPTCHA_PROVIDER' in str(exc.value)
        assert 'none' in str(exc.value) and 'altcha' in str(exc.value)

    def test_landing_ttl_of_zero_is_allowed(self):
        assert settings('production', LANDING_CACHE_TTL='0')['LANDING_CACHE_TTL'] == 0


class TestKillSwitchWarnings:
    @pytest.mark.parametrize('name', ['WTF_CSRF_ENABLED', 'RATELIMIT_ENABLED'])
    def test_turning_a_protection_off_outside_testing_is_logged(self, caplog, name):
        with caplog.at_level(logging.WARNING, logger='config'):
            settings('production', **{name: 'false'})
        assert any(name in r.getMessage() for r in caplog.records)

    def test_captcha_none_outside_testing_is_logged(self, caplog):
        with caplog.at_level(logging.WARNING, logger='config'):
            settings('development', CAPTCHA_PROVIDER='none')
        assert any('CAPTCHA_PROVIDER' in r.getMessage() for r in caplog.records)

    def test_defaults_log_nothing(self, caplog):
        with caplog.at_level(logging.WARNING, logger='config'):
            settings('production')
            settings('testing')
        assert not [r for r in caplog.records if 'CSRF' in r.getMessage()
                    or 'RATELIMIT' in r.getMessage() or 'CAPTCHA' in r.getMessage()]


# --- real apps ---------------------------------------------------------------------

def build_app(clean_env, env, **extra):
    """An app configured only through the environment, as a deployment is."""
    clean_env.setenv('RB_ENV', env)
    clean_env.setenv('SECRET_KEY', KEY)
    clean_env.setenv('DATABASE_URL', 'sqlite:///:memory:')
    for name, value in extra.items():
        clean_env.setenv(name, value)
    app = create_app()
    with app.app_context():
        db.create_all()
        user = User(username='cookieuser', email='cookie@test.com')
        user.set_password(PASSWORD)
        db.session.add(user)
        db.session.commit()
    return app


def login(client, https):
    """Log in through the real form: token from the page, Referer on HTTPS."""
    headers = {'Referer': 'https://localhost/riftbound/login'} if https else {}
    page = client.get('/riftbound/login', headers=headers)
    token = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', page.get_data(as_text=True))
    data = {'username': 'cookieuser', 'password': PASSWORD}
    if token:
        data['csrf_token'] = token.group(1)
    return client.post('/riftbound/login', data=data, headers=headers)


def session_cookie_header(resp):
    cookies = [c for c in resp.headers.getlist('Set-Cookie') if c.startswith('session=')]
    assert len(cookies) == 1, resp.headers.getlist('Set-Cookie')
    return cookies[0]


class TestLoginCookie:
    def test_production_cookie_is_httponly_lax_and_secure(self, clean_env):
        app = build_app(clean_env, 'production')
        client = app.test_client()
        resp = login(client, https=True)
        assert resp.status_code == 302, resp.get_data(as_text=True)
        header = session_cookie_header(resp)
        assert 'HttpOnly' in header
        assert 'SameSite=Lax' in header
        assert 'Secure' in header

    @pytest.mark.parametrize('env', ['development', 'testing'])
    def test_development_and_testing_cookie_has_no_secure_flag(self, clean_env, env):
        app = build_app(clean_env, env)
        resp = login(app.test_client(), https=False)
        assert resp.status_code == 302, resp.get_data(as_text=True)
        header = session_cookie_header(resp)
        assert 'HttpOnly' in header
        assert 'SameSite=Lax' in header
        assert 'Secure' not in header

    def test_production_remember_cookie_config(self, clean_env):
        app = build_app(clean_env, 'production')
        assert app.config['REMEMBER_COOKIE_HTTPONLY'] is True
        assert app.config['REMEMBER_COOKIE_SAMESITE'] == 'Lax'
        assert app.config['REMEMBER_COOKIE_SECURE'] is True

    def test_secure_flag_override_reaches_the_cookie(self, clean_env):
        app = build_app(clean_env, 'development', SESSION_COOKIE_SECURE='true')
        resp = login(app.test_client(), https=True)
        assert 'Secure' in session_cookie_header(resp)


class TestKillSwitchesOnTheApp:
    def test_csrf_is_enabled_by_default_in_production(self, clean_env):
        assert build_app(clean_env, 'production').config['WTF_CSRF_ENABLED'] is True

    def test_csrf_switch_off_by_env(self, clean_env):
        app = build_app(clean_env, 'production', WTF_CSRF_ENABLED='false')
        assert app.config['WTF_CSRF_ENABLED'] is False

    def test_default_testing_app_has_the_protections_off(self, app):
        assert app.config['WTF_CSRF_ENABLED'] is False
        assert app.config['RATELIMIT_ENABLED'] is False
        assert app.config['CAPTCHA_PROVIDER'] == 'none'
