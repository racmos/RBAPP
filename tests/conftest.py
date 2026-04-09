"""
Pytest configuration and fixtures for Riftbound tests.
"""
import os
import pytest
from unittest.mock import patch
from app import create_app, db

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
