"""Small helpers for tests that deal with CSRF tokens and cookies (unit d).

The CSRF token comes from GET /auth/session (`tests.conftest.api_csrf_token`): the
Jinja pages that carried it in a meta tag or a form field are gone.
"""


def token_payload(token):
    """The session secret inside a signed CSRF token. Flask-WTF signs it with a
    timestamp, so two renders a second apart differ as strings but carry the
    same payload."""
    return token.rsplit('.', 2)[0]


# --- Two-factor sign-in (F9-e) -------------------------------------------------------------

LOGIN_URL = '/riftbound/api/v1/auth/login'
MFA_URL = '/riftbound/api/v1/auth/mfa'


def totp_code(secret, now, offset=0):
    """The code an authenticator app shows `offset` steps from `now` (naive UTC)."""
    from datetime import timezone

    import pyotp
    totp = pyotp.TOTP(secret)
    return totp.generate_otp(totp.timecode(now.replace(tzinfo=timezone.utc)) + offset)


def turn_on_2fa(user, frozen_clock):
    """Turn 2FA on for `user` through the service (no request, no re-auth); returns
    `(secret, recovery codes)`. The clock then moves one step on, so the next code is new."""
    from app.services import mfa
    secret = mfa.setup(user)['secret'].replace(' ', '')
    status, codes, _ = mfa.enable(user, totp_code(secret, frozen_clock.now),
                                  keep_session_id=None)
    assert status is mfa.MfaStatus.OK
    frozen_clock.advance(seconds=30)
    return secret, codes


def sign_in_2fa(client, username, secret, frozen_clock, password=None, remember=False,
                headers=None):
    """Sign a 2FA user in through both steps (password, then the current TOTP code); the clock
    then moves one step on so the next code is not a replay. Returns `client`."""
    from tests.conftest import DEFAULT_PASSWORD
    headers = headers or {}
    first = client.post(LOGIN_URL, json={'username': username,
                                         'password': password or DEFAULT_PASSWORD,
                                         'remember': remember}, headers=headers)
    assert first.get_json()['data'] == {'mfa_required': True, 'methods': ['totp', 'recovery']}
    second = client.post(MFA_URL, json={'code': totp_code(secret, frozen_clock.now)},
                         headers=headers)
    assert second.status_code == 200, second.get_json()
    frozen_clock.advance(seconds=30)
    return client
