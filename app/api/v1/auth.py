"""Session endpoints of the JSON API (API-4..7) and the two-factor sign-in step (F9-e).

Login, lockout and registration live in `app.services.auth` and
`app.services.captcha`. CSRF is not exempt: a client reads the token from
GET /auth/session and sends it as `X-CSRFToken`.

Two-factor sign-in (F9-e): for a user with 2FA on, the right password does not sign in. The
Flask session (the signed cookie) gets a pending step instead,
`mfa_pending = {uid, remember, method, started_at, attempts}`, and POST /auth/mfa finishes it
with a TOTP or a recovery code. The pending step never authenticates anything: there is no
`_user_id` and no session row until the code is right. It lives 5 minutes from `started_at`
and allows 5 wrong codes; every wrong code is also a login failure of the account (the lock).
"""
from datetime import datetime

from flask import current_app, request, session
from flask_login import current_user, logout_user
from flask_wtf.csrf import generate_csrf

from app import db, limiter
from app.api.error_codes import ErrorCode
from app.api.responses import fail, ok
from app.api.v1 import api_v1
from app.schemas.validation import validate_json
from app.schemas.validators import LoginRequest, MfaSignIn, RegisterRequest
from app.services import auth as auth_service
from app.services import mfa as mfa_service
from app.services import profile as profile_service
from app.services import sessions as sessions_service
from app.services.auth import (AuthStatus, DuplicateUserError, LOGIN_RATE_LIMIT,
                               MFA_MAX_ATTEMPTS, MFA_METHODS, MFA_SIGNIN_RATE_LIMIT,
                               MFA_STEP_LIFETIME, REGISTER_RATE_LIMIT)
from app.services.captcha import FORM_FIELD as CAPTCHA_FIELD, get_captcha_provider
from app.services.prefs import get_prefs
from app.utils import clock

INVALID_MESSAGE = 'Invalid credentials'
LOCKED_MESSAGE = 'Invalid credentials or account temporarily locked'
CAPTCHA_MESSAGE = 'Captcha verification failed'
MFA_EXPIRED_MESSAGE = 'The sign-in step expired'
PENDING_KEY = 'mfa_pending'
PENDING_METHODS = ('password',)        # F9-f adds the OAuth providers


def user_payload(user):
    """The public fields of an account (F9-b S6: plus `display_name`, `avatar_url`). Never the
    hash. Built by `app.services.profile.user_payload`."""
    return profile_service.user_payload(user)


@api_v1.get('/auth/session')
def auth_session():
    """Who is calling, plus a CSRF token for the unsafe requests that follow.

    A blocked user counts as anonymous (Flask-Login treats an inactive user as
    not authenticated). A signed-in caller also gets `prefs` (the five interface
    preferences, `null` = Auto) so one call bootstraps the client; reading them
    never creates a row. Anonymous callers get no `prefs` key; an anonymous caller
    in the middle of a two-factor sign-in gets `mfa_pending: true` (F9-e S3).
    """
    data = {'authenticated': bool(current_user.is_authenticated), 'csrf_token': generate_csrf()}
    if data['authenticated']:
        data['user'] = user_payload(current_user)
        data['prefs'] = get_prefs(current_user.id)
    elif _live_pending() is not None:
        data['mfa_pending'] = True
    return ok(data)


@api_v1.get('/auth/captcha')
def auth_captcha():
    """A fresh challenge for the register form (`challenge` is null when there is no captcha)."""
    provider = get_captcha_provider()
    return ok({'provider': provider.name, 'challenge': provider.challenge()})


def _locked(retry_after):
    return fail('Too Many Requests', LOCKED_MESSAGE, 429,
                headers={'Retry-After': str(retry_after)},
                code=ErrorCode.LOCKED, params={'retry_after': int(retry_after)})


# --- The pending two-factor step (F9-e S2, S3) -----------------------------------------------

def _live_pending():
    """The pending step of this Flask session while it is usable (well formed, under 5 minutes
    old, under 5 wrong codes); None otherwise. Reads only the cookie, never the database."""
    pending = session.get(PENDING_KEY)
    if not isinstance(pending, dict):
        return None
    try:
        uid = pending['uid']
        attempts = pending['attempts']
        started = datetime.fromisoformat(pending['started_at'])
    except (KeyError, TypeError, ValueError):
        return None
    if not isinstance(uid, int) or not isinstance(attempts, int) \
            or not isinstance(pending.get('remember'), bool) \
            or pending.get('method') not in PENDING_METHODS:
        return None
    if attempts >= MFA_MAX_ATTEMPTS or clock.utcnow() - started >= MFA_STEP_LIFETIME:
        return None
    return pending


def _drop_pending():
    """Remove the pending step; True when there was one. A Flask session without it is not
    touched (no cookie written, no `Vary: Cookie`)."""
    return session.pop(PENDING_KEY, None) is not None


def _start_pending(user, remember, method):
    """Replace any pending step with a new one. A client that was signed in (as anybody) is
    signed out first, as by a logout: while the step exists the client has no identity (S3)."""
    if current_user.is_authenticated:
        session_id = sessions_service.current_id()
        if session_id is not None:
            sessions_service.revoke(current_user.id, session_id)
        logout_user()
    session[PENDING_KEY] = {'uid': user.id, 'remember': bool(remember), 'method': method,
                            'started_at': clock.utcnow().isoformat(), 'attempts': 0}


def _mfa_expired():
    return fail('Unauthorized', MFA_EXPIRED_MESSAGE, 401, code=ErrorCode.MFA_EXPIRED)


@api_v1.post('/auth/login')
@limiter.shared_limit(LOGIN_RATE_LIMIT, scope='login')
@validate_json(LoginRequest)
def auth_login():
    credentials = request.validated_data
    _drop_pending()                         # a new password login ends any pending step (S3)
    result = auth_service.authenticate(credentials.username, credentials.password)

    if result.status is AuthStatus.OK:
        # One server-side session row per sign-in (F9-a S5); the body is unchanged.
        sessions_service.sign_in(result.user, remember=credentials.remember,
                                 auth_method='password')
        return ok({'user': user_payload(result.user)})

    if result.status is AuthStatus.MFA_REQUIRED:
        # F9-e S2: no session row, no login, no remember cookie; the code goes to /auth/mfa.
        _start_pending(result.user, credentials.remember, 'password')
        return ok({'mfa_required': True, 'methods': list(MFA_METHODS)})

    if result.status is AuthStatus.LOCKED:
        return _locked(result.retry_after)

    # INVALID, and BLOCKED if it ever appears: indistinguishable (R4).
    return fail('Unauthorized', INVALID_MESSAGE, 401, code=ErrorCode.INVALID_CREDENTIALS)


@api_v1.post('/auth/mfa')
@limiter.shared_limit(MFA_SIGNIN_RATE_LIMIT, scope='mfa')
@validate_json(MfaSignIn)
def auth_mfa():
    """Finish a two-factor sign-in (F9-e S4) with a TOTP `code` or a `recovery_code`.

    401 `mfa_expired` without a live pending step (or when its user is gone, blocked or has no
    2FA any more); 429 `locked` while the account is locked; 401 `mfa_invalid` for a wrong code
    (one more login failure; the 5th wrong code ends the step); 503 for a TOTP code while 2FA
    is unavailable (nothing counted; a recovery code still works). A right code signs in
    through `sessions.sign_in(..., mfa_passed=True)` → `{user, recovery_code_used,
    recovery_codes_left}`.
    """
    data = request.validated_data
    pending = _live_pending()
    if pending is None:
        _drop_pending()
        return _mfa_expired()

    try:
        result = auth_service.second_factor(pending['uid'], code=data.code,
                                            recovery_code=data.recovery_code)
    except mfa_service.MfaUnavailable:
        db.session.rollback()
        return fail('Service Unavailable', mfa_service.NOT_AVAILABLE, 503)

    if result.status is AuthStatus.EXPIRED:
        _drop_pending()
        return _mfa_expired()

    if result.status is AuthStatus.LOCKED:
        _drop_pending()
        return _locked(result.retry_after)

    if result.status is AuthStatus.INVALID:
        attempts = pending['attempts'] + 1
        if attempts >= MFA_MAX_ATTEMPTS:
            _drop_pending()
        else:
            session[PENDING_KEY] = {**pending, 'attempts': attempts}
        return fail('Unauthorized', mfa_service.CODE_INVALID, 401, code=ErrorCode.MFA_INVALID)

    _drop_pending()
    user = result.user
    # Commits the session row with the reset count, the TOTP step or the used recovery code.
    sessions_service.sign_in(user, remember=bool(pending['remember']),
                             auth_method=pending['method'], mfa_passed=True)
    left = mfa_service.status(user.id)['recovery_codes_left']
    return ok({'user': user_payload(user), 'recovery_code_used': result.recovery_code_used,
               'recovery_codes_left': left})


@api_v1.post('/auth/logout')
def auth_logout():
    """End the server-side session, then the cookies (F9-a S8): the old Flask session or
    remember cookie can never sign in again. It also ends a pending two-factor step (F9-e S3):
    a client with only that step gets `{}`; a client with neither is the usual 401."""
    had_pending = _drop_pending()
    if not current_user.is_authenticated:
        if had_pending:
            return ok({})
        return current_app.login_manager.unauthorized()
    session_id = sessions_service.current_id()
    if session_id is not None:
        sessions_service.revoke(current_user.id, session_id)
    logout_user()
    return ok({})


@api_v1.post('/auth/register')
@limiter.shared_limit(REGISTER_RATE_LIMIT, scope='register')
@validate_json(RegisterRequest)
def auth_register():
    data = request.validated_data

    # Same order as the form: fields (done by validate_json), then the captcha
    # (so a bot cannot probe usernames without solving it), then duplicates.
    body = request.get_json(silent=True) or {}
    if not get_captcha_provider().verify(body.get(CAPTCHA_FIELD)):
        return fail('Captcha Error', CAPTCHA_MESSAGE, 400, code=ErrorCode.CAPTCHA_FAILED)

    try:
        user = auth_service.register_user(data)
    except DuplicateUserError as error:
        code = ErrorCode.USERNAME_TAKEN if error.field == 'username' else ErrorCode.EMAIL_TAKEN
        return fail('Conflict', error.message, 409, code=code)

    # No session: the client logs in afterwards.
    return ok({'user': {'id': user.id, 'username': user.username}}, status=201)
