"""
Pytest configuration and fixtures for Riftbound tests.
"""
import os

# D1: pin the environment BEFORE importing the app so `.env` is never read
# and the production-only checks never run against the test overrides.
os.environ['RB_ENV'] = 'testing'

import pytest
from unittest.mock import patch
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
