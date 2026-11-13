"""F9-b S9-S11 (AC5): re-authentication. The `reauth_required` rule (10 minutes after the
current session's `reauth_at`) and POST /me/reauth (password now, a TOTP code from F9-d)."""
from datetime import timedelta

import pytest
import sqlalchemy as sa
from flask_login import login_required

from app import db
from app.api.responses import ok
from app.models import RbSession, User
from app.security import REAUTH_WINDOW, reauth_required
from tests.conftest import DEFAULT_PASSWORD, login_as

API = '/riftbound/api/v1'
REAUTH = f'{API}/me/reauth'
PROBE = '/riftbound/api/v1/test-only/reauth-probe'
FORBIDDEN = {'success': False, 'error': 'Forbidden',
             'message': 'Confirm your identity to continue', 'code': 'reauth_required'}


@pytest.fixture
def probe(app):
    """A test-only route guarded by `reauth_required`, added before the first request."""
    @login_required
    @reauth_required
    def reauth_probe():
        return ok({'passed': True})

    app.add_url_rule(PROBE, 'reauth_probe', reauth_probe, methods=['POST'])
    return PROBE


@pytest.fixture
def ana(app, probe, make_user, frozen_clock):
    """`ana` signed in at the frozen time (2030-01-01 12:00 UTC)."""
    make_user('ana')
    return login_as(app.test_client(), 'ana')


def session_rows(username='ana'):
    db.session.expire_all()
    return db.session.execute(
        sa.select(RbSession).join(User, User.id == RbSession.rbses_user_id)
        .where(User.username == username).order_by(RbSession.rbses_id)).scalars().all()


def stored(username='ana'):
    db.session.expire_all()
    return User.query.filter_by(username=username).one()


def remove_password(username='ana'):
    user = stored(username)
    user.password_hash = None
    db.session.commit()


def details(response):
    assert response.status_code == 400, response.get_json()
    body = response.get_json()
    assert body['code'] == 'validation_error'
    return [{k: d.get(k) for k in ('field', 'code', 'message')} for d in body['details']]


# --- The rule (S9) --------------------------------------------------------------------------

class TestTheRule:
    def test_the_window_is_ten_minutes(self):
        assert REAUTH_WINDOW == timedelta(minutes=10)

    def test_a_fresh_sign_in_passes(self, ana):
        response = ana.post(PROBE)
        assert (response.status_code, response.get_json()['data']) == (200, {'passed': True})

    def test_9_59_passes_and_10_01_is_403_with_the_methods(self, ana, frozen_clock):
        frozen_clock.advance(minutes=9, seconds=59)
        assert ana.post(PROBE).status_code == 200
        frozen_clock.advance(seconds=62)
        response = ana.post(PROBE)
        assert response.status_code == 403
        assert response.get_json() == {**FORBIDDEN, 'params': {'methods': ['password']}}

    def test_an_account_without_a_password_has_no_method_yet(self, ana, frozen_clock):
        remove_password()
        frozen_clock.advance(minutes=11)
        assert ana.post(PROBE).get_json() == {**FORBIDDEN, 'params': {'methods': []}}

    def test_re_authenticating_opens_the_window_again(self, ana, frozen_clock):
        frozen_clock.advance(minutes=30)
        assert ana.post(PROBE).status_code == 403
        assert ana.post(REAUTH, json={'password': DEFAULT_PASSWORD}).status_code == 200
        frozen_clock.advance(minutes=9)
        assert ana.post(PROBE).status_code == 200

    def test_only_the_current_session_counts(self, app, ana, frozen_clock):
        other = login_as(app.test_client(), 'ana')
        frozen_clock.advance(minutes=30)
        assert ana.post(REAUTH, json={'password': DEFAULT_PASSWORD}).status_code == 200
        assert ana.post(PROBE).status_code == 200
        assert other.post(PROBE).status_code == 403

    def test_anonymous_callers_get_401_first(self, app, probe, client):
        response = client.post(PROBE)
        assert (response.status_code, response.get_json()['code']) == (401, 'unauthenticated')


# --- POST /me/reauth (S11) ------------------------------------------------------------------

class TestReauth:
    def test_the_password_marks_only_the_current_session(self, app, ana, frozen_clock):
        login_as(app.test_client(), 'ana')
        frozen_clock.advance(minutes=30)
        response = ana.post(REAUTH, json={'password': DEFAULT_PASSWORD})
        assert response.status_code == 200
        assert response.get_json() == {'success': True,
                                       'data': {'reauth_until': '2030-01-01T12:40:00Z'}}
        mine, other = session_rows()
        assert mine.rbses_reauth_at == frozen_clock.now
        assert other.rbses_reauth_at == frozen_clock.now - timedelta(minutes=30)
        assert ana.get(f'{API}/me').get_json()['data']['security']['reauth_until'] == \
            '2030-01-01T12:40:00Z'

    def test_a_wrong_password_writes_nothing_and_counts_no_failure(self, ana, frozen_clock):
        frozen_clock.advance(minutes=30)
        for _ in range(6):
            response = ana.post(REAUTH, json={'password': 'not-it'})
            assert response.status_code == 400
            body = response.get_json()
            assert (body['code'], body['message']) == ('current_password_incorrect',
                                                       'The current password is incorrect')
        [row] = session_rows()
        assert row.rbses_reauth_at == frozen_clock.now - timedelta(minutes=30)
        user = stored()
        assert (user.failed_login_count, user.locked_until) == (0, None)
        assert ana.post(PROBE).status_code == 403

    def test_a_password_on_an_account_without_one_is_a_validation_error(self, ana,
                                                                       frozen_clock):
        remove_password()
        frozen_clock.advance(minutes=30)
        assert details(ana.post(REAUTH, json={'password': DEFAULT_PASSWORD})) == [
            {'field': 'password', 'code': 'invalid_value',
             'message': 'This account has no password'}]
        assert session_rows()[0].rbses_reauth_at == frozen_clock.now - timedelta(minutes=30)

    def test_a_code_before_two_factor_exists(self, ana, frozen_clock):
        frozen_clock.advance(minutes=30)
        assert details(ana.post(REAUTH, json={'code': '123456'})) == [
            {'field': 'code', 'code': 'invalid_value',
             'message': 'Two-factor authentication is not enabled'}]
        assert ana.post(PROBE).status_code == 403

    @pytest.mark.parametrize('body', [{}, {'password': DEFAULT_PASSWORD, 'code': '123456'},
                                      {'password': None, 'code': None}])
    def test_both_or_neither_is_a_validation_error(self, ana, frozen_clock, body):
        frozen_clock.advance(minutes=30)
        response = ana.post(REAUTH, json=body)
        assert response.status_code == 400
        assert response.get_json()['code'] == 'validation_error'
        assert ana.post(PROBE).status_code == 403

    def test_password_length_bounds(self, ana):
        assert details(ana.post(REAUTH, json={'password': ''}))[0]['code'] == 'too_short'
        assert details(ana.post(REAUTH, json={'password': 'x' * 1025}))[0]['code'] == 'too_long'
        assert ana.post(REAUTH, json={'password': 'x' * 1024}).get_json()['code'] == \
            'current_password_incorrect'

    def test_twenty_per_hour_per_ip(self, limited_app, ana):
        codes = [ana.post(REAUTH, json={'password': 'not-it'}).status_code for _ in range(20)]
        assert codes == [400] * 20
        response = ana.post(REAUTH, json={'password': DEFAULT_PASSWORD})
        assert response.status_code == 429
        assert int(response.headers['Retry-After']) > 0
        assert response.get_json()['code'] == 'rate_limited'

    def test_the_login_still_works_after_wrong_reauths(self, app, ana):
        for _ in range(6):
            ana.post(REAUTH, json={'password': 'not-it'})
        assert login_as(app.test_client(), 'ana')

    def test_anonymous_is_401(self, client):
        response = client.post(REAUTH, json={'password': DEFAULT_PASSWORD})
        assert (response.status_code, response.get_json()['code']) == (401, 'unauthenticated')
