"""
Pytest configuration and fixtures for Riftbound tests.
"""
import os
from datetime import datetime, timedelta

# D1: pin the environment BEFORE importing the app so `.env` is never read
# and the production-only checks never run against the test overrides.
os.environ['RB_ENV'] = 'testing'

import pytest
from flask import g
from unittest.mock import patch
from werkzeug.security import generate_password_hash
from app import create_app, db

# Variables read by the app factory / entry points (unit a).
CONFIG_ENV_NAMES = (
    'RB_ENV', 'SECRET_KEY', 'DATABASE_URL', 'FLASK_DEBUG', 'RB_HOST', 'RB_PORT',
    'PROXY_FIX_X_FOR', 'PROXY_FIX_X_PROTO', 'PROXY_FIX_X_HOST', 'RB_VERSION',
    # unit d
    'SESSION_COOKIE_SECURE', 'REMEMBER_COOKIE_SECURE', 'WTF_CSRF_ENABLED',
    'RATELIMIT_ENABLED', 'RATELIMIT_STORAGE_URI', 'CAPTCHA_PROVIDER', 'ALTCHA_HMAC_KEY',
    'ALTCHA_EXPIRE_SECONDS', 'ALTCHA_MAX_NUMBER', 'LANDING_CACHE_TTL',
    'LOGIN_MAX_FAILURES', 'LOGIN_LOCK_BASE_MINUTES', 'LOGIN_LOCK_MAX_MINUTES',
    # F1 unit b
    'FRONTEND_DIST',
    # F1 unit g
    'SPA_CSP',
)


@pytest.fixture
def clean_env(monkeypatch, tmp_path):
    """Unset every config variable (restored on teardown, even when a test
    triggers load_dotenv) and point the `.env` hook to a file that does not
    exist, so a developer's real `.env` can never leak into config tests.
    Returns the monkeypatch object for further setenv calls."""
    import app as app_module
    for name in CONFIG_ENV_NAMES:
        monkeypatch.setenv(name, 'placeholder')   # registers the original state
        monkeypatch.delenv(name)
    monkeypatch.setattr(app_module, 'DOTENV_PATH', str(tmp_path / 'missing.env'))
    return monkeypatch


@pytest.fixture
def app():
    """Create application for testing."""
    # Create application with test configuration overrides
    app = create_app(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        WTF_CSRF_ENABLED=False,
        SECRET_KEY='test-secret-key'
    )
    
    # The fixture keeps one app context open for the whole test, so Flask-Login's
    # per-context cache (`g._login_user`) would outlive the request and the
    # first user loaded would be "logged in" for every other client too. Drop
    # it before each request so every test client is identified by its own
    # session cookie (needed once a test uses more than one client, ACL-8).
    # Same for Flask-WTF's cached CSRF token (`g.csrf_token`): without this a
    # second client would be handed the first client's token.
    @app.before_request
    def _forget_cached_login():
        g.pop('_login_user', None)
        g.pop('csrf_token', None)

    with app.app_context():
        try:
            db.create_all()
            print("DB Tables created successfully") # Esto aparecerá si fallan los tests
        except Exception as e:
            print(f"Error creating DB tables: {e}")
            raise e
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def authenticated_client(app, client):
    """Create authenticated test client."""
    from app.models import User
    
    with app.app_context():
        # Create test user
        user = User(username='testuser', email='test@test.com')
        user.set_password('testpass123')
        db.session.add(user)
        db.session.commit()
        
        # Login
        client.post('/riftbound/login', data={
            'username': 'testuser',
            'password': 'testpass123'
        }, follow_redirects=True)
        
        yield client


# --- Users and roles (unit c, ACL-8) -------------------------------------------

DEFAULT_PASSWORD = 'testpass123'


@pytest.fixture
def make_user(app):
    """Factory: create (and commit) a user. Returns the User; the caller logs in
    through `login_as` or one of the *_client fixtures."""
    from app.models import User

    def _make(username, email=None, password=DEFAULT_PASSWORD, is_admin=False,
              is_blocked=False):
        user = User(username=username, email=email or f'{username}@test.com')
        # A cheap hash: the default (scrypt) costs ~0.2 s per user and most tests
        # create several. check_password() reads the method from the hash itself.
        user.password_hash = generate_password_hash(password, method='pbkdf2:sha256:1000')
        user.is_admin = is_admin
        user.is_blocked = is_blocked
        db.session.add(user)
        db.session.commit()
        return user

    return _make


def login_as(client, username, password=DEFAULT_PASSWORD):
    """Log `client` in through the real login form."""
    client.post('/riftbound/login', data={'username': username, 'password': password})
    return client


@pytest.fixture
def admin_client(app, make_user):
    """Its own test client, logged in as an admin (`admin`)."""
    make_user('admin', is_admin=True)
    return login_as(app.test_client(), 'admin')


@pytest.fixture
def other_user_client(app, make_user):
    """Its own test client, logged in as a second ordinary user (`otheruser`)."""
    make_user('otheruser')
    return login_as(app.test_client(), 'otheruser')


@pytest.fixture
def sample_set(app):
    """Create a sample set for testing."""
    from app.models import RbSet
    
    with app.app_context():
        set = RbSet(
            rbset_id='TEST1',
            rbset_name='Test Set 1',
            rbset_ncard=100
        )
        db.session.add(set)
        db.session.commit()
        
        # Refresh to get the committed data
        db.session.refresh(set)
        yield set


@pytest.fixture
def sample_card(app, sample_set):
    """Create a sample card for testing."""
    from app.models import RbCard
    
    with app.app_context():
        card = RbCard(
            rbcar_rbset_id=sample_set.rbset_id,
            rbcar_id='001',
            rbcar_name='Test Card',
            rbcar_type='Creature',
            rbcar_energy=3,
            rbcar_power=4,
            rbcar_might=5
        )
        db.session.add(card)
        db.session.commit()
        
        db.session.refresh(card)
        yield card


# --- Unit d: protections that are OFF in the default `app` (4.4) ---------------
#
# The default `app` has CSRF, the rate limiter and the captcha off, so the 93
# baseline tests (and everything written since) are untouched. These fixtures
# turn ONE protection on, on top of `app`, so they combine with `make_user`,
# `admin_client` and friends.
#
# Fixture ORDER matters when a test also asks for a logged-in client:
# `admin_client` and `other_user_client` log in through the real form, so
# request them BEFORE `csrf_app` (the login would otherwise need a token).

@pytest.fixture
def csrf_app(app):
    """`app` with CSRF protection on (CSRFProtect reads the flag per request)."""
    app.config['WTF_CSRF_ENABLED'] = True
    yield app
    app.config['WTF_CSRF_ENABLED'] = False


@pytest.fixture
def limited_app(app):
    """`app` with the rate limiter on and empty counters. The limiter is a
    process-wide singleton, so it is switched off and reset again on teardown."""
    from app import limiter
    app.config['RATELIMIT_ENABLED'] = True
    limiter.enabled = True
    limiter.reset()
    yield app
    limiter.reset()
    limiter.enabled = False
    app.config['RATELIMIT_ENABLED'] = False


@pytest.fixture
def altcha_app(app):
    """`app` with the ALTCHA provider and a tiny `max_number`, so a test can
    solve a challenge by brute force in milliseconds."""
    app.config['CAPTCHA_PROVIDER'] = 'altcha'
    app.config['ALTCHA_MAX_NUMBER'] = 1000
    yield app
    app.config['CAPTCHA_PROVIDER'] = 'none'


class FrozenClock:
    """Callable stand-in for `clock.utcnow` that only moves when told to."""

    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, **delta):
        self.now = self.now + timedelta(**delta)
        return self.now


@pytest.fixture
def frozen_clock(monkeypatch):
    """Freeze `app.utils.clock.utcnow` at 2030-01-01 12:00 UTC; call
    `frozen_clock.advance(minutes=16)` to move it (no sleeping, D17)."""
    from app.utils import clock
    frozen = FrozenClock(datetime(2030, 1, 1, 12, 0, 0))
    monkeypatch.setattr(clock, 'utcnow', frozen)
    return frozen


# --- Migrations (unit b) ------------------------------------------------------

@pytest.fixture
def migration_app(tmp_path):
    """App on empty in-memory SQLite (`riftbound` attached) with NO create_all:
    the schema is whatever Alembic builds. Legacy-table backups go to
    `tmp_path/backups` (MIG-4). Yielded inside an app context."""
    app = create_app(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        SECRET_KEY='test-secret-key',
        LEGACY_BACKUP_DIR=str(tmp_path / 'backups'),
    )
    with app.app_context():
        yield app
        db.session.remove()
        db.engine.dispose()


@pytest.fixture
def pg_url():
    """URL of a throw-away PostgreSQL database (D20).

    Skips unless TEST_POSTGRES_URL is set; REFUSES any database whose name does
    not contain "test" (never point this at dev data). Schema `riftbound` is
    dropped before and after each test, so each test starts from nothing and
    `flask db upgrade` has to create it (MIG-1)."""
    from sqlalchemy import create_engine, text
    from tests.migration_helpers import checked_test_database_url

    url = os.environ.get('TEST_POSTGRES_URL')
    if not url:
        pytest.skip('TEST_POSTGRES_URL is not set')
    try:
        checked_test_database_url(url)
    except ValueError as exc:
        pytest.fail(str(exc))

    engine = create_engine(url, isolation_level='AUTOCOMMIT')
    try:
        with engine.connect() as conn:
            conn.execute(text('DROP SCHEMA IF EXISTS riftbound CASCADE'))
        yield url
        with engine.connect() as conn:
            conn.execute(text('DROP SCHEMA IF EXISTS riftbound CASCADE'))
    finally:
        engine.dispose()


# --- F1 unit b: SPA hosting (2.6) -------------------------------------------------
#
# A temporary `dist/` stands in for the Vite build, so the Python lane never
# needs Node (CI-9). `secret.txt` sits NEXT TO the dist, not inside it.

SPA_INDEX_HTML = '<!doctype html><html><head><title>Rift Manager</title></head><body><div id="root"></div></body></html>\n'


@pytest.fixture
def spa_dist(tmp_path):
    """A fake frontend build. Returns the dist directory."""
    dist = tmp_path / 'dist'
    (dist / 'assets').mkdir(parents=True)
    (dist / 'index.html').write_text(SPA_INDEX_HTML, encoding='utf-8')
    (dist / 'assets' / 'app-abc123.js').write_text('console.log("rb");\n', encoding='utf-8')
    (dist / 'sw.js').write_text('self.skipWaiting;\n', encoding='utf-8')
    (dist / 'manifest.webmanifest').write_text('{"name":"Rift Manager"}\n', encoding='utf-8')
    (dist / 'pwa-192x192.png').write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00' * 16)
    (tmp_path / 'secret.txt').write_text('TOP-SECRET-OUTSIDE-DIST', encoding='utf-8')
    return dist


@pytest.fixture
def spa_app(app, spa_dist):
    """`app` whose FRONTEND_DIST points at `spa_dist` (read per request)."""
    app.config['FRONTEND_DIST'] = str(spa_dist)
    return app
