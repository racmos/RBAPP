"""
Profile update (PROF-1..PROF-3): `POST /riftbound/profile/update`.
"""
import re

import pytest
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import User
from tests.conftest import login_as

URL = '/riftbound/profile/update'


@pytest.fixture
def people(app, make_user):
    """alice (a@x.io) and bob (b@x.io, password oldpass1), bob logged in."""
    make_user('alice', email='a@x.io', password='alicepass1')
    make_user('bob', email='b@x.io', password='oldpass1')
    return login_as(app.test_client(), 'bob', 'oldpass1')


def bob():
    db.session.expire_all()
    return User.query.filter_by(username='bob').one()


# ---------------------------------------------------------------------------
# PROF-1 duplicate email is a client error
# ---------------------------------------------------------------------------

class TestDuplicateEmail:
    def test_a_taken_email_is_409_even_with_other_case_and_spaces(self, people):
        resp = people.post(URL, json={'email': 'A@x.io '})
        assert resp.status_code == 409
        assert resp.json['success'] is False
        assert resp.json['error'] == 'Conflict'
        assert resp.json['message']
        assert bob().email == 'b@x.io'

    def test_the_comparison_is_case_insensitive_against_a_mixed_case_stored_email(
            self, app, make_user):
        make_user('carol', email='Carol@Example.COM')
        make_user('dave', email='dave@example.com')
        client = login_as(app.test_client(), 'dave')
        resp = client.post(URL, json={'email': ' carol@example.com'})
        assert resp.status_code == 409
        assert User.query.filter_by(username='dave').one().email == 'dave@example.com'

    def test_my_own_email_is_accepted(self, people):
        resp = people.post(URL, json={'email': 'b@x.io'})
        assert resp.status_code == 200
        assert resp.json == {'success': True}
        assert bob().email == 'b@x.io'

    def test_my_own_email_in_another_case_is_accepted(self, people):
        resp = people.post(URL, json={'email': 'B@X.io'})
        assert resp.status_code == 200
        assert bob().email == 'B@X.io'

    def test_a_free_email_is_saved_trimmed(self, people):
        resp = people.post(URL, json={'email': '  new@x.io '})
        assert resp.status_code == 200
        assert bob().email == 'new@x.io'

    def test_a_violation_only_detected_at_commit_is_409_and_rolled_back(
            self, app, people, monkeypatch):
        def failing_commit():
            raise IntegrityError('UPDATE rbusers', {}, Exception('duplicate key'))

        monkeypatch.setattr(db.session, 'commit', failing_commit)
        resp = people.post(URL, json={'email': 'race@x.io'})
        monkeypatch.undo()                                  # real commit again

        assert resp.status_code == 409
        assert resp.json['error'] == 'Conflict'
        assert bob().email == 'b@x.io'                      # not dirty, not saved
        # the session is usable again (it was rolled back, not left poisoned)
        assert people.post(URL, json={'email': 'later@x.io'}).status_code == 200
        assert bob().email == 'later@x.io'

    def test_a_409_leaves_a_simultaneous_password_change_unapplied(self, people):
        resp = people.post(URL, json={'email': 'a@x.io', 'password': 'newpass12',
                                      'current_password': 'oldpass1'})
        assert resp.status_code == 409
        assert bob().check_password('oldpass1')
        assert not bob().check_password('newpass12')


# ---------------------------------------------------------------------------
# PROF-2 a password change needs the current password
# ---------------------------------------------------------------------------

class TestPasswordChange:
    def test_the_correct_current_password_changes_it(self, people):
        resp = people.post(URL, json={'password': 'newpass12', 'current_password': 'oldpass1'})
        assert resp.status_code == 200
        assert resp.json == {'success': True}
        assert bob().check_password('newpass12')
        assert not bob().check_password('oldpass1')

    def test_a_missing_current_password_is_400_and_keeps_the_old_one(self, people):
        resp = people.post(URL, json={'password': 'newpass12'})
        assert resp.status_code == 400
        assert resp.json['success'] is False and resp.json['message']
        assert bob().check_password('oldpass1')

    @pytest.mark.parametrize('wrong', ['nope', '', 'oldpass1 ', 'OLDPASS1'])
    def test_a_wrong_current_password_is_400_and_keeps_the_old_one(self, people, wrong):
        resp = people.post(URL, json={'password': 'newpass12', 'current_password': wrong})
        assert resp.status_code == 400
        assert resp.json['success'] is False and resp.json['message']
        assert bob().check_password('oldpass1')
        assert not bob().check_password('newpass12')

    @pytest.mark.parametrize('short', ['1234567', 'a', 'short'])
    def test_a_new_password_under_8_characters_is_400(self, people, short):
        resp = people.post(URL, json={'password': short, 'current_password': 'oldpass1'})
        assert resp.status_code == 400
        assert bob().check_password('oldpass1')

    def test_exactly_8_characters_is_accepted(self, people):
        resp = people.post(URL, json={'password': '12345678', 'current_password': 'oldpass1'})
        assert resp.status_code == 200
        assert bob().check_password('12345678')

    def test_an_email_only_update_does_not_need_the_current_password(self, people):
        resp = people.post(URL, json={'email': 'new@x.io'})
        assert resp.status_code == 200
        assert bob().email == 'new@x.io'
        assert bob().check_password('oldpass1')

    def test_a_current_password_alone_changes_nothing(self, people):
        resp = people.post(URL, json={'current_password': 'oldpass1'})
        assert resp.status_code == 200
        assert bob().check_password('oldpass1') and bob().email == 'b@x.io'

    def test_email_and_password_can_change_together(self, people):
        resp = people.post(URL, json={'email': 'new@x.io', 'password': 'newpass12',
                                      'current_password': 'oldpass1'})
        assert resp.status_code == 200
        assert (bob().email, bob().check_password('newpass12')) == ('new@x.io', True)

    def test_the_current_password_is_not_stored_or_echoed(self, people):
        resp = people.post(URL, json={'password': 'newpass12', 'current_password': 'oldpass1'})
        assert 'oldpass1' not in resp.get_data(as_text=True)
        assert 'newpass12' not in resp.get_data(as_text=True)


# ---------------------------------------------------------------------------
# PROF-3 stays authenticated, keeps validating
# ---------------------------------------------------------------------------

class TestAuthenticationAndValidation:
    def test_anonymous_callers_change_nothing(self, app, people, client):
        before = [(u.username, u.email, u.password_hash) for u in User.query.order_by(User.id)]
        for body in ({'email': 'hacked@x.io'},
                     {'password': 'newpass12', 'current_password': 'oldpass1'}):
            resp = client.post(URL, json=body)
            assert resp.status_code in (302, 401)
        db.session.expire_all()
        assert [(u.username, u.email, u.password_hash)
                for u in User.query.order_by(User.id)] == before

    @pytest.mark.parametrize('email', ['nope', '', '   '])
    def test_an_invalid_email_is_400_validation_error(self, people, email):
        resp = people.post(URL, json={'email': email})
        assert resp.status_code == 400
        assert resp.json['error'] == 'Validation Error'
        assert bob().email == 'b@x.io'


# ---------------------------------------------------------------------------
# The page asks for the current password and sends it
# ---------------------------------------------------------------------------

class TestProfilePage:
    def test_has_a_current_password_input_and_the_script_sends_it(self, people):
        html = people.get('/riftbound/profile').get_data(as_text=True)
        assert 'id="current_password"' in html
        assert re.search(r'<input[^>]*type="password"[^>]*id="current_password"'
                         r'|<input[^>]*id="current_password"[^>]*type="password"', html)
        assert 'data.current_password' in html

    def test_the_form_still_has_the_new_password_fields(self, people):
        html = people.get('/riftbound/profile').get_data(as_text=True)
        assert 'id="password"' in html and 'id="password_confirm"' in html
