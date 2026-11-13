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


# --- POST /me/reauth with a TOTP code (F9-d S13) ----------------------------------------------

def _totp_code(frozen_clock, secret, offset=0):
    import pyotp
    from datetime import timezone
    totp = pyotp.TOTP(secret)
    return totp.generate_otp(totp.timecode(frozen_clock.now.replace(tzinfo=timezone.utc))
                             + offset)


@pytest.fixture
def ana_2fa(ana, frozen_clock):
    """`ana` with 2FA on; returns (secret, recovery codes). The clock then moves past the
    window, so the session needs a re-authentication and the next code is new."""
    secret = ana.post(f'{API}/me/2fa/setup').get_json()['data']['secret'].replace(' ', '')
    response = ana.post(f'{API}/me/2fa/enable', json={'code': _totp_code(frozen_clock, secret)})
    assert response.status_code == 200, response.get_json()
    frozen_clock.advance(minutes=30)
    return secret, response.get_json()['data']['recovery_codes']


MFA_INVALID = {'success': False, 'error': 'Bad Request', 'message': 'The code is not valid',
               'code': 'mfa_invalid'}


class TestReauthWithTotp:
    def test_a_current_code_re_authenticates(self, ana, ana_2fa, frozen_clock):
        assert ana.post(PROBE).status_code == 403
        response = ana.post(REAUTH, json={'code': _totp_code(frozen_clock, ana_2fa[0])})
        assert response.get_json() == {'success': True,
                                       'data': {'reauth_until': '2030-01-01T12:40:00Z'}}
        assert ana.post(PROBE).status_code == 200

    def test_an_adjacent_code_is_accepted_with_spaces(self, ana, ana_2fa, frozen_clock):
        given = _totp_code(frozen_clock, ana_2fa[0], offset=-1)
        response = ana.post(REAUTH, json={'code': f'{given[:3]} {given[3:]}'})
        assert response.status_code == 200

    def test_a_replayed_code_is_refused(self, ana, ana_2fa, frozen_clock):
        given = _totp_code(frozen_clock, ana_2fa[0])
        assert ana.post(REAUTH, json={'code': given}).status_code == 200
        frozen_clock.advance(minutes=11)
        response = ana.post(REAUTH, json={'code': given})
        assert (response.status_code, response.get_json()) == (400, MFA_INVALID)
        assert ana.post(PROBE).status_code == 403

    def test_a_recovery_code_is_refused_and_not_spent(self, ana, ana_2fa):
        response = ana.post(REAUTH, json={'code': ana_2fa[1][0]})
        assert (response.status_code, response.get_json()) == (400, MFA_INVALID)
        assert ana.post(PROBE).status_code == 403
        assert ana.get(f'{API}/me').get_json()['data']['security']['mfa'][
            'recovery_codes_left'] == 10

    def test_a_wrong_code_counts_no_login_failure(self, ana, ana_2fa):
        for _ in range(6):
            assert ana.post(REAUTH, json={'code': '000000'}).get_json()['code'] in (
                'mfa_invalid',)
        user = stored()
        assert (user.failed_login_count, user.locked_until) == (0, None)

    def test_the_password_still_works(self, ana, ana_2fa):
        assert ana.post(REAUTH, json={'password': DEFAULT_PASSWORD}).status_code == 200

    def test_methods_list_totp_when_it_is_on(self, ana, ana_2fa):
        assert ana.post(PROBE).get_json()['params'] == {'methods': ['password', 'totp']}
        remove_password()
        assert ana.post(PROBE).get_json()['params'] == {'methods': ['totp']}

    def test_a_pending_setup_is_not_on(self, ana, frozen_clock):
        secret = ana.post(f'{API}/me/2fa/setup').get_json()['data']['secret'].replace(' ', '')
        frozen_clock.advance(minutes=30)
        assert ana.post(PROBE).get_json()['params'] == {'methods': ['password']}
        assert details(ana.post(REAUTH, json={'code': _totp_code(frozen_clock, secret)})) == [
            {'field': 'code', 'code': 'invalid_value',
             'message': 'Two-factor authentication is not enabled'}]

    def test_an_undecryptable_secret_is_503_and_nothing_is_marked(self, app, ana, ana_2fa,
                                                                 frozen_clock, caplog):
        from cryptography.fernet import Fernet
        app.config['TOTP_ENCRYPTION_KEY'] = Fernet.generate_key().decode()
        response = ana.post(REAUTH, json={'code': _totp_code(frozen_clock, ana_2fa[0])})
        assert (response.status_code, response.get_json()) == (503, {
            'success': False, 'error': 'Service Unavailable',
            'message': 'Two-factor authentication is not available'})
        assert ana_2fa[0] not in caplog.text
        assert ana.post(PROBE).status_code == 403
