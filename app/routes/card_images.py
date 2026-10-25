"""Card images from the data directory (M-d, S3).

  GET /riftbound/static/images/cards/<path>  -> the file under CARD_IMAGES_DIR

Same URL as before, so `RbCard.image_src`, the pages and the API do not change;
only where the files live on disk does. The rule is more specific than Flask's
`static` rule, so it wins for this prefix and every other /riftbound/static/
URL keeps coming from the app's static folder.

Public, like the static files. `..`, absolute paths and symlinks that resolve
outside the root are a 404, as is a missing file, a folder or a null byte. Caching is
Flask's static one: conditional requests and SEND_FILE_MAX_AGE_DEFAULT.
"""
import os

from flask import Blueprint, abort, current_app, send_from_directory
from werkzeug.security import safe_join

card_images_bp = Blueprint('card_images', __name__)


def _inside(root: str, path: str) -> bool:
    """True when `path` (symlinks followed) is `root` or below it."""
    root = os.path.realpath(root)
    return os.path.commonpath([root, os.path.realpath(path)]) == root


@card_images_bp.get('/riftbound/static/images/cards/<path:filename>')
def serve(filename):
    root = current_app.config['CARD_IMAGES_DIR']
    if '\x00' in filename:                          # os.path would raise; static answers 404
        abort(404)
    path = safe_join(root, filename)                # None for `..` or an absolute path
    if path is None or not _inside(root, path) or not os.path.isfile(path):
        abort(404)
    return send_from_directory(root, filename)
