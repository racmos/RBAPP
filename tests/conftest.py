"""
Pytest configuration and fixtures for Riftbound tests.
"""
import os

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
    'PROXY_FIX_X_FOR', 'PROXY_FIX_X_PROTO', 'PROXY_FIX_X_HOST',
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
    @app.before_request
    def _forget_cached_login():
        g.pop('_login_user', None)

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
