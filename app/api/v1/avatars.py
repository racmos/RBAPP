"""Avatars (F9-c S3, S7, S9): POST/DELETE /me/avatar and GET /users/<id>/avatar.

The logic and the only knowledge of `AVATAR_DIR` live in `app/services/avatars.py`. The
upload's per-request body limit is set by a URL value preprocessor, which Flask runs before
every `before_request` hook: the CSRF check reads the form, so the limit must already be in
place then for an oversized body to be refused before one byte of it is read.
"""
from flask import request, send_file
from flask_login import current_user, login_required
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import RequestEntityTooLarge

from app import limiter
from app.api.error_codes import DetailCode, ErrorCode
from app.api.responses import fail, ok
from app.api.v1 import api_v1
from app.schemas.validation import validation_failure
from app.services import avatars

UPLOAD_ENDPOINT = 'api_v1.upload_my_avatar'
AVATAR_RATE_LIMIT = '20/hour'
IMAGE_INVALID_MESSAGE = 'The file is not a supported image'
CACHE_CURRENT = 'private, max-age=31536000, immutable'
CACHE_STALE = 'private, no-cache'


@api_v1.url_value_preprocessor
def _limit_avatar_body(endpoint, values):
    """S3: the upload's body may be at most 5 MB + 64 KB, refused before it is read."""
    if endpoint == UPLOAD_ENDPOINT:
        request.max_content_length = avatars.MAX_BODY_BYTES


def _missing_file():
    return validation_failure([{'field': 'file', 'message': 'Field required', 'type': 'missing',
                                'code': DetailCode.REQUIRED.value}])


@api_v1.post('/me/avatar')
@login_required
@limiter.shared_limit(AVATAR_RATE_LIMIT, scope='avatar')
def upload_my_avatar():
    """Replace the caller's avatar from the multipart field `file` (S3-S6): `{avatar_url}`.
    The file name and content type of the part are never used."""
    file = request.files.get('file')
    if not isinstance(file, FileStorage):
        return _missing_file()
    blob = file.stream.read(avatars.MAX_FILE_BYTES + 1)
    if len(blob) > avatars.MAX_FILE_BYTES:
        raise RequestEntityTooLarge()
    try:
        url = avatars.save_avatar(current_user.id, blob)
    except avatars.ImageInvalid:
        return fail('Validation Error', IMAGE_INVALID_MESSAGE, 400, code=ErrorCode.IMAGE_INVALID)
    return ok({'avatar_url': url})


@api_v1.delete('/me/avatar')
@login_required
def delete_my_avatar():
    """Remove the caller's avatar (S7); the same answer when there is none."""
    avatars.remove_avatar(current_user.id)
    return ok({'avatar_url': None})


@api_v1.get('/users/<int:user_id>/avatar')
@login_required
def user_avatar(user_id):
    """Any signed-in user may read any user's avatar (S9, D-F9-12). `size` 256 (default) or
    64; `v` equal to the current version makes the answer cacheable for a year."""
    size_text = request.args.get('size', str(avatars.DEFAULT_SIZE))
    if size_text not in {str(size) for size in avatars.SIZES}:
        return validation_failure([{'field': 'size', 'message': 'size must be 256 or 64',
                                    'type': 'value_error',
                                    'code': DetailCode.INVALID_VALUE.value}],
                                  message='Invalid query parameters')
    stored = avatars.stored_avatar(user_id, int(size_text))
    if stored is None:
        return fail('Not Found', 'Avatar not found', 404)
    path, version = stored
    response = send_file(path, mimetype='image/webp', conditional=False, etag=False,
                         max_age=None, last_modified=None)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    current = request.args.get('v') == str(version)
    response.headers['Cache-Control'] = CACHE_CURRENT if current else CACHE_STALE
    response.headers.pop('Expires', None)
    return response
