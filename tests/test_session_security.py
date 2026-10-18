"""
Characterization test for key rotation (SESS-3).

Flask signs the session cookie with SECRET_KEY, so a cookie signed with another
key must be ignored and the visitor treated as anonymous. This already holds
today; the test pins it so the config rework of unit a cannot regress it.
"""
import pytest

from app import create_app, db
from app.models import User

KEY_A = 'rotation-test-key-A-' + 'a' * 20
KEY_B = 'rotation-test-key-B-' + 'b' * 20
USERNAME = 'rotuser'
PASSWORD = 'rotpass123'


def _make_app(secret_key):
    """Own in-memory DB per app, with the same user (id 1) in both, so that an
    accepted cookie would resolve to a real user and give 200."""
    app = create_app(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        SECRET_KEY=secret_key,
    )
    with app.app_context():
        db.create_all()
        user = User(username=USERNAME, email='rot@test.com')
        user.set_password(PASSWORD)
        db.session.add(user)
        db.session.commit()
    return app


def _logged_in_session_cookie(app):
    client = app.test_client()
    resp = client.post('/riftbound/login',
                       data={'username': USERNAME, 'password': PASSWORD})
    assert resp.status_code == 302
    cookie = client.get_cookie('session')
    assert cookie is not None
    return cookie.value


def _client_with_cookie(app, value):
    client = app.test_client()
    client.set_cookie('session', value)
    return client


@pytest.fixture
def app_a():
    return _make_app(KEY_A)


@pytest.fixture
def app_b():
    return _make_app(KEY_B)


class TestKeyRotation:
    def test_cookie_is_accepted_by_an_app_with_the_same_key(self, app_a):
        # Control: proves the cookie really authenticates, so the next test
        # is not passing because of a broken setup.
        value = _logged_in_session_cookie(app_a)
        resp = _client_with_cookie(_make_app(KEY_A), value).get('/riftbound/')
        assert resp.status_code == 200

    def test_cookie_signed_with_another_key_is_anonymous(self, app_a, app_b):
        value = _logged_in_session_cookie(app_a)
        resp = _client_with_cookie(app_b, value).get('/riftbound/')
        assert resp.status_code == 302
        assert '/riftbound/login' in resp.headers['Location']

    def test_rotation_works_in_both_directions(self, app_a, app_b):
        value = _logged_in_session_cookie(app_b)
        resp = _client_with_cookie(app_a, value).get('/riftbound/')
        assert resp.status_code == 302
        assert '/riftbound/login' in resp.headers['Location']
