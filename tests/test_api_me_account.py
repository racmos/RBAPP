"""PATCH /me/account: change the signed-in user's email and password (PR 1/3 of the Jinja retirement).

Same rules as the Jinja profile update (PROF-1, PROF-2): a new password needs the current one, the
email is unique ignoring case, and an email-only update does not need the password.
"""
import pytest

from app import db
from app.models import User

URL = '/riftbound/api/v1/me/account'
PASSWORD = 'testpass123'


def _patch(client, body):
    return client.patch(URL, json=body)


def _user(username='testuser'):
    return User.query.filter_by(username=username).one()


def _login_ok(app, username, password):
    response = app.test_client().post('/riftbound/api/v1/auth/login',
                                      json={'username': username, 'password': password})
    return response.status_code == 200


def test_changes_the_email_and_returns_the_fresh_user(authenticated_client):
    response = _patch(authenticated_client, {'email': '  New@Example.com '})
    assert response.status_code == 200
    user = response.get_json()['data']['user']
    assert user == {'id': _user().id, 'username': 'testuser', 'email': 'New@Example.com',
                    'is_admin': False, 'display_name': None, 'avatar_url': None}   # F9-b S6
    assert _user().email == 'New@Example.com'


def test_an_email_only_update_does_not_need_the_password(authenticated_client):
    assert _patch(authenticated_client, {'email': 'x@example.com'}).status_code == 200


def test_changes_the_password_and_keeps_the_caller_signed_in(app, authenticated_client):
    response = _patch(authenticated_client,
                      {'current_password': PASSWORD, 'password': 'brand-new-pass'})
    assert response.status_code == 200
    assert 'password' not in str(response.get_json()['data'])
    assert authenticated_client.get('/riftbound/api/v1/auth/session').get_json()[
        'data']['authenticated'] is True
    assert _login_ok(app, 'testuser', 'brand-new-pass')
    assert not _login_ok(app, 'testuser', PASSWORD)


def test_a_wrong_current_password_is_refused_and_changes_nothing(app, authenticated_client):
    response = _patch(authenticated_client,
                      {'current_password': 'not-it', 'password': 'brand-new-pass',
                       'email': 'other@example.com'})
    assert response.status_code == 400
    body = response.get_json()
    assert body['code'] == 'current_password_incorrect'
    assert body['message'] == 'The current password is incorrect'
    assert _user().email == 'test@test.com'
    assert _login_ok(app, 'testuser', PASSWORD)


def test_a_new_password_without_the_current_one_is_a_validation_error(authenticated_client):
    response = _patch(authenticated_client, {'password': 'brand-new-pass'})
    assert response.status_code == 400
    assert response.get_json()['code'] == 'validation_error'


def test_a_short_new_password_is_a_validation_error(authenticated_client):
    response = _patch(authenticated_client, {'current_password': PASSWORD, 'password': 'short'})
    assert response.status_code == 400
    body = response.get_json()
    assert body['code'] == 'validation_error'
    assert body['details'][0]['field'] == 'password'


def test_an_empty_body_is_a_validation_error(authenticated_client):
    response = _patch(authenticated_client, {})
    assert response.status_code == 400
    assert response.get_json()['code'] == 'validation_error'


def test_an_invalid_email_is_a_validation_error(authenticated_client):
    response = _patch(authenticated_client, {'email': 'no-at-sign'})
    assert response.status_code == 400
    assert response.get_json()['details'][0]['field'] == 'email'


def test_an_email_of_another_account_is_a_conflict_ignoring_case(make_user, authenticated_client):
    make_user('other', email='Taken@Example.com')
    response = _patch(authenticated_client, {'email': 'taken@example.COM'})
    assert response.status_code == 409
    body = response.get_json()
    assert body['code'] == 'email_taken'
    assert body['message'] == 'That email address is already in use'
    assert _user().email == 'test@test.com'


def test_keeping_the_own_email_with_another_case_is_fine(authenticated_client):
    assert _patch(authenticated_client, {'email': 'TEST@test.com'}).status_code == 200


def test_anonymous_callers_get_401(client):
    response = client.patch(URL, json={'email': 'x@example.com'})
    assert response.status_code == 401
    assert response.get_json()['code'] == 'unauthenticated'


def test_only_the_caller_is_changed(make_user, authenticated_client):
    make_user('bystander', email='by@example.com')
    _patch(authenticated_client, {'email': 'mine@example.com'})
    assert _user('bystander').email == 'by@example.com'
    db.session.rollback()


def test_the_password_check_is_rate_limited(limited_app, authenticated_client):
    codes = [_patch(authenticated_client,
                    {'current_password': 'wrong-one', 'password': 'brand-new-pass'}).status_code
             for _ in range(12)]
    assert codes[:10] == [400] * 10
    assert 429 in codes[10:]
    last = _patch(authenticated_client, {'current_password': 'wrong-one',
                                         'password': 'brand-new-pass'})
    assert last.get_json()['code'] == 'rate_limited'


# --- CHAR (F9-b S5): today's answers, pinned before the optional e-mail and re-auth ------------

def _value_error(message):
    return {'success': False, 'error': 'Validation Error', 'message': 'Invalid request data',
            'code': 'validation_error',
            'details': [{'field': '', 'message': f'Value error, {message}',
                         'type': 'value_error', 'code': 'invalid_value'}]}


@pytest.mark.parametrize('body', [{'password': 'brand-new-pass'},
                                  {'password': 'brand-new-pass', 'current_password': ''},
                                  {'password': 'brand-new-pass', 'email': 'new@example.com'}])
def test_char_a_missing_current_password_body(authenticated_client, body):
    response = _patch(authenticated_client, body)
    assert response.status_code == 400
    assert response.get_json() == _value_error(
        'current_password is required to change the password')
    assert _user().email == 'test@test.com'


@pytest.mark.parametrize('body', [{}, {'current_password': PASSWORD}, {'password': None}])
def test_char_nothing_to_change_body(authenticated_client, body):
    response = _patch(authenticated_client, body)
    assert response.status_code == 400
    assert response.get_json() == _value_error('Send an email or a new password')


# --- Optional e-mail, accounts without a password, password_changed_at (F9-b S3, S5) ---------

SESSION = '/riftbound/api/v1/auth/session'
FORBIDDEN = {'success': False, 'error': 'Forbidden',
             'message': 'Confirm your identity to continue', 'code': 'reauth_required',
             'params': {'methods': []}}


def _fresh(username='testuser'):
    db.session.expire_all()
    return _user(username)


@pytest.mark.parametrize('removed', [None, '', '   '])
def test_null_or_blank_removes_the_email(authenticated_client, removed):
    response = _patch(authenticated_client, {'email': removed})
    assert response.status_code == 200
    assert response.get_json()['data']['user']['email'] is None
    assert _fresh().email is None
    assert authenticated_client.get(SESSION).get_json()['data']['user']['email'] is None


def test_removing_the_email_with_a_password_change_needs_the_current_password(
        authenticated_client):
    response = _patch(authenticated_client, {'email': None, 'password': 'brand-new-pass'})
    assert response.get_json() == _value_error(
        'current_password is required to change the password')
    assert _fresh().email == 'test@test.com'


def test_an_email_can_be_added_back(authenticated_client):
    _patch(authenticated_client, {'email': None})
    assert _patch(authenticated_client, {'email': 'back@example.com'}).status_code == 200
    assert _fresh().email == 'back@example.com'


def test_a_password_change_stamps_password_changed_at(authenticated_client, frozen_clock):
    assert _patch(authenticated_client, {'current_password': PASSWORD,
                                         'password': 'brand-new-pass'}).status_code == 200
    assert _fresh().password_changed_at == frozen_clock.now


def test_an_email_change_keeps_password_changed_at(authenticated_client, frozen_clock):
    before = _fresh().password_changed_at
    frozen_clock.advance(minutes=1)
    _patch(authenticated_client, {'email': 'x@example.com'})
    assert _fresh().password_changed_at == before


class TestAccountWithoutPassword:
    @pytest.fixture
    def nopass(self, app, authenticated_client, frozen_clock):
        """`testuser` signed in, then its password removed (an OAuth-only account)."""
        user = _fresh()
        user.password_hash = None
        user.password_changed_at = None
        db.session.commit()
        return authenticated_client

    def test_a_first_password_with_a_stale_reauth_is_403(self, nopass, frozen_clock):
        frozen_clock.advance(minutes=10, seconds=1)
        response = _patch(nopass, {'password': 'brand-new-pass', 'email': 'new@example.com'})
        assert response.status_code == 403
        assert response.get_json() == FORBIDDEN
        user = _fresh()
        assert (user.password_hash, user.email, user.password_changed_at) == (
            None, 'test@test.com', None)

    def test_a_first_password_with_a_recent_reauth_is_set(self, app, nopass, frozen_clock):
        from app.services import sessions
        from tests.conftest import login_as
        other = app.test_client()
        frozen_clock.advance(minutes=30)
        [row] = sessions.list_active(_fresh().id, None)
        sessions.mark_reauth(row.rbses_id)
        assert _patch(nopass, {'password': 'brand-new-pass',
                               'current_password': 'ignored'}).status_code == 200
        user = _fresh()
        assert user.has_password and user.password_changed_at == frozen_clock.now
        assert nopass.get(SESSION).get_json()['data']['authenticated'] is True
        assert login_as(other, 'testuser', 'brand-new-pass')

    def test_the_first_password_ends_the_other_sessions(self, app, nopass, frozen_clock):
        from app.services import sessions
        from tests.conftest import login_as
        user = _fresh()
        user.set_password('temporary-pass')
        db.session.commit()
        elsewhere = login_as(app.test_client(), 'testuser', 'temporary-pass')
        user.password_hash = None
        db.session.commit()
        assert _patch(nopass, {'password': 'brand-new-pass'}).status_code == 200
        assert elsewhere.get(SESSION).get_json()['data']['authenticated'] is False
        assert nopass.get(SESSION).get_json()['data']['authenticated'] is True
        assert len(sessions.list_active(user.id, None)) == 1

    def test_the_email_needs_no_reauth(self, nopass, frozen_clock):
        frozen_clock.advance(hours=1)
        assert _patch(nopass, {'email': None}).status_code == 200
        assert _patch(nopass, {'email': 'again@example.com'}).status_code == 200
        assert _fresh().email == 'again@example.com'

    def test_nothing_to_change_is_still_the_400(self, nopass):
        assert _patch(nopass, {'current_password': 'x'}).get_json() == _value_error(
            'Send an email or a new password')
