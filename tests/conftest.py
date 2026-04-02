"""
Pytest configuration and fixtures for Riftbound tests.
"""
import pytest
from app import create_app, db


@pytest.fixture
def app():
    """Create application for testing."""
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['SECRET_KEY'] = 'test-secret-key'
    
    with app.app_context():
        db.create_all()
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
