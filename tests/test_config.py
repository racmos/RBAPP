"""
Tests for configuration and secrets handling (unit a, specs CFG-1..7).

Layout:
  - TestTestEnvContract ....... conftest pins RB_ENV=testing (D1)
  - TestResolveEnv ............ CFG-2   (pure)
  - TestLoadSettings .......... CFG-1, CFG-7, D2 ephemeral key (pure)
  - TestValidateSettings ...... CFG-3   (pure, never echoes values)
  - TestEngineOptions ......... CFG-5   (pure)
  - TestCreateApp ............. CFG-1..3 through the app factory
  - TestDotenvGating .......... CFG-4, R15 (temp `.env` via the DOTENV_PATH hook)
  - TestEngineAndProxyViaApp .. CFG-5, CFG-7 through the app factory
  - TestNoCredentialsInTree ... CFG-1, CFG-6 file scans

The `clean_env` fixture (tests/conftest.py) unsets every config variable and
isolates the `.env` hook.

Tests never print or assert on real credentials: every key and URL is a
throw-away value generated here.
"""
import hashlib
import logging
import os
import secrets
from pathlib import Path

import pytest
from dotenv import dotenv_values

import app as app_module
import config
from app import create_app

ROOT = Path(__file__).resolve().parent.parent

GOOD_KEY = secrets.token_urlsafe(48)                       # 64 chars
GOOD_DB_URL = 'postgresql+psycopg://svc_user:Pa55w0rd-zz@db.example.test:5432/riftbound'
SQLITE_URL = 'sqlite:///:memory:'


def _prod_env(monkeypatch, **extra):
    """Valid production environment, with optional overrides ('' or None unsets)."""
    values = {'RB_ENV': 'production', 'SECRET_KEY': GOOD_KEY, 'DATABASE_URL': GOOD_DB_URL}
    values.update(extra)
    for name, value in values.items():
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)


# ---------------------------------------------------------------------------
# conftest contract (task 1.2)
# ---------------------------------------------------------------------------

class TestTestEnvContract:
    """tests/conftest.py must pin RB_ENV=testing before importing the app (D1)."""

    def test_conftest_sets_rb_env_testing(self):
        assert os.environ.get('RB_ENV') == 'testing'


# ---------------------------------------------------------------------------
# CFG-2 resolve_env
# ---------------------------------------------------------------------------

class TestResolveEnv:
    def test_unset_means_production(self):
        assert config.resolve_env({}) == 'production'

    @pytest.mark.parametrize('raw', ['', '   '])
    def test_blank_means_production(self, raw):
        assert config.resolve_env({'RB_ENV': raw}) == 'production'

    @pytest.mark.parametrize('name', ['development', 'testing', 'production'])
    def test_known_values(self, name):
        assert config.resolve_env({'RB_ENV': name}) == name

    def test_value_is_normalized(self):
        assert config.resolve_env({'RB_ENV': ' Development '}) == 'development'

    def test_environments_constant(self):
        assert config.ENVIRONMENTS == ('development', 'testing', 'production')

    def test_unknown_value_raises_naming_allowed_values(self):
        with pytest.raises(config.ConfigError) as exc:
            config.resolve_env({'RB_ENV': 'staging'})
        assert isinstance(exc.value, RuntimeError)
        assert 'development, testing, production' in str(exc.value)

    def test_unknown_value_other_spelling(self):
        with pytest.raises(RuntimeError, match='development, testing, production'):
            config.resolve_env({'RB_ENV': 'prod'})


# ---------------------------------------------------------------------------
# CFG-1 / CFG-7 load_settings
# ---------------------------------------------------------------------------

class TestLoadSettings:
    def test_reads_secret_and_database_url_from_environ(self):
        settings = config.load_settings(
            'production', {'SECRET_KEY': GOOD_KEY, 'DATABASE_URL': GOOD_DB_URL})
        assert settings['SECRET_KEY'] == GOOD_KEY
        assert settings['SQLALCHEMY_DATABASE_URI'] == GOOD_DB_URL

    def test_reads_other_values(self):
        other_key = secrets.token_urlsafe(40)
        settings = config.load_settings(
            'testing', {'SECRET_KEY': other_key, 'DATABASE_URL': SQLITE_URL})
        assert settings['SECRET_KEY'] == other_key
        assert settings['SQLALCHEMY_DATABASE_URI'] == SQLITE_URL

    def test_records_the_environment_and_keeps_tracking_off(self):
        settings = config.load_settings('production', {})
        assert settings['RB_ENV'] == 'production'
        assert settings['SQLALCHEMY_TRACK_MODIFICATIONS'] is False

    def test_missing_values_stay_missing_outside_development(self):
        settings = config.load_settings('production', {})
        assert settings['SECRET_KEY'] is None
        assert settings['SQLALCHEMY_DATABASE_URI'] is None

    def test_blank_values_count_as_missing(self):
        settings = config.load_settings('production', {'SECRET_KEY': '', 'DATABASE_URL': ''})
        assert settings['SECRET_KEY'] is None
        assert settings['SQLALCHEMY_DATABASE_URI'] is None

    # D2: development gets an ephemeral key when none is configured
    def test_development_without_key_gets_a_random_one(self):
        first = config.load_settings('development', {'DATABASE_URL': SQLITE_URL})['SECRET_KEY']
        second = config.load_settings('development', {'DATABASE_URL': SQLITE_URL})['SECRET_KEY']
        assert len(first) >= 32 and len(second) >= 32
        assert first != second

    def test_development_ephemeral_key_logs_a_warning_without_the_key(self, caplog):
        with caplog.at_level(logging.WARNING):
            key = config.load_settings('development', {})['SECRET_KEY']
        assert 'SECRET_KEY' in caplog.text
        assert key not in caplog.text

    def test_development_keeps_a_configured_key(self):
        settings = config.load_settings('development', {'SECRET_KEY': GOOD_KEY})
        assert settings['SECRET_KEY'] == GOOD_KEY

    # CFG-7
    def test_proxy_fix_defaults_trust_one_hop(self):
        settings = config.load_settings('production', {})
        assert settings['PROXY_FIX_X_FOR'] == 1
        assert settings['PROXY_FIX_X_PROTO'] == 1
        assert settings['PROXY_FIX_X_HOST'] == 1

    def test_proxy_fix_values_come_from_environ(self):
        settings = config.load_settings(
            'production',
            {'PROXY_FIX_X_FOR': '0', 'PROXY_FIX_X_PROTO': '2', 'PROXY_FIX_X_HOST': '3'})
        assert (settings['PROXY_FIX_X_FOR'], settings['PROXY_FIX_X_PROTO'],
                settings['PROXY_FIX_X_HOST']) == (0, 2, 3)

    @pytest.mark.parametrize('bad', ['abc', '-1', '1.5'])
    def test_proxy_fix_rejects_non_integers_naming_the_variable(self, bad):
        with pytest.raises(config.ConfigError, match='PROXY_FIX_X_FOR'):
            config.load_settings('production', {'PROXY_FIX_X_FOR': bad})


# ---------------------------------------------------------------------------
# CFG-3 validate_settings
# ---------------------------------------------------------------------------

def _cfg(**overrides):
    cfg = {'SECRET_KEY': GOOD_KEY, 'SQLALCHEMY_DATABASE_URI': GOOD_DB_URL, 'DEBUG': False}
    cfg.update(overrides)
    return cfg


class TestValidateSettings:
    def test_valid_production_config_passes(self):
        assert config.validate_settings(_cfg(), 'production') is None

    def test_missing_secret_key(self):
        with pytest.raises(config.ConfigError, match='SECRET_KEY'):
            config.validate_settings(_cfg(SECRET_KEY=None), 'production')

    def test_missing_database_url(self):
        with pytest.raises(config.ConfigError, match='DATABASE_URL'):
            config.validate_settings(_cfg(SQLALCHEMY_DATABASE_URI=None), 'production')

    def test_all_problems_are_reported_together(self):
        with pytest.raises(config.ConfigError) as exc:
            config.validate_settings(
                _cfg(SECRET_KEY=None, SQLALCHEMY_DATABASE_URI=None), 'production')
        assert 'SECRET_KEY' in str(exc.value)
        assert 'DATABASE_URL' in str(exc.value)

    @pytest.mark.parametrize('weak', [
        'you-will-never-guess',                          # legacy default
        'change-me-please-change-me-please-xx',          # CFG-3 scenario
        'CHANGE-ME-please-change-me-please-XX',          # case-insensitive
        'x' * 20 + 'ChangeMe' + 'x' * 20,                # changeme, mixed case
        'x' * 20 + 'changeme' + 'x' * 20,
        'k' * 31,                                        # one char short
    ])
    def test_weak_secret_keys_are_rejected_without_echoing_them(self, weak):
        with pytest.raises(config.ConfigError) as exc:
            config.validate_settings(_cfg(SECRET_KEY=weak), 'production')
        assert 'SECRET_KEY' in str(exc.value)
        assert weak not in str(exc.value)

    def test_32_characters_is_enough(self):
        assert config.validate_settings(_cfg(SECRET_KEY='k' * 32), 'production') is None

    # The old .env.example placeholder is exactly 32 chars and holds neither
    # 'change-me' nor 'changeme': only the denylist can reject it.
    def test_denylist_rejects_the_old_example_placeholder(self):
        placeholder = 'your-secret-key-here-change-this'
        assert len(placeholder) == 32
        with pytest.raises(config.ConfigError, match='SECRET_KEY'):
            config.validate_settings(_cfg(SECRET_KEY=placeholder), 'production')

    def test_denylist_is_stored_as_digests_not_literals(self):
        # R13: the legacy default may not live in config.py, only its digest.
        legacy = 'you-will-never-guess'
        assert hashlib.sha256(legacy.encode()).hexdigest() in config.SECRET_KEY_DENYLIST_SHA256
        assert legacy not in (ROOT / 'config.py').read_text()

    def test_error_never_echoes_the_database_url(self):
        with pytest.raises(config.ConfigError) as exc:
            config.validate_settings(_cfg(SECRET_KEY=None), 'production')
        assert GOOD_DB_URL not in str(exc.value)
        assert 'Pa55w0rd-zz' not in str(exc.value)

    # Development: DATABASE_URL still required, SECRET_KEY may be omitted
    def test_development_may_omit_secret_key(self):
        assert config.validate_settings(_cfg(SECRET_KEY=None), 'development') is None

    def test_development_requires_database_url(self):
        with pytest.raises(config.ConfigError, match='DATABASE_URL'):
            config.validate_settings(_cfg(SQLALCHEMY_DATABASE_URI=None), 'development')

    def test_testing_flag_skips_every_check(self):
        cfg = {'TESTING': True, 'SECRET_KEY': None, 'SQLALCHEMY_DATABASE_URI': None}
        assert config.validate_settings(cfg, 'production') is None

    def test_testing_env_without_testing_flag_is_still_validated(self):
        with pytest.raises(config.ConfigError, match='SECRET_KEY'):
            config.validate_settings(_cfg(SECRET_KEY=None), 'testing')

    # D2: production needs DEBUG off
    def test_production_rejects_debug(self):
        with pytest.raises(config.ConfigError, match='DEBUG'):
            config.validate_settings(_cfg(DEBUG=True), 'production')

    def test_development_allows_debug(self):
        assert config.validate_settings(_cfg(DEBUG=True), 'development') is None


# ---------------------------------------------------------------------------
# CFG-5 engine_options
# ---------------------------------------------------------------------------

class TestEngineOptions:
    @pytest.mark.parametrize('uri', ['sqlite:///:memory:', 'sqlite:////tmp/x.db'])
    def test_sqlite_has_only_pre_ping(self, uri):
        assert config.engine_options(uri) == {'pool_pre_ping': True}

    @pytest.mark.parametrize('uri', [
        GOOD_DB_URL, 'postgresql+psycopg://u:p@h/db', 'postgresql://u:p@h/db'])
    def test_postgresql_sets_client_encoding(self, uri):
        options = config.engine_options(uri)
        assert options == {'connect_args': {'client_encoding': 'utf8'}, 'pool_pre_ping': True}


# ---------------------------------------------------------------------------
# CFG-1..3 through create_app
# ---------------------------------------------------------------------------

class TestCreateApp:
    def test_values_come_from_the_environment(self, clean_env):
        _prod_env(clean_env)
        app = create_app()
        assert app.config['SECRET_KEY'] == GOOD_KEY
        assert app.config['SQLALCHEMY_DATABASE_URI'] == GOOD_DB_URL
        assert app.config['RB_ENV'] == 'production'

    def test_unset_rb_env_is_production(self, clean_env):
        clean_env.setenv('SECRET_KEY', GOOD_KEY)
        clean_env.setenv('DATABASE_URL', GOOD_DB_URL)
        assert create_app().config['RB_ENV'] == 'production'

    def test_production_without_secret_key_raises(self, clean_env):
        _prod_env(clean_env, SECRET_KEY=None)
        with pytest.raises(RuntimeError) as exc:
            create_app()
        assert 'SECRET_KEY' in str(exc.value)
        assert 'DATABASE_URL' not in str(exc.value)   # only the offender is named

    @pytest.mark.parametrize('weak', [
        'you-will-never-guess',
        'change-me-please-change-me-please-xx',
        'k' * 31,
    ])
    def test_weak_secret_keys_raise_without_echoing_the_value(self, clean_env, weak):
        _prod_env(clean_env, SECRET_KEY=weak)
        with pytest.raises(RuntimeError) as exc:
            create_app()
        assert 'SECRET_KEY' in str(exc.value)
        assert weak not in str(exc.value)

    def test_production_without_database_url_raises(self, clean_env):
        _prod_env(clean_env, DATABASE_URL=None)
        with pytest.raises(RuntimeError) as exc:
            create_app()
        assert 'DATABASE_URL' in str(exc.value)
        assert 'SECRET_KEY' not in str(exc.value)

    def test_unknown_rb_env_raises_listing_allowed_values(self, clean_env):
        _prod_env(clean_env, RB_ENV='staging')
        with pytest.raises(RuntimeError, match='development, testing, production'):
            create_app()

    def test_test_contract_is_unchanged(self, clean_env):
        # No RB_ENV, SECRET_KEY or DATABASE_URL anywhere in the environment.
        app = create_app(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI=SQLITE_URL,
            SECRET_KEY='test-secret-key',
        )
        assert app.config['TESTING'] is True
        assert app.config['SECRET_KEY'] == 'test-secret-key'
        assert app.config['SQLALCHEMY_DATABASE_URI'] == SQLITE_URL

    def test_validation_runs_after_overrides_so_they_can_fix_the_config(self, clean_env):
        clean_env.setenv('RB_ENV', 'production')       # nothing else in the env
        app = create_app(SECRET_KEY=GOOD_KEY, SQLALCHEMY_DATABASE_URI=SQLITE_URL)
        assert app.config['SECRET_KEY'] == GOOD_KEY

    def test_validation_runs_after_overrides_so_they_can_break_the_config(self, clean_env):
        _prod_env(clean_env)                            # env is valid...
        with pytest.raises(RuntimeError, match='SECRET_KEY'):
            create_app(SECRET_KEY='short')              # ...the override is not

    def test_production_rejects_flask_debug(self, clean_env):
        _prod_env(clean_env, FLASK_DEBUG='1')
        with pytest.raises(RuntimeError, match='DEBUG'):
            create_app()

    def test_development_without_secret_key_starts_with_an_ephemeral_key(self, clean_env):
        clean_env.setenv('RB_ENV', 'development')
        clean_env.setenv('DATABASE_URL', SQLITE_URL)
        app = create_app()
        assert len(app.config['SECRET_KEY']) >= 32

    def test_development_without_database_url_raises(self, clean_env):
        clean_env.setenv('RB_ENV', 'development')
        with pytest.raises(RuntimeError, match='DATABASE_URL'):
            create_app()

    def test_create_app_no_longer_takes_a_config_class(self):
        import inspect
        assert 'config_class' not in inspect.signature(create_app).parameters


# ---------------------------------------------------------------------------
# CFG-4 dotenv gating (R15)
# ---------------------------------------------------------------------------

@pytest.fixture
def dotenv_file(clean_env, tmp_path):
    """Returns a writer for the temp `.env` that the app's path hook points to."""
    path = tmp_path / '.env'
    clean_env.setattr(app_module, 'DOTENV_PATH', str(path))

    def write(**values):
        path.write_text(''.join(f'{k}={v}\n' for k, v in values.items()))
        return path
    return write


class TestDotenvGating:
    def test_development_loads_database_url_from_the_file(self, clean_env, dotenv_file):
        dotenv_file(DATABASE_URL=SQLITE_URL)
        clean_env.setenv('RB_ENV', 'development')
        assert create_app().config['SQLALCHEMY_DATABASE_URI'] == SQLITE_URL

    def test_development_loads_secret_key_from_the_file(self, clean_env, dotenv_file):
        dotenv_file(DATABASE_URL=SQLITE_URL, SECRET_KEY=GOOD_KEY)
        clean_env.setenv('RB_ENV', 'development')
        assert create_app().config['SECRET_KEY'] == GOOD_KEY

    def test_real_environment_wins_over_the_file(self, clean_env, dotenv_file):
        dotenv_file(DATABASE_URL='sqlite:////tmp/from-file.db')
        clean_env.setenv('RB_ENV', 'development')
        clean_env.setenv('DATABASE_URL', SQLITE_URL)     # override=False
        assert create_app().config['SQLALCHEMY_DATABASE_URI'] == SQLITE_URL

    def test_production_never_reads_the_file(self, clean_env, dotenv_file):
        dotenv_file(SECRET_KEY=GOOD_KEY, DATABASE_URL=GOOD_DB_URL)
        clean_env.setenv('RB_ENV', 'production')
        with pytest.raises(RuntimeError, match='SECRET_KEY'):
            create_app()
        assert 'SECRET_KEY' not in os.environ
        assert 'DATABASE_URL' not in os.environ

    def test_testing_never_reads_the_file(self, clean_env, dotenv_file):
        dotenv_file(DATABASE_URL=GOOD_DB_URL)
        clean_env.setenv('RB_ENV', 'testing')
        app = create_app(TESTING=True, SQLALCHEMY_DATABASE_URI=SQLITE_URL, SECRET_KEY='test-secret-key')
        assert app.config['SQLALCHEMY_DATABASE_URI'] == SQLITE_URL
        assert 'DATABASE_URL' not in os.environ

    def test_unset_rb_env_lets_the_file_declare_development(self, clean_env, dotenv_file):
        dotenv_file(RB_ENV='development', DATABASE_URL=SQLITE_URL)
        app = create_app()                               # RB_ENV is unset in the process
        assert app.config['RB_ENV'] == 'development'
        assert app.config['SQLALCHEMY_DATABASE_URI'] == SQLITE_URL

    def test_unset_rb_env_and_file_without_development_stays_production(self, clean_env, dotenv_file):
        dotenv_file(SECRET_KEY=GOOD_KEY, DATABASE_URL=GOOD_DB_URL)   # no RB_ENV line
        with pytest.raises(RuntimeError, match='SECRET_KEY'):
            create_app()
        assert 'SECRET_KEY' not in os.environ            # the file was not applied

    def test_default_path_is_the_repo_root_env_file(self):
        assert Path(app_module.DOTENV_PATH) == ROOT / '.env'

    def test_missing_file_is_fine(self, clean_env):
        clean_env.setenv('RB_ENV', 'development')
        clean_env.setenv('DATABASE_URL', SQLITE_URL)
        assert create_app().config['RB_ENV'] == 'development'


# ---------------------------------------------------------------------------
# CFG-5 / CFG-7 through create_app
# ---------------------------------------------------------------------------

def _app_with_probe(**overrides):
    app = create_app(
        TESTING=True, SECRET_KEY='test-secret-key',
        SQLALCHEMY_DATABASE_URI=SQLITE_URL, **overrides)

    @app.route('/__probe/remote_addr')
    def _probe_remote_addr():
        from flask import request
        return request.remote_addr or ''
    return app


class TestEngineAndProxyViaApp:
    def test_sqlite_override_gets_pre_ping_and_no_connect_args(self, clean_env):
        app = create_app(TESTING=True, SECRET_KEY='k', SQLALCHEMY_DATABASE_URI=SQLITE_URL)
        assert app.config['SQLALCHEMY_ENGINE_OPTIONS'] == {'pool_pre_ping': True}
        assert 'connect_args' not in app.config['SQLALCHEMY_ENGINE_OPTIONS']

    def test_postgresql_uri_gets_client_encoding(self, clean_env):
        _prod_env(clean_env)
        app = create_app()
        options = app.config['SQLALCHEMY_ENGINE_OPTIONS']
        assert options['connect_args'] == {'client_encoding': 'utf8'}
        assert options['pool_pre_ping'] is True

    def test_options_follow_the_final_uri_not_the_env_uri(self, clean_env):
        # Env says PostgreSQL, the override switches to SQLite: options must follow.
        _prod_env(clean_env)
        app = create_app(SQLALCHEMY_DATABASE_URI=SQLITE_URL)
        assert app.config['SQLALCHEMY_ENGINE_OPTIONS'] == {'pool_pre_ping': True}

    def test_default_trusts_one_forwarded_hop(self, clean_env):
        app = _app_with_probe()
        resp = app.test_client().get(
            '/__probe/remote_addr', headers={'X-Forwarded-For': '203.0.113.9'})
        assert resp.get_data(as_text=True) == '203.0.113.9'

    def test_zero_hops_ignores_the_header(self, clean_env):
        clean_env.setenv('PROXY_FIX_X_FOR', '0')
        app = _app_with_probe()
        resp = app.test_client().get(
            '/__probe/remote_addr', headers={'X-Forwarded-For': '203.0.113.9'})
        assert resp.get_data(as_text=True) == '127.0.0.1'      # test client socket address

    def test_two_hops_reads_one_entry_further_left(self, clean_env):
        clean_env.setenv('PROXY_FIX_X_FOR', '2')
        app = _app_with_probe()
        resp = app.test_client().get(
            '/__probe/remote_addr',
            headers={'X-Forwarded-For': '198.51.100.1, 203.0.113.9'})
        assert resp.get_data(as_text=True) == '198.51.100.1'


# ---------------------------------------------------------------------------
# CFG-1 / CFG-6 file scans
# ---------------------------------------------------------------------------

# Built from pieces so this file is not itself a hit for `git grep`.
LEGACY_LITERALS = ('you-will-never' + '-guess', 'abcd' + '1234', '192.168.1' + '.33')


def _scanned_files():
    files = [ROOT / 'config.py', ROOT / 'run.py', ROOT / 'wsgi.py', ROOT / '.env.example']
    files += sorted((ROOT / 'app').rglob('*.py'))
    return files


class TestNoCredentialsInTree:
    def test_scan_covers_the_expected_files(self):
        files = _scanned_files()
        names = {f.relative_to(ROOT).as_posix() for f in files}
        assert {'config.py', 'run.py', 'wsgi.py', '.env.example', 'app/__init__.py'} <= names
        assert all(f.is_file() for f in files)

    @pytest.mark.parametrize('literal', LEGACY_LITERALS)
    def test_legacy_literals_are_gone(self, literal):
        hits = [f.relative_to(ROOT).as_posix() for f in _scanned_files()
                if literal in f.read_text(errors='replace')]
        assert hits == []

    def test_env_example_declares_the_core_variables(self):
        values = dotenv_values(ROOT / '.env.example')
        assert 'RB_ENV' in values
        assert 'SECRET_KEY' in values
        assert values['DATABASE_URL'].startswith('postgresql+psycopg://')

    def test_env_example_mentions_the_optional_variables(self):
        text = (ROOT / '.env.example').read_text()
        for name in ('RB_HOST', 'RB_PORT', 'PROXY_FIX_X_FOR', 'PROXY_FIX_X_PROTO',
                     'PROXY_FIX_X_HOST', 'RB_LEGACY_BACKUP_DIR'):
            assert name in text, f'.env.example must mention {name}'

    def test_env_example_placeholders_are_not_usable_credentials(self):
        values = dotenv_values(ROOT / '.env.example')
        # Copying the example unchanged must not pass production validation.
        with pytest.raises(config.ConfigError, match='SECRET_KEY'):
            config.validate_settings(
                {'SECRET_KEY': values['SECRET_KEY'],
                 'SQLALCHEMY_DATABASE_URI': values['DATABASE_URL']},
                'production')


# ---------------------------------------------------------------------------
# CFG-6 service unit (the spec marks the review MANUAL; the mechanical part is
# cheap to pin here)
# ---------------------------------------------------------------------------

SERVICE_FILE = ROOT / 'docs' / 'riftbound.service'


def _service_lines():
    """Non-comment, non-blank lines of the unit file."""
    return [line.strip() for line in SERVICE_FILE.read_text().splitlines()
            if line.strip() and not line.strip().startswith('#')]


class TestServiceUnit:
    def test_secrets_come_from_an_environment_file(self):
        assert 'EnvironmentFile=/etc/riftbound/riftbound.env' in _service_lines()

    @pytest.mark.parametrize('name', ['SECRET_KEY', 'DATABASE_URL'])
    def test_no_secret_literals_in_the_unit(self, name):
        assert [line for line in _service_lines() if name in line] == []

    def test_entry_point_is_run_app(self):
        exec_start = [line for line in _service_lines() if line.startswith('ExecStart=')]
        assert len(exec_start) == 1
        assert exec_start[0].endswith(' run:app')

    def test_rotation_and_firewall_advice_is_documented(self):
        text = SERVICE_FILE.read_text().lower()
        assert 'rotate' in text
        assert 'firewall' in text
        assert '8000' in text

    def test_stale_port_comment_is_gone(self):
        assert 'changed to port 8001' not in SERVICE_FILE.read_text().lower()
