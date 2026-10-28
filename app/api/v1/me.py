"""The signed-in user's own settings: GET/PATCH /me/prefs (PREF-3, PREF-4).

Preferences are account-level interface settings; `null` means Auto. The PATCH
body is validated before anything is written, so it is all-or-nothing, and only
the fields that were sent are applied (`model_fields_set`).
"""
from flask import request
from flask_login import current_user, login_required

from app.api.responses import ok
from app.api.v1 import api_v1
from app.schemas.validation import validate_json
from app.schemas.validators import PrefsUpdate
from app.services import prefs as prefs_service


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
