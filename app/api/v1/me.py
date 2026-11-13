"""The signed-in user's own settings: GET/PATCH /me/prefs (PREF-3, PREF-4), PATCH /me/account,
the private profile GET/PATCH /me and POST /me/reauth (F9-b).

Preferences are account-level interface settings; `null` means Auto. The PATCH
body is validated before anything is written, so it is all-or-nothing, and only
the fields that were sent are applied (`model_fields_set`).
"""
from flask import request
from flask_login import current_user, login_required

from app import limiter
from app.api.error_codes import ErrorCode
from app.api.responses import fail, ok
from app.api.v1 import api_v1
from app.api.v1.auth import user_payload
from app.schemas.validation import validate_json, validation_failure
from app.schemas.validators import (CURRENT_PASSWORD_REQUIRED, AccountUpdate, PrefsUpdate,
                                    ProfilePatch, ReauthRequest)
from app.security import REAUTH_WINDOW, reauth_required
from app.services import account as account_service
from app.services import prefs as prefs_service
from app.services import profile as profile_service
from app.services import sessions as sessions_service
from app.services.account import (ACCOUNT_RATE_LIMIT, REAUTH_RATE_LIMIT, AccountStatus,
                                  ReauthStatus)


def _value_error(field, message, type_='value_error'):
    """One `details[]` item for a check made after the schema."""
    return {'field': field, 'message': message, 'type': type_, 'code': 'invalid_value'}


def _first_password():
    """S5: setting a password on an account without one is a sensitive action (S10)."""
    return request.validated_data.password is not None and not current_user.has_password


@api_v1.get('/me')
@login_required
def get_me():
    """`{user, profile, security}` of the caller (F9-b S7). Never creates a profile row."""
    return ok(profile_service.me_payload(current_user))


@api_v1.patch('/me')
@login_required
@validate_json(ProfilePatch)
def patch_me():
    """Absent = unchanged, `null` or blank = cleared; all-or-nothing (S8). Returns `GET /me`."""
    data = request.validated_data
    profile_service.update_profile(current_user.id,
                                   data.model_dump(include=data.model_fields_set))
    return ok(profile_service.me_payload(current_user))


@api_v1.post('/me/reauth')
@login_required
@limiter.shared_limit(REAUTH_RATE_LIMIT, scope='reauth')
@validate_json(ReauthRequest)
def me_reauth():
    """Re-authenticate the current session (S11): `{reauth_until}` for the next 10 minutes."""
    data = request.validated_data
    status, at = account_service.reauthenticate(current_user, data.password, data.code)
    if status is ReauthStatus.NO_TWO_FACTOR:
        return validation_failure([_value_error('code', account_service.NO_TWO_FACTOR,
                                                'invalid_value')])
    if status is ReauthStatus.NO_PASSWORD:
        return validation_failure([_value_error('password', account_service.NO_PASSWORD,
                                                'invalid_value')])
    if status is ReauthStatus.WRONG_PASSWORD:
        return fail('Bad Request', account_service.CURRENT_PASSWORD_INCORRECT, 400,
                    code=ErrorCode.CURRENT_PASSWORD_INCORRECT)
    return ok({'reauth_until': sessions_service._iso(at + REAUTH_WINDOW)})


@api_v1.get('/me/prefs')
@login_required
def get_me_prefs():
    """The preferences, each `null` when unset. Never creates a row."""
    return ok({'prefs': prefs_service.get_prefs(current_user.id)})


@api_v1.patch('/me/prefs')
@login_required
@validate_json(PrefsUpdate)
def patch_me_prefs():
    """Absent = unchanged, `null` = Auto, a valid value = stored; returns all of them."""
    data = request.validated_data
    changes = data.model_dump(include=data.model_fields_set)
    return ok({'prefs': prefs_service.update_prefs(current_user.id, changes)})


@api_v1.patch('/me/account')
@login_required
@limiter.shared_limit(ACCOUNT_RATE_LIMIT, scope='account')
@validate_json(AccountUpdate)
@reauth_required(when=_first_password)
def patch_me_account():
    """Change the caller's email (`null` or blank removes it) and/or password; returns the
    fresh user (F9-b S5).

    The limit also caps guesses of the current password. A first password on an account
    without one needs a recent re-authentication instead of the current password. A password
    change ends every other session of the user; this one stays signed in (F9-a S9).
    """
    data = request.validated_data
    email = data.email if 'email' in data.model_fields_set else account_service.UNCHANGED
    status = account_service.update_account(current_user, email, data.password,
                                            data.current_password)
    if status is AccountStatus.CURRENT_PASSWORD_REQUIRED:
        # The body the schema gave before F9-b (pinned by a CHAR test).
        return validation_failure([_value_error('', f'Value error, {CURRENT_PASSWORD_REQUIRED}')])
    if status is AccountStatus.WRONG_PASSWORD:
        return fail('Bad Request', account_service.CURRENT_PASSWORD_INCORRECT, 400,
                    code=ErrorCode.CURRENT_PASSWORD_INCORRECT)
    if status is AccountStatus.EMAIL_TAKEN:
        return fail('Conflict', account_service.EMAIL_IN_USE, 409, code=ErrorCode.EMAIL_TAKEN)
    return ok({'user': user_payload(current_user)})
