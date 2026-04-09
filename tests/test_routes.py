"""
Basic tests for Riftbound routes.
"""
import pytest
import json


class TestAuth:
    """Test authentication routes."""
    
    def test_login_page_loads(self, client):
        """Login page should load successfully."""
        response = client.get('/riftbound/login')
        assert response.status_code == 200
    
    def test_register_page_loads(self, client):
        """Register page should load successfully."""
        response = client.get('/riftbound/register')
        assert response.status_code == 200
    
    def test_login_success(self, app, client):
        """Valid credentials should login successfully."""
        from app.models import User
        from app import db
        
        with app.app_context():
            user = User(username='logintest', email='login@test.com')
            user.set_password('password123')
            db.session.add(user)
            db.session.commit()
        
        response = client.post('/riftbound/login', data={
            'username': 'logintest',
            'password': 'password123'
        }, follow_redirects=True)
        
        assert response.status_code == 200
    
    def test_login_invalid_credentials(self, client):
        """Invalid credentials should fail."""
        response = client.post('/riftbound/login', data={
            'username': 'nonexistent',
            'password': 'wrongpass'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        # Should show error message
        assert b'Invalid' in response.data or b'error' in response.data
    
    def test_register_success(self, client):
        """Registration should succeed with valid data."""
        response = client.post('/riftbound/register', data={
            'username': 'newuser',
            'email': 'new@test.com',
            'password': 'securepass123'
        }, follow_redirects=True)
        
        assert response.status_code == 200
    
    def test_register_duplicate_username(self, app, client):
        """Duplicate username should fail."""
        from app.models import User
        from app import db
        
        with app.app_context():
            user = User(username='duplicate', email='first@test.com')
            user.set_password('password')
            db.session.add(user)
            db.session.commit()
        
        response = client.post('/riftbound/register', data={
            'username': 'duplicate',
            'email': 'second@test.com',
            'password': 'password'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'already' in response.data or b'error' in response.data


class TestProtectedRoutes:
    """Test routes that require authentication."""
    
    def test_dashboard_requires_login(self, client):
        """Dashboard should redirect to login if not authenticated."""
        response = client.get('/riftbound/', follow_redirects=False)
        assert response.status_code == 302
        assert '/login' in response.location
    
    def test_dashboard_loads_authenticated(self, authenticated_client):
        """Dashboard should load for authenticated users."""
        response = authenticated_client.get('/riftbound/')
        assert response.status_code == 200
    
    def test_sets_requires_login(self, client):
        """Sets page should redirect to login if not authenticated."""
        response = client.get('/riftbound/set', follow_redirects=False)
        assert response.status_code == 302
    
    def test_cards_requires_login(self, client):
        """Cards page should redirect to login if not authenticated."""
        response = client.get('/riftbound/card', follow_redirects=False)
        assert response.status_code == 302
    
    def test_collection_requires_login(self, client):
        """Collection page should redirect to login if not authenticated."""
        response = client.get('/riftbound/collection', follow_redirects=False)
        assert response.status_code == 302


class TestSetsAPI:
    """Test Sets API endpoints."""
    
    def test_get_sets(self, authenticated_client, sample_set):
        """Should return list of sets."""
        response = authenticated_client.get('/riftbound/set')
        assert response.status_code == 200
    
    def test_add_set_success(self, authenticated_client, app):
        """Should add a new set."""
        response = authenticated_client.post('/riftbound/set/add',
            json={'rbset_id': 'NEW1', 'rbset_name': 'New Set'},
            content_type='application/json'
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        
        # Verify in database
        from app.models import RbSet
        with app.app_context():
            set = RbSet.query.filter_by(rbset_id='NEW1').first()
            assert set is not None
            assert set.rbset_name == 'New Set'
    
    def test_add_set_duplicate_id(self, authenticated_client, sample_set):
        """Should fail when adding set with duplicate ID."""
        response = authenticated_client.post('/riftbound/set/add',
            json={'rbset_id': 'TEST1', 'rbset_name': 'Duplicate'},
            content_type='application/json'
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'already exists' in data['message']
    
    def test_add_set_duplicate_name(self, authenticated_client, sample_set):
        """Should fail when adding set with duplicate name."""
        response = authenticated_client.post('/riftbound/set/add',
            json={'rbset_id': 'DIFF1', 'rbset_name': 'Test Set 1'},
            content_type='application/json'
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False


class TestCardsAPI:
    """Test Cards API endpoints."""
    
    def test_get_cards(self, authenticated_client, sample_card):
        """Should return list of cards."""
        response = authenticated_client.get('/riftbound/card')
        assert response.status_code == 200
    
    def test_get_cards_pagination(self, authenticated_client, sample_card):
        """Should handle pagination parameters."""
        response = authenticated_client.get('/riftbound/card?page=1&per_page=10')
        assert response.status_code == 200
    
    def test_add_card_success(self, authenticated_client, sample_set):
        """Should add a new card."""
        response = authenticated_client.post('/riftbound/card/add',
            json={
                'rbcar_rbset_id': 'TEST1',
                'rbcar_id': 'NEW001',
                'rbcar_name': 'New Test Card',
                'rbcar_type': 'Spell'
            },
            content_type='application/json'
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
    
    def test_add_card_duplicate(self, authenticated_client, sample_card):
        """Should fail when adding duplicate card."""
        response = authenticated_client.post('/riftbound/card/add',
            json={
                'rbcar_rbset_id': 'TEST1',
                'rbcar_id': '001',
                'rbcar_name': 'Duplicate Card'
            },
            content_type='application/json'
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False


class TestCollectionAPI:
    """Test Collection API endpoints."""
    
    def test_get_collection(self, authenticated_client):
        """Should return user's collection."""
        response = authenticated_client.get('/riftbound/collection')
        assert response.status_code == 200
    
    def test_add_to_collection(self, authenticated_client, sample_card):
        """Should add card to collection."""
        response = authenticated_client.post('/riftbound/collection/add',
            json={
                'rbcol_rbset_id': 'TEST1',
                'rbcol_rbcar_id': '001',
                'rbcol_quantity': 2
            },
            content_type='application/json'
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
    
    def test_add_nonexistent_card_to_collection(self, authenticated_client):
        """Should fail when adding nonexistent card."""
        response = authenticated_client.post('/riftbound/collection/add',
            json={
                'rbcol_rbset_id': 'NONEX',
                'rbcol_rbcar_id': '999',
                'rbcol_quantity': 1
            },
            content_type='application/json'
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False


class TestProfileAPI:
    """Test Profile API endpoints."""
    
    def test_get_profile(self, authenticated_client):
        """Should return user profile."""
        response = authenticated_client.get('/riftbound/profile')
        assert response.status_code == 200
    
    def test_update_email(self, authenticated_client):
        """Should update user email."""
        response = authenticated_client.post('/riftbound/profile/update',
            json={'email': 'newemail@test.com'},
            content_type='application/json'
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
    
    def test_update_password(self, authenticated_client):
        """Should update user password."""
        response = authenticated_client.post('/riftbound/profile/update',
            json={'password': 'newpassword123'},
            content_type='application/json'
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
