"""Session endpoints of the JSON API (API-4..7).

They use the same services, lockout and rate limits as the Jinja forms
(`app.services.auth`, `app.services.captcha`), so both front doors behave the
same. CSRF is not exempt: a client reads the token from GET /auth/session and
sends it as `X-CSRFToken`.
"""
from flask import request
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf.csrf import generate_csrf

from app import limiter
from app.api.error_codes import ErrorCode
from app.api.responses import fail, ok
from app.api.v1 import api_v1
from app.schemas.validation import validate_json
from app.schemas.validators import LoginRequest, RegisterRequest
from app.services import auth as auth_service
from app.services.auth import (AuthStatus, DuplicateUserError, LOGIN_RATE_LIMIT,
                               REGISTER_RATE_LIMIT)
from app.services.captcha import FORM_FIELD as CAPTCHA_FIELD, get_captcha_provider
from app.services.prefs import get_prefs

INVALID_MESSAGE = 'Invalid credentials'
LOCKED_MESSAGE = 'Invalid credentials or account temporarily locked'
CAPTCHA_MESSAGE = 'Captcha verification failed'


def user_payload(user):
    """The public fields of an account. Never the hash."""
    return {'id': user.id, 'username': user.username, 'email': user.email,
            'is_admin': bool(user.is_admin)}


@api_v1.get('/auth/session')
def auth_session():
    """Who is calling, plus a CSRF token for the unsafe requests that follow.

    A blocked user counts as anonymous (Flask-Login treats an inactive user as
    not authenticated). A signed-in caller also gets `prefs` (the five interface
    preferences, `null` = Auto) so one call bootstraps the client; reading them
    never creates a row. Anonymous callers get no `prefs` key.
    """
    data = {'authenticated': bool(current_user.is_authenticated), 'csrf_token': generate_csrf()}
    if data['authenticated']:
        data['user'] = user_payload(current_user)
        data['prefs'] = get_prefs(current_user.id)
    return ok(data)


@api_v1.get('/auth/captcha')
def auth_captcha():
    """A fresh challenge for the register form (`challenge` is null when there is no captcha)."""
    provider = get_captcha_provider()
    return ok({'provider': provider.name, 'challenge': provider.challenge()})


@api_v1.post('/auth/login')
@limiter.shared_limit(LOGIN_RATE_LIMIT, scope='login')
@validate_json(LoginRequest)
def auth_login():
    credentials = request.validated_data
    result = auth_service.authenticate(credentials.username, credentials.password)

    if result.status is AuthStatus.OK:
        login_user(result.user, remember=credentials.remember)
        return ok({'user': user_payload(result.user)})

    if result.status is AuthStatus.LOCKED:
        return fail('Too Many Requests', LOCKED_MESSAGE, 429,
                    headers={'Retry-After': str(result.retry_after)},
                    code=ErrorCode.LOCKED, params={'retry_after': int(result.retry_after)})

    # INVALID, and BLOCKED if it ever appears: indistinguishable (R4).
    return fail('Unauthorized', INVALID_MESSAGE, 401, code=ErrorCode.INVALID_CREDENTIALS)


@api_v1.post('/auth/logout')
@login_required
def auth_logout():
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
