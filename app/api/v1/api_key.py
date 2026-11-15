"""The signed-in user's personal read-only API key (F9-h S3-S5): GET, POST and DELETE
/me/api-key.

POST needs a recent re-authentication of the current session (`reauth_required`) and answers the
key once (`Cache-Control: no-store`); it replaces an existing key in the same transaction. DELETE
needs no re-authentication and is idempotent. None of these routes accepts a key itself (the
deny list of `app.services.api_keys`). Logic in `app/services/api_keys.py`.
"""
from flask_login import current_user, login_required

from app.api.responses import ok
from app.api.v1 import api_v1
from app.security import reauth_required
from app.services import api_keys


@api_v1.get('/me/api-key')
@login_required
def get_my_api_key():
    """S3: `{api_key: {prefix, created_at, last_used_at} | null}`."""
    return ok({'api_key': api_keys.get_info(current_user.id)})


@api_v1.post('/me/api-key')
@login_required
@reauth_required
def create_my_api_key():
    """S4: create or replace the key → 201 `{key, api_key}`; the only time the key is shown."""
    key, info = api_keys.create(current_user.id)
    response = ok({'key': key, 'api_key': info}, status=201)
    response.headers['Cache-Control'] = 'no-store'
    return response


@api_v1.delete('/me/api-key')
@login_required
def delete_my_api_key():
    """S5: revoke the key (idempotent) → `{api_key: null}`."""
    api_keys.revoke(current_user.id)
    return ok({'api_key': None})
