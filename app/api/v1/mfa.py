"""TOTP two-factor authentication of the signed-in user (F9-d S7-S12): POST /me/2fa/setup,
/me/2fa/enable, /me/2fa/disable and /me/2fa/recovery-codes.

Every route needs a recent re-authentication of the current session (`reauth_required`),
shares one limit of 20/hour per IP (scope `mfa_manage`) and answers 503 while 2FA is
unavailable (no usable `TOTP_ENCRYPTION_KEY`, or a stored secret the key cannot decrypt).
Answers that carry a secret or recovery codes are `Cache-Control: no-store`. A wrong code is a
400 `mfa_invalid` (never a 401: the SPA would treat the user as signed out, S16) and never
counts as a login failure. Logic in `app/services/mfa.py`.
"""
from functools import wraps

from flask import request
from flask_login import current_user, login_required

from app import db, limiter
from app.api.error_codes import ErrorCode
from app.api.responses import fail, ok
from app.api.v1 import api_v1
from app.schemas.validation import validate_json
from app.schemas.validators import MfaCode
from app.security import reauth_required
from app.services import mfa, sessions
from app.services.mfa import MfaStatus


def _unavailable():
    return fail('Service Unavailable', mfa.NOT_AVAILABLE, 503)


def _requires_mfa(view):
    """503 before anything else while 2FA is unavailable, and when a secret cannot be
    decrypted half-way (S11; nothing of the request is kept)."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not mfa.available():
            return _unavailable()
        try:
            return view(*args, **kwargs)
        except mfa.MfaUnavailable:
            db.session.rollback()
            return _unavailable()
    return wrapper


def _no_store(response):
    response.headers['Cache-Control'] = 'no-store'
    return response


def _invalid():
    return fail('Bad Request', mfa.CODE_INVALID, 400, code=ErrorCode.MFA_INVALID)


def _already_on():
    return fail('Conflict', mfa.ALREADY_ON, 409, code=ErrorCode.ALREADY_EXISTS)


@api_v1.post('/me/2fa/setup')
@login_required
@limiter.shared_limit(mfa.MFA_RATE_LIMIT, scope='mfa_manage')
@_requires_mfa
@reauth_required
def mfa_setup():
    """S7: a new pending secret → `{secret, otpauth_uri, qr}`; 409 when 2FA is already on."""
    try:
        payload = mfa.setup(current_user)
    except mfa.AlreadyEnabled:
        return _already_on()
    return _no_store(ok(payload))


@api_v1.post('/me/2fa/enable')
@login_required
@limiter.shared_limit(mfa.MFA_RATE_LIMIT, scope='mfa_manage')
@_requires_mfa
@validate_json(MfaCode)
@reauth_required
def mfa_enable():
    """S8: confirm the pending setup with a code → `{recovery_codes, revoked_sessions}`."""
    status, codes, revoked = mfa.enable(current_user, request.validated_data.code,
                                        keep_session_id=sessions.current_id())
    if status is MfaStatus.NOT_FOUND:
        return fail('Not Found', mfa.NOT_SET_UP, 404)
    if status is MfaStatus.ALREADY_ENABLED:
        return _already_on()
    if status is MfaStatus.INVALID:
        return _invalid()
    return _no_store(ok({'recovery_codes': codes, 'revoked_sessions': revoked}))


@api_v1.post('/me/2fa/disable')
@login_required
@limiter.shared_limit(mfa.MFA_RATE_LIMIT, scope='mfa_manage')
@_requires_mfa
@validate_json(MfaCode)
@reauth_required
def mfa_disable():
    """S9: turn 2FA off with a TOTP or a recovery code → `{revoked_sessions}`."""
    status, revoked = mfa.disable(current_user, request.validated_data.code,
                                  keep_session_id=sessions.current_id())
    if status is MfaStatus.NOT_FOUND:
        return fail('Not Found', mfa.NOT_ON, 404)
    if status is MfaStatus.INVALID:
        return _invalid()
    return ok({'revoked_sessions': revoked})


@api_v1.post('/me/2fa/recovery-codes')
@login_required
@limiter.shared_limit(mfa.MFA_RATE_LIMIT, scope='mfa_manage')
@_requires_mfa
@reauth_required
def mfa_recovery_codes():
    """S10: 10 new recovery codes replace the old ones → `{recovery_codes, revoked_sessions}`."""
    status, codes, revoked = mfa.regenerate_codes(current_user,
                                                  keep_session_id=sessions.current_id())
    if status is MfaStatus.NOT_FOUND:
        return fail('Not Found', mfa.NOT_ON, 404)
    return _no_store(ok({'recovery_codes': codes, 'revoked_sessions': revoked}))
