"""Card images from the data directory (M-d, S4, D-Md-2).

  GET /riftbound/media/cards/<folder>/<filename>  -> CARD_IMAGES_DIR/<folder>/<filename>

Public, like the static files; the URLs come from `RbCard.image_src`
(`app.services.card_images.card_image_url`). `folder` must be letters and digits
and `filename` a plain file name; anything else, a missing file, a folder or a
symlink that resolves outside the root is a 404. Images are cached for a week.

The route never touches `session` or `current_user`, so no response carries a
`Set-Cookie`. Its 404 is a minimal answer, not the Jinja error page, because
`base.html` would write the session (same reason as `app/routes/spa.py`).
"""
from flask import Blueprint, make_response, send_from_directory

from app.errors import json_error, wants_json
from app.services.card_images import images_root, stored_card_image

media_bp = Blueprint('media', __name__, url_prefix='/riftbound/media')

CACHE_WEEK = 'public, max-age=604800'


def _not_found():
    if wants_json():
        return json_error('Not Found', 'Image not found', 404)
    response = make_response('Not Found\n', 404)
    response.content_type = 'text/plain; charset=utf-8'
    return response


@media_bp.get('/cards/<folder>/<filename>')
def card_image(folder, filename):
    relative = stored_card_image(folder, filename)
    if relative is None:
        return _not_found()
    response = send_from_directory(images_root(), relative, conditional=True)
    response.headers['Cache-Control'] = CACHE_WEEK
    return response
