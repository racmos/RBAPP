"""PATCH /me/account: change the signed-in user's email and password (PR 1/3 of the Jinja retirement).

Same rules as the Jinja profile update (PROF-1, PROF-2): a new password needs the current one, the
email is unique ignoring case, and an email-only update does not need the password.
"""
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
                    'is_admin': False}
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
