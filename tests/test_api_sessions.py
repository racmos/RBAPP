"""F9-a S10-S12 (AC3): the caller's signed-in devices: GET /me/sessions, DELETE /me/sessions/<id>
and DELETE /me/sessions.

IP addresses come only from the documentation ranges (RFC 5737)."""
from datetime import timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy import event

from app import db
from app.models import RbSession
from tests.conftest import DEFAULT_PASSWORD

API = '/riftbound/api/v1'
LOGIN = f'{API}/auth/login'
SESSION = f'{API}/auth/session'
SESSIONS = f'{API}/me/sessions'
FIREFOX = 'Mozilla/5.0 (X11; Linux x86_64; rv:132.0) Gecko/20100101 Firefox/132.0'
SAFARI = ('Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 '
          '(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1')
NOT_FOUND = {'success': False, 'error': 'Not Found'}


def sign_in(app, username='ana', remember=False, user_agent=FIREFOX, addr='192.0.2.10'):
    client = app.test_client()
    response = client.post(LOGIN, json={'username': username, 'password': DEFAULT_PASSWORD,
                                        'remember': remember},
                           headers={'User-Agent': user_agent},
                           environ_base={'REMOTE_ADDR': addr})
    assert response.status_code == 200
    return client


def authenticated(client):
    return client.get(SESSION).get_json()['data']['authenticated']


def items(client):
    response = client.get(SESSIONS)
    assert response.status_code == 200
    return response.get_json()['data']['items']


def rows():
    db.session.expire_all()
    return db.session.execute(sa.select(RbSession).order_by(RbSession.rbses_id)).scalars().all()


def set_cookies(response, name):
    return [c for c in response.headers.getlist('Set-Cookie') if c.startswith(f'{name}=')]


@pytest.fixture
def ana(make_user):
    return make_user('ana')


# --- GET /me/sessions (S10) -----------------------------------------------------------------

class TestList:
    def test_the_shape_of_one_session(self, app, ana, frozen_clock):
        client = sign_in(app, remember=True, addr='203.0.113.77')
        [item] = items(client)
        assert item == {
            'id': rows()[0].rbses_id, 'current': True, 'device': 'Firefox on Linux',
            'user_agent': FIREFOX, 'ip_prefix': '203.0.113.0/24',
            'created_at': '2030-01-01T12:00:00Z', 'last_seen_at': '2030-01-01T12:00:00Z',
            'expires_at': '2030-01-31T12:00:00Z', 'remember': True,
            'auth_method': 'password', 'mfa': False}

    def test_a_session_that_is_not_remembered_has_no_expiry(self, app, ana, frozen_clock):
        [item] = items(sign_in(app))
        assert (item['remember'], item['expires_at']) == (False, None)

    def test_never_the_token_or_its_hash(self, app, ana, frozen_clock):
        client = sign_in(app)
        with client.session_transaction() as flask_session:
            token = flask_session['_user_id'][2:]
        text = client.get(SESSIONS).get_data(as_text=True)
        assert token not in text
        assert rows()[0].rbses_token_hash not in text
        assert 'token' not in text and 'hash' not in text

    def test_current_first_then_most_recently_used(self, app, ana, frozen_clock):
        first = sign_in(app)
        frozen_clock.advance(minutes=1)
        second = sign_in(app, user_agent=SAFARI)
        frozen_clock.advance(minutes=1)
        third = sign_in(app)
        frozen_clock.advance(minutes=10)
        assert authenticated(second)               # moves second's last_seen_at
        ids = [r.rbses_id for r in rows()]

        listed = items(first)                      # third was used last at 12:02
        assert [i['id'] for i in listed] == [ids[0], ids[1], ids[2]]
        assert [i['current'] for i in listed] == [True, False, False]
        assert listed[1]['device'] == 'Safari on iOS'
        assert listed[1]['last_seen_at'] == '2030-01-01T12:12:00Z'
        assert listed[2]['last_seen_at'] == '2030-01-01T12:02:00Z'
        assert [i['current'] for i in items(third)] == [True, False, False]
        assert items(third)[0]['id'] == ids[2]

    def test_only_the_callers_active_sessions(self, app, ana, make_user, frozen_clock):
        make_user('bo')
        client = sign_in(app)
        sign_in(app, username='bo')
        revoked, idle, expired, kept = (sign_in(app), sign_in(app), sign_in(app, remember=True),
                                        sign_in(app, remember=True))
        assert all(authenticated(c) for c in (revoked, idle, expired, kept))
        ids = [r.rbses_id for r in rows()]
        when = frozen_clock.now
        for row in rows():
            if row.rbses_id == ids[2]:
                row.rbses_revoked_at = when
            elif row.rbses_id == ids[3]:
                row.rbses_last_seen_at = when - timedelta(hours=12)
            elif row.rbses_id == ids[4]:
                row.rbses_expires_at = when
        db.session.commit()
        assert [i['id'] for i in items(client)] == [ids[0], ids[5]]

    def test_at_most_three_statements(self, app, ana, frozen_clock):
        client = sign_in(app)
        for _ in range(3):
            sign_in(app)
        db.session.expire_all()
        seen = []

        def record(conn, cursor, statement, parameters, context, executemany):
            seen.append(statement)

        event.listen(db.engine, 'before_cursor_execute', record)
        try:
            assert len(items(client)) == 4
        finally:
            event.remove(db.engine, 'before_cursor_execute', record)
        assert len(seen) <= 3, seen

    def test_anonymous_is_401(self, client):
        response = client.get(SESSIONS)
        assert (response.status_code, response.get_json()['code']) == (401, 'unauthenticated')


# --- DELETE /me/sessions/<id> (S11) ---------------------------------------------------------

class TestRevokeOne:
    def test_another_session_of_the_caller(self, app, ana, frozen_clock):
        here, there = sign_in(app), sign_in(app, remember=True)
        there_id = rows()[1].rbses_id
        response = here.delete(f'{SESSIONS}/{there_id}')
        assert response.status_code == 200
        assert response.get_json()['data'] == {'revoked': 1, 'current': False}
        assert authenticated(here)
        assert not authenticated(there)
        there.delete_cookie('session')
        assert not authenticated(there)            # the remember cookie is dead too
        assert [r.rbses_revoked_at is None for r in rows()] == [True, False]

    def test_the_current_session_logs_the_caller_out(self, app, ana, frozen_clock):
        here, there = sign_in(app, remember=True), sign_in(app)
        here_id = rows()[0].rbses_id
        response = here.delete(f'{SESSIONS}/{here_id}')
        assert response.status_code == 200
        assert response.get_json()['data'] == {'revoked': 1, 'current': True}
        [expired] = set_cookies(response, 'remember_token')
        assert 'Expires=Thu, 01 Jan 1970' in expired
        assert not authenticated(here)
        assert authenticated(there)

    @pytest.mark.parametrize('case', ['other_user', 'unknown', 'revoked', 'expired'])
    def test_not_an_active_session_of_the_caller_is_404(self, app, ana, make_user,
                                                        frozen_clock, case):
        make_user('bo')
        here = sign_in(app)
        other = sign_in(app, username='bo') if case == 'other_user' else sign_in(app)
        target = rows()[1]
        if case == 'revoked':
            target.rbses_revoked_at = frozen_clock.now
        elif case == 'expired':
            target.rbses_last_seen_at = frozen_clock.now - timedelta(hours=13)
        db.session.commit()
        before = [(r.rbses_id, r.rbses_revoked_at) for r in rows()]
        target_id = 999 if case == 'unknown' else target.rbses_id
        response = here.delete(f'{SESSIONS}/{target_id}')
        assert response.status_code == 404
        assert {k: response.get_json()[k] for k in NOT_FOUND} == NOT_FOUND
        assert [(r.rbses_id, r.rbses_revoked_at) for r in rows()] == before
        assert authenticated(here)
        if case == 'other_user':
            assert authenticated(other)


# --- DELETE /me/sessions (S12) --------------------------------------------------------------

class TestRevokeOthers:
    def test_every_other_session_of_the_caller(self, app, ana, make_user, frozen_clock):
        make_user('bo')
        here = sign_in(app)
        others = [sign_in(app), sign_in(app, remember=True)]
        bo = sign_in(app, username='bo')
        response = here.delete(SESSIONS)
        assert response.status_code == 200
        assert response.get_json()['data'] == {'revoked': 2}
        assert authenticated(here) and authenticated(bo)
        assert not any(authenticated(c) for c in others)
        assert [i['current'] for i in items(here)] == [True]

    def test_nothing_to_revoke_is_zero(self, app, ana, frozen_clock):
        here = sign_in(app)
        assert here.delete(SESSIONS).get_json()['data'] == {'revoked': 0}
        assert authenticated(here)
