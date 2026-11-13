"""F9-b S6-S8 (AC4, AC6): the caller's private profile: GET /me and PATCH /me, and the
`display_name` / `avatar_url` keys of every user payload."""
import pytest
import sqlalchemy as sa
from sqlalchemy import event

from app import db
from app.models import RbUserProfile, User
from tests.conftest import DEFAULT_PASSWORD, login_as

API = '/riftbound/api/v1'
ME = f'{API}/me'
NOW = '2030-01-01T12:00:00Z'
EMPTY_PROFILE = {'display_name': None, 'bio': None, 'country': None, 'city': None,
                 'avatar_url': None, 'updated_at': None}
# F9-d S14: the default test app has a TOTP key, so 2FA is available and off.
MFA_OFF = {'available': True, 'enabled': False, 'pending': False, 'recovery_codes_left': 0}


@pytest.fixture
def ana(app, make_user, frozen_clock):
    """`ana` signed in at the frozen time (2030-01-01 12:00 UTC); returns her client."""
    make_user('ana')
    return login_as(app.test_client(), 'ana')


def ana_id():
    return User.query.filter_by(username='ana').one().id


def profiles():
    db.session.expire_all()
    return db.session.execute(sa.select(RbUserProfile)).scalars().all()


def patch(client, body):
    return client.patch(ME, json=body)


def validation(response):
    assert response.status_code == 400, response.get_json()
    body = response.get_json()
    assert (body['code'], body['error']) == ('validation_error', 'Validation Error')
    return [{k: d.get(k) for k in ('field', 'code', 'params')} for d in body['details']]


# --- GET /me (S7) ---------------------------------------------------------------------------

class TestGetMe:
    def test_the_shape_and_the_defaults(self, ana):
        response = ana.get(ME)
        assert response.status_code == 200
        assert response.get_json()['data'] == {
            'user': {'id': ana_id(), 'username': 'ana', 'email': 'ana@test.com',
                     'is_admin': False, 'display_name': None, 'avatar_url': None},
            'profile': EMPTY_PROFILE,
            'security': {
                'has_password': True, 'password_changed_at': None, 'member_since': NOW,
                'mfa': MFA_OFF, 'sessions_active': 1, 'api_key': None, 'connections': [],
                'reauth_until': '2030-01-01T12:10:00Z'},
        }

    def test_reading_never_creates_a_profile(self, ana):
        ana.get(ME)
        ana.get(ME)
        assert profiles() == []

    def test_sessions_active_counts_only_the_callers_active_sessions(self, app, ana, make_user):
        login_as(app.test_client(), 'ana')
        ended = login_as(app.test_client(), 'ana')
        ended.post(f'{API}/auth/logout')
        make_user('bo')
        login_as(app.test_client(), 'bo')
        assert ana.get(ME).get_json()['data']['security']['sessions_active'] == 2

    def test_reauth_until_is_null_once_the_window_has_passed(self, ana, frozen_clock):
        frozen_clock.advance(minutes=9, seconds=59)
        assert ana.get(ME).get_json()['data']['security']['reauth_until'] == \
            '2030-01-01T12:10:00Z'
        frozen_clock.advance(seconds=1)
        assert ana.get(ME).get_json()['data']['security']['reauth_until'] is None

    def test_password_changed_at_and_has_password(self, ana, frozen_clock):
        user = User.query.filter_by(username='ana').one()
        user.password_changed_at = frozen_clock.now
        db.session.commit()
        security = ana.get(ME).get_json()['data']['security']
        assert (security['has_password'], security['password_changed_at']) == (True, NOW)
        user.password_hash = None
        db.session.commit()
        assert ana.get(ME).get_json()['data']['security']['has_password'] is False

    def test_a_null_email_is_null(self, ana):
        User.query.filter_by(username='ana').one().email = None
        db.session.commit()
        assert ana.get(ME).get_json()['data']['user']['email'] is None

    @pytest.mark.parametrize('with_profile', [False, True])
    def test_at_most_five_statements(self, ana, with_profile):
        if with_profile:
            assert patch(ana, {'display_name': 'Ana', 'city': 'Madrid'}).status_code == 200
        db.session.expire_all()
        seen = []

        def record(conn, cursor, statement, parameters, context, executemany):
            seen.append(statement)

        event.listen(db.engine, 'before_cursor_execute', record)
        try:
            assert ana.get(ME).status_code == 200
        finally:
            event.remove(db.engine, 'before_cursor_execute', record)
        assert len(seen) <= 5, seen

    def test_anonymous_is_401(self, client):
        response = client.get(ME)
        assert (response.status_code, response.get_json()['code']) == (401, 'unauthenticated')


# --- PATCH /me (S8) -------------------------------------------------------------------------

class TestPatchMe:
    def test_the_spec_example(self, ana):
        response = patch(ana, {'display_name': '  Ana  ', 'country': 'es'})
        assert response.status_code == 200
        data = response.get_json()['data']
        assert data['profile'] == {'display_name': 'Ana', 'bio': None, 'country': 'ES',
                                   'city': None, 'avatar_url': None, 'updated_at': NOW}
        assert data['user']['display_name'] == 'Ana'
        assert data == ana.get(ME).get_json()['data']
        [row] = profiles()
        assert (row.rbupf_user_id, row.rbupf_display_name, row.rbupf_country) == (
            ana_id(), 'Ana', 'ES')

    def test_absent_is_unchanged_and_every_patch_stamps_updated_at(self, ana, frozen_clock):
        patch(ana, {'display_name': 'Ana', 'country': 'ES', 'city': 'Madrid'})
        frozen_clock.advance(minutes=5)
        profile = patch(ana, {'bio': 'Line one\nLine two'}).get_json()['data']['profile']
        assert profile == {'display_name': 'Ana', 'bio': 'Line one\nLine two', 'country': 'ES',
                           'city': 'Madrid', 'avatar_url': None,
                           'updated_at': '2030-01-01T12:05:00Z'}
        frozen_clock.advance(minutes=5)
        profile = patch(ana, {}).get_json()['data']['profile']
        assert profile['updated_at'] == '2030-01-01T12:10:00Z'
        assert profile['display_name'] == 'Ana'

    @pytest.mark.parametrize('cleared', [None, '', '   '])
    def test_null_or_blank_clears(self, ana, cleared):
        patch(ana, {'display_name': 'Ana', 'bio': 'Hi', 'country': 'ES', 'city': 'Madrid'})
        body = {key: cleared for key in ('display_name', 'bio', 'country', 'city')}
        profile = patch(ana, body).get_json()['data']['profile']
        assert {k: profile[k] for k in body} == dict.fromkeys(body)
        assert ana.get(f'{API}/auth/session').get_json()['data']['user']['display_name'] is None

    @pytest.mark.parametrize('field, limit', [('display_name', 40), ('bio', 240), ('city', 80)])
    def test_length_limits_after_trimming(self, ana, field, limit):
        fits = '  ' + 'a' * limit + '  '
        assert patch(ana, {field: fits}).get_json()['data']['profile'][field] == 'a' * limit
        details = validation(patch(ana, {field: 'a' * (limit + 1)}))
        assert details == [{'field': field, 'code': 'too_long', 'params': {'max': limit}}]
        assert profiles()[0].__getattribute__(f'rbupf_{field}') == 'a' * limit

    @pytest.mark.parametrize('field, value', [
        ('display_name', 'Ana\tB'), ('display_name', 'Ana\nB'), ('display_name', 'A\x00'),
        ('display_name', 'A\x7f'), ('city', 'Ma\ndrid'), ('city', 'Ma\x1bdrid'),
        ('bio', 'Hi\x07there'), ('bio', 'Hi\tthere'),
    ])
    def test_control_characters_are_refused(self, ana, field, value):
        assert validation(patch(ana, {field: value})) == [
            {'field': field, 'code': 'invalid_format', 'params': None}]
        assert profiles() == []

    def test_the_bio_keeps_line_breaks(self, ana):
        bio = 'First line\nSecond line\r\nThird line'
        assert patch(ana, {'bio': f'  {bio}\n'}).get_json()['data']['profile']['bio'] == bio

    @pytest.mark.parametrize('given, stored', [('es', 'ES'), ('Es', 'ES'), ('GB', 'GB'),
                                               (' fr ', 'FR'), ('ax', 'AX')])
    def test_country_codes_are_stored_upper_case(self, ana, given, stored):
        assert patch(ana, {'country': given}).get_json()['data']['profile']['country'] == stored

    @pytest.mark.parametrize('given', ['XX', 'UK', 'ESP', 'E', 'e1', 34])
    def test_unknown_country_codes_are_refused(self, ana, given):
        assert validation(patch(ana, {'country': given})) == [
            {'field': 'country', 'code': 'invalid_value', 'params': None}]

    def test_all_or_nothing(self, ana):
        patch(ana, {'display_name': 'Ana'})
        details = validation(patch(ana, {'display_name': 'Changed', 'bio': 'Fine',
                                         'country': 'XX'}))
        assert [d['field'] for d in details] == ['country']
        [row] = profiles()
        assert (row.rbupf_display_name, row.rbupf_bio, row.rbupf_country) == ('Ana', None, None)

    def test_a_refused_first_patch_creates_no_row(self, ana):
        validation(patch(ana, {'display_name': 'x' * 41}))
        assert profiles() == []

    def test_unknown_keys_change_nothing(self, ana):
        response = patch(ana, {'username': 'mallory', 'email': 'evil@test.com', 'is_admin': True,
                               'avatar_url': 'http://x', 'display_name': 'Ana'})
        assert response.status_code == 200
        user = User.query.filter_by(id=ana_id()).one()
        assert (user.username, user.email, user.is_admin) == ('ana', 'ana@test.com', False)
        assert response.get_json()['data']['user']['avatar_url'] is None

    def test_only_the_callers_profile_changes(self, app, ana, make_user):
        make_user('bo')
        bo = login_as(app.test_client(), 'bo')
        patch(bo, {'display_name': 'Bo'})
        patch(ana, {'display_name': 'Ana'})
        assert bo.get(ME).get_json()['data']['profile']['display_name'] == 'Bo'
        assert ana.get(ME).get_json()['data']['profile']['display_name'] == 'Ana'

    def test_not_json_object_is_400(self, ana):
        response = ana.patch(ME, data='display_name=Ana')
        assert response.status_code == 400

    def test_anonymous_is_401(self, client):
        response = client.patch(ME, json={'display_name': 'Ana'})
        assert (response.status_code, response.get_json()['code']) == (401, 'unauthenticated')


# --- The user payload (S6) ------------------------------------------------------------------

USER_KEYS = ['avatar_url', 'display_name', 'email', 'id', 'is_admin', 'username']


class TestUserPayload:
    def test_every_payload_carries_the_display_name(self, app, ana):
        patch(ana, {'display_name': 'Ana B.'})
        session = ana.get(f'{API}/auth/session').get_json()['data']['user']
        login = app.test_client().post(f'{API}/auth/login', json={
            'username': 'ana', 'password': DEFAULT_PASSWORD}).get_json()['data']['user']
        account = ana.patch(f'{API}/me/account', json={'email': 'ana@new.com'}).get_json()[
            'data']['user']
        me = ana.get(ME).get_json()['data']['user']
        for payload in (session, login, account, me):
            assert sorted(payload) == USER_KEYS
            assert (payload['display_name'], payload['avatar_url']) == ('Ana B.', None)
        assert account == me == {**session, 'email': 'ana@new.com'}

    def test_without_a_profile_both_are_null(self, app, ana):
        user = ana.get(f'{API}/auth/session').get_json()['data']['user']
        assert (user['display_name'], user['avatar_url']) == (None, None)
