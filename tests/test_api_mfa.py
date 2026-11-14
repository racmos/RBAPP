"""F9-d S7-S12, S14 (AC3): POST /me/2fa/setup, /enable, /disable, /recovery-codes and the
`security.mfa` summary of GET /me."""
import logging
import re
from datetime import timezone
from urllib.parse import unquote

import pyotp
import pytest
import sqlalchemy as sa
from cryptography.fernet import Fernet

from app import db
from app.models import RbRecoveryCode, RbSession, RbUserMfa, User
from tests.auth_helpers import sign_in_2fa
from tests.conftest import login_as

API = '/riftbound/api/v1'
ME = f'{API}/me'
SETUP = f'{API}/me/2fa/setup'
ENABLE = f'{API}/me/2fa/enable'
DISABLE = f'{API}/me/2fa/disable'
CODES = f'{API}/me/2fa/recovery-codes'
SESSION = f'{API}/auth/session'
ROUTES = (SETUP, ENABLE, DISABLE, CODES)
INVALID = {'success': False, 'error': 'Bad Request', 'message': 'The code is not valid',
           'code': 'mfa_invalid'}
UNAVAILABLE = {'success': False, 'error': 'Service Unavailable',
               'message': 'Two-factor authentication is not available'}
RECOVERY = re.compile(r'^[abcdefghjkmnpqrstuvwxyz23456789]{5}-[abcdefghjkmnpqrstuvwxyz23456789]{5}$')


def now_code(frozen_clock, secret, offset=0):
    """The code an authenticator app shows `offset` steps from the frozen time."""
    totp = pyotp.TOTP(secret)
    return totp.generate_otp(totp.timecode(frozen_clock.now.replace(tzinfo=timezone.utc))
                             + offset)


def user_id(name='ana'):
    return User.query.filter_by(username=name).one().id


def mfa_row(name='ana'):
    db.session.expire_all()
    return db.session.get(RbUserMfa, user_id(name))


def code_rows(name='ana'):
    db.session.expire_all()
    return db.session.execute(sa.select(RbRecoveryCode).where(
        RbRecoveryCode.rbrco_user_id == user_id(name))).scalars().all()


def sessions_of(name='ana'):
    db.session.expire_all()
    return db.session.execute(sa.select(RbSession).where(
        RbSession.rbses_user_id == user_id(name)).order_by(RbSession.rbses_id)).scalars().all()


def signed_in(client):
    return client.get(SESSION).get_json()['data']['authenticated']


def security(client):
    return client.get(ME).get_json()['data']['security']


@pytest.fixture
def ana(app, make_user, frozen_clock):
    """`ana` signed in at the frozen time (re-authenticated by the sign-in)."""
    make_user('ana')
    return login_as(app.test_client(), 'ana')


@pytest.fixture
def other(app, ana):
    """A second session of `ana` on another client."""
    return login_as(app.test_client(), 'ana')


def setup(client):
    response = client.post(SETUP)
    assert response.status_code == 200, response.get_json()
    return response.get_json()['data']['secret'].replace(' ', '')


@pytest.fixture
def pending(ana):
    """`ana` with a pending setup; returns the clear secret."""
    return setup(ana)


@pytest.fixture
def enabled(ana, pending, frozen_clock):
    """`ana` with 2FA on; returns (secret, recovery codes). The clock moves one step on, so the
    next code is not a replay."""
    response = ana.post(ENABLE, json={'code': now_code(frozen_clock, pending)})
    assert response.status_code == 200, response.get_json()
    frozen_clock.advance(seconds=30)
    return pending, response.get_json()['data']['recovery_codes']


# --- Setup (S7) ------------------------------------------------------------------------------

class TestSetup:
    def test_the_answer(self, ana):
        response = ana.post(SETUP)
        assert response.status_code == 200
        assert response.headers['Cache-Control'] == 'no-store'
        data = response.get_json()['data']
        assert set(data) == {'secret', 'otpauth_uri', 'qr'}
        assert re.fullmatch(r'([A-Z2-7]{4} ){7}[A-Z2-7]{4}', data['secret'])
        clear = data['secret'].replace(' ', '')
        assert data['otpauth_uri'] == (
            f'otpauth://totp/Rift%20Manager:ana?secret={clear}&issuer=Rift%20Manager')
        assert data['qr'].startswith('data:image/svg+xml')
        assert '<svg' in unquote(data['qr'])

    def test_it_creates_a_pending_row(self, ana, frozen_clock):
        setup(ana)
        row = mfa_row()
        assert (row.rbmfa_enabled_at, row.rbmfa_last_step, row.rbmfa_created_at) == (
            None, None, frozen_clock.now)
        assert security(ana)['mfa'] == {'available': True, 'enabled': False, 'pending': True,
                                        'recovery_codes_left': 0}

    def test_a_second_setup_replaces_the_secret(self, ana):
        first, second = setup(ana), setup(ana)
        assert first != second
        assert db.session.execute(sa.select(sa.func.count()).select_from(RbUserMfa)).scalar() == 1

    def test_already_on_is_409(self, ana, enabled):
        before = mfa_row().rbmfa_secret_enc
        response = ana.post(SETUP)
        assert response.status_code == 409
        assert response.get_json() == {
            'success': False, 'error': 'Conflict', 'code': 'already_exists',
            'message': 'Two-factor authentication is already on'}
        assert mfa_row().rbmfa_secret_enc == before

    def test_the_secret_is_never_shown_again_nor_logged(self, ana, frozen_clock, caplog):
        with caplog.at_level(logging.DEBUG):
            secret = setup(ana)
            response = ana.post(ENABLE, json={'code': now_code(frozen_clock, secret)})
            assert response.status_code == 200
            assert secret not in response.get_data(as_text=True)
            assert secret not in ana.get(ME).get_data(as_text=True)
            assert secret not in ana.get(SESSION).get_data(as_text=True)
        assert secret not in caplog.text


# --- Enable (S8) -----------------------------------------------------------------------------

class TestEnable:
    def test_success(self, ana, other, pending, frozen_clock):
        response = ana.post(ENABLE, json={'code': now_code(frozen_clock, pending)})
        assert response.status_code == 200
        assert response.headers['Cache-Control'] == 'no-store'
        data = response.get_json()['data']
        assert data['revoked_sessions'] == 1
        assert len(data['recovery_codes']) == 10
        assert all(RECOVERY.match(c) for c in data['recovery_codes'])
        row = mfa_row()
        assert row.rbmfa_enabled_at == frozen_clock.now
        assert row.rbmfa_last_step is not None
        assert len(code_rows()) == 10
        mine, theirs = sessions_of()
        assert (mine.rbses_mfa, mine.rbses_revoked_at) == (True, None)
        assert theirs.rbses_revoked_at == frozen_clock.now
        assert signed_in(ana) and not signed_in(other)
        assert security(ana)['mfa'] == {'available': True, 'enabled': True, 'pending': False,
                                        'recovery_codes_left': 10}

    def test_without_a_setup_is_404(self, ana):
        response = ana.post(ENABLE, json={'code': '123456'})
        assert response.status_code == 404
        body = response.get_json()
        assert (body['success'], body['error']) == (False, 'Not Found')
        assert 'code' not in body

    def test_already_on_is_409(self, ana, enabled, frozen_clock):
        response = ana.post(ENABLE, json={'code': now_code(frozen_clock, enabled[0])})
        assert response.status_code == 409
        assert response.get_json()['code'] == 'already_exists'

    @pytest.mark.parametrize('wrong', ['000000', 'abcdef', '12345'])
    def test_a_wrong_code_changes_nothing(self, ana, other, pending, frozen_clock, wrong):
        if wrong == '000000' and now_code(frozen_clock, pending) == wrong:
            wrong = '111111'
        response = ana.post(ENABLE, json={'code': wrong})
        assert (response.status_code, response.get_json()) == (400, INVALID)
        row = mfa_row()
        assert (row.rbmfa_enabled_at, row.rbmfa_last_step) == (None, None)
        assert code_rows() == []
        assert signed_in(other)
        assert [s.rbses_mfa for s in sessions_of()] == [False, False]

    def test_a_code_two_steps_away_is_refused(self, ana, pending, frozen_clock):
        response = ana.post(ENABLE, json={'code': now_code(frozen_clock, pending, offset=2)})
        assert (response.status_code, response.get_json()) == (400, INVALID)

    @pytest.mark.parametrize('body, field_code', [({}, 'required'), ({'code': ''}, 'too_short'),
                                                  ({'code': 'x' * 33}, 'too_long')])
    def test_the_body_is_validated(self, ana, pending, body, field_code):
        response = ana.post(ENABLE, json=body)
        assert response.status_code == 400
        assert response.get_json()['code'] == 'validation_error'
        assert response.get_json()['details'][0]['code'] == field_code


# --- Disable (S9) ----------------------------------------------------------------------------

class TestDisable:
    def test_with_a_totp_code(self, ana, enabled, frozen_clock, app):
        other = sign_in_2fa(app.test_client(), 'ana', enabled[0], frozen_clock)   # F9-e
        response = ana.post(DISABLE, json={'code': now_code(frozen_clock, enabled[0])})
        assert (response.status_code, response.get_json()['data']) == (
            200, {'revoked_sessions': 1})
        assert mfa_row() is None and code_rows() == []
        assert signed_in(ana) and not signed_in(other)
        assert security(ana)['mfa'] == {'available': True, 'enabled': False, 'pending': False,
                                        'recovery_codes_left': 0}

    def test_with_a_recovery_code_in_any_case_and_spacing(self, ana, enabled):
        given = enabled[1][4].upper().replace('-', ' ')
        response = ana.post(DISABLE, json={'code': given})
        assert response.status_code == 200
        assert mfa_row() is None

    def test_the_enabling_code_cannot_be_replayed(self, ana, pending, frozen_clock):
        used = now_code(frozen_clock, pending)
        assert ana.post(ENABLE, json={'code': used}).status_code == 200
        response = ana.post(DISABLE, json={'code': used})
        assert (response.status_code, response.get_json()) == (400, INVALID)
        assert mfa_row() is not None

    def test_a_wrong_code_changes_nothing(self, ana, enabled, app, frozen_clock):
        other = sign_in_2fa(app.test_client(), 'ana', enabled[0], frozen_clock)   # F9-e
        response = ana.post(DISABLE, json={'code': 'zzzzz-zzzzz'})
        assert (response.status_code, response.get_json()) == (400, INVALID)
        assert mfa_row().rbmfa_enabled_at is not None
        assert len(code_rows()) == 10
        assert signed_in(other)

    def test_a_used_recovery_code_is_refused(self, ana, enabled, frozen_clock):
        first = enabled[1][0]
        assert ana.post(DISABLE, json={'code': first}).status_code == 200
        assert ana.post(ENABLE, json={'code': '123456'}).status_code == 404
        # 2FA on again with new codes: the old one never works again.
        secret = setup(ana)
        assert ana.post(ENABLE, json={'code': now_code(frozen_clock, secret)}).status_code == 200
        assert ana.post(DISABLE, json={'code': first}).get_json() == INVALID

    @pytest.mark.parametrize('state', ['off', 'pending'])
    def test_not_on_is_404(self, ana, state):
        if state == 'pending':
            setup(ana)
        response = ana.post(DISABLE, json={'code': '123456'})
        assert (response.status_code, response.get_json()['error']) == (404, 'Not Found')


# --- Recovery codes (S10) --------------------------------------------------------------------

class TestRegenerate:
    def test_new_codes_replace_the_old_ones(self, ana, enabled, app, frozen_clock):
        other = sign_in_2fa(app.test_client(), 'ana', enabled[0], frozen_clock)   # F9-e
        response = ana.post(CODES)
        assert response.status_code == 200
        assert response.headers['Cache-Control'] == 'no-store'
        data = response.get_json()['data']
        assert data['revoked_sessions'] == 1
        assert len(data['recovery_codes']) == 10
        assert not set(data['recovery_codes']) & set(enabled[1])
        assert len(code_rows()) == 10
        assert not signed_in(other)
        assert ana.post(DISABLE, json={'code': enabled[1][0]}).get_json() == INVALID
        assert ana.post(DISABLE, json={'code': data['recovery_codes'][0]}).status_code == 200

    @pytest.mark.parametrize('state', ['off', 'pending'])
    def test_not_on_is_404(self, ana, state):
        if state == 'pending':
            setup(ana)
        assert ana.post(CODES).status_code == 404
        assert code_rows() == []


# --- Re-authentication, rate limit, availability (S7-S12) ------------------------------------

class TestGuards:
    @pytest.mark.parametrize('route', ROUTES)
    def test_a_stale_reauth_is_403_and_nothing_applies(self, ana, enabled, frozen_clock, route,
                                                      app):
        other = sign_in_2fa(app.test_client(), 'ana', enabled[0], frozen_clock)   # F9-e
        frozen_clock.advance(minutes=11)
        before = (mfa_row().rbmfa_secret_enc, sorted(r.rbrco_code_hash for r in code_rows()))
        body = {'code': now_code(frozen_clock, enabled[0])} if route in (ENABLE, DISABLE) else None
        response = ana.post(route, json=body)
        assert response.status_code == 403
        assert response.get_json() == {
            'success': False, 'error': 'Forbidden', 'code': 'reauth_required',
            'message': 'Confirm your identity to continue',
            'params': {'methods': ['password', 'totp']}}
        assert (mfa_row().rbmfa_secret_enc, sorted(r.rbrco_code_hash for r in code_rows())) == \
            before
        assert signed_in(other)

    def test_a_stale_reauth_blocks_setup_too(self, ana, frozen_clock):
        frozen_clock.advance(minutes=11)
        response = ana.post(SETUP)
        assert response.status_code == 403
        assert response.get_json()['params'] == {'methods': ['password']}
        assert mfa_row() is None

    @pytest.mark.parametrize('route', ROUTES)
    def test_anonymous_is_401(self, client, route):
        response = client.post(route, json={'code': '123456'})
        assert (response.status_code, response.get_json()['code']) == (401, 'unauthenticated')

    def test_the_four_routes_share_twenty_per_hour(self, limited_app, ana):
        statuses = []
        for n in range(20):
            route = ROUTES[n % 4]
            statuses.append(ana.post(route, json={'code': '000000'}).status_code)
        assert 429 not in statuses
        response = ana.post(DISABLE, json={'code': '000000'})
        assert response.status_code == 429
        assert response.get_json()['code'] == 'rate_limited'
        assert int(response.headers['Retry-After']) > 0

    def test_wrong_codes_never_count_as_login_failures(self, app, ana, enabled, frozen_clock):
        for _ in range(8):
            assert ana.post(DISABLE, json={'code': '000000'}).status_code == 400
        user = User.query.filter_by(username='ana').one()
        db.session.refresh(user)
        assert (user.failed_login_count, user.locked_until) == (0, None)
        assert signed_in(sign_in_2fa(app.test_client(), 'ana', enabled[0], frozen_clock))

    @pytest.mark.parametrize('route', ROUTES)
    def test_without_a_key_every_route_is_503(self, app, ana, route):
        app.config['TOTP_ENCRYPTION_KEY'] = None
        response = ana.post(route, json={'code': '123456'})
        assert (response.status_code, response.get_json()) == (503, UNAVAILABLE)
        assert mfa_row() is None

    def test_without_a_key_get_me_says_unavailable(self, app, ana):
        app.config['TOTP_ENCRYPTION_KEY'] = None
        assert security(ana)['mfa'] == {'available': False, 'enabled': False, 'pending': False,
                                        'recovery_codes_left': 0}

    @pytest.mark.parametrize('route', [ENABLE, DISABLE])
    def test_an_undecryptable_secret_is_503_and_logged_without_it(self, app, ana, enabled,
                                                                  frozen_clock, route, caplog):
        secret = enabled[0]
        if route == ENABLE:
            db.session.execute(sa.delete(RbUserMfa))
            db.session.commit()
            secret = setup(ana)
        app.config['TOTP_ENCRYPTION_KEY'] = Fernet.generate_key().decode()
        with caplog.at_level(logging.DEBUG):
            response = ana.post(route, json={'code': now_code(frozen_clock, secret)})
        assert (response.status_code, response.get_json()) == (503, UNAVAILABLE)
        assert 'cannot be decrypted' in caplog.text
        assert secret not in caplog.text
        assert mfa_row() is not None


# --- GET /me (S14) ---------------------------------------------------------------------------

class TestSummary:
    def test_recovery_codes_left_counts_unused_codes(self, ana, enabled, frozen_clock):
        assert ana.post(DISABLE, json={'code': 'zzzzz-zzzzz'}).status_code == 400
        assert security(ana)['mfa']['recovery_codes_left'] == 10
        code_rows()[0].rbrco_used_at = frozen_clock.now
        db.session.commit()
        assert security(ana)['mfa']['recovery_codes_left'] == 9

    def test_another_users_2fa_is_not_mine(self, app, ana, enabled, make_user):
        make_user('bo')
        bo = login_as(app.test_client(), 'bo')
        assert security(bo)['mfa'] == {'available': True, 'enabled': False, 'pending': False,
                                       'recovery_codes_left': 0}

    def test_get_me_stays_within_five_statements_with_2fa_on(self, ana, enabled):
        from sqlalchemy import event
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
