"""The signed-in user's own settings: GET/PATCH /me/prefs (PREF-3, PREF-4), PATCH /me/account.

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
from app.schemas.validation import validate_json
from app.schemas.validators import AccountUpdate, PrefsUpdate
from app.services import account as account_service
from app.services import prefs as prefs_service
from app.services.account import ACCOUNT_RATE_LIMIT, AccountStatus


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
def patch_me_account():
    """Change the caller's email and/or password; returns the fresh user.

    The limit also caps guesses of the current password. The session stays valid after a
    password change (Flask-Login keys it on the user id).
    """
    data = request.validated_data
    status = account_service.update_account(current_user, data.email, data.password,
                                            data.current_password)
    if status is AccountStatus.WRONG_PASSWORD:
        return fail('Bad Request', account_service.CURRENT_PASSWORD_INCORRECT, 400,
                    code=ErrorCode.CURRENT_PASSWORD_INCORRECT)
    if status is AccountStatus.EMAIL_TAKEN:
        return fail('Conflict', account_service.EMAIL_IN_USE, 409, code=ErrorCode.EMAIL_TAKEN)
    return ok({'user': user_payload(current_user)})
