"""
User avatars (F9-c S2, S4-S8): untrusted image parsing, processing, storage and URLs.

This is the only module that knows the avatars root: `AVATAR_DIR` (default
`<project>/data/avatars`, see `config.py`), a data directory outside git, created on the
first upload. Each avatar is two WebP files, `<stem>-256.webp` and `<stem>-64.webp`, where
the stem `<user id>-<version>` comes from `rbuserprofile.rbupf_avatar_file`. Paths are built
only from that stored stem and a known size (`avatar_path`); no client text ever reaches
the file system.

The upload is decoded by Pillow only (never the file name or the content type): accepted
formats JPEG, PNG, WebP and GIF (first frame), at least 64 px a side and at most 25
megapixels (checked on the header, before any pixel is decoded; Pillow's decompression-bomb
warning is an error too). The image is turned upright from its EXIF orientation, cropped to
a centred square, resized and re-encoded from bare pixels, so no metadata of the upload
(EXIF and GPS, XMP, ICC) survives. Anything else is `ImageInvalid` and nothing is written.

The files are served by `GET /users/<id>/avatar` (`app/api/v1/avatars.py`) to signed-in
users only (D-F9-12).
"""
import io
import logging
import os
import re
import tempfile
import warnings
from typing import Optional

from flask import current_app
from PIL import Image, ImageOps

from app import db
from app.models import RbUserProfile
from app.utils import clock

logger = logging.getLogger(__name__)

SIZES = (256, 64)
DEFAULT_SIZE = 256
MAX_FILE_MB = 5
MAX_FILE_BYTES = MAX_FILE_MB * 1024 * 1024              # 5,242,880: the largest file accepted
MAX_BODY_BYTES = MAX_FILE_BYTES + 64 * 1024             # the request body around it (multipart)
MAX_PIXELS = 25_000_000
MIN_SIDE = 64
FORMATS = ('JPEG', 'PNG', 'WEBP', 'GIF')
WEBP_QUALITY = 85
URL_TEMPLATE = '/riftbound/api/v1/users/{user_id}/avatar?v={version}'

_STEM = re.compile(r'[0-9]+-[0-9]+')


class ImageInvalid(ValueError):
    """The upload is not a supported image. `reason` (for logs and tests, never shown):
    `not_an_image`, `too_many_pixels`, `too_small` or `damaged`."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


# --- where the files live -------------------------------------------------------------

def avatars_root() -> str:
    """The avatars root (`AVATAR_DIR`)."""
    return current_app.config['AVATAR_DIR']


def avatar_path(stem, size) -> str:
    """Absolute path of the `size` file of the avatar `stem` (`<user id>-<version>`).

    Raises ValueError when the stem is not two numbers joined by `-`, the size is not one
    of `SIZES`, or the resolved path (symlinks followed) is not inside the root. Creates
    nothing.
    """
    if not isinstance(stem, str) or not _STEM.fullmatch(stem):
        raise ValueError('the avatar stem must be <user id>-<version>')
    if isinstance(size, bool) or size not in SIZES:
        raise ValueError('unknown avatar size')
    root = os.path.realpath(avatars_root())
    path = os.path.join(root, f'{stem}-{size}.webp')
    if os.path.commonpath([root, os.path.realpath(path)]) != root:
        raise ValueError('the avatar path escapes the avatars folder')
    return path


def avatar_url(user_id: int, version: int) -> str:
    """`/riftbound/api/v1/users/<id>/avatar?v=<version>` (S8)."""
    return URL_TEMPLATE.format(user_id=int(user_id), version=int(version))


def profile_avatar_url(row: Optional[RbUserProfile]) -> Optional[str]:
    """The `avatar_url` of a profile row: the versioned URL, or None without an avatar."""
    if row is None or not row.rbupf_avatar_file:
        return None
    return avatar_url(row.rbupf_user_id, row.rbupf_avatar_version)


def stored_avatar(user_id: int, size: int):
    """`(path, version)` of the `size` file of the user's current avatar, or None when the
    user has no avatar, the stored stem is unusable or the file is missing."""
    row = db.session.get(RbUserProfile, user_id)
    if row is None or not row.rbupf_avatar_file:
        return None
    try:
        path = avatar_path(row.rbupf_avatar_file, size)
    except ValueError:
        return None
    if not os.path.isfile(path):
        return None
    return path, row.rbupf_avatar_version


# --- untrusted image -> two clean WebP files ------------------------------------------

def _decode(blob: bytes) -> Image.Image:
    """Open and fully decode `blob` with the checks of S4, or raise `ImageInvalid`."""
    with warnings.catch_warnings():
        warnings.simplefilter('error', Image.DecompressionBombWarning)
        try:
            image = Image.open(io.BytesIO(blob), formats=FORMATS)
        except Exception as exc:                 # any parser failure: not an image we take
            raise ImageInvalid('not_an_image') from exc
        if image.format not in FORMATS:
            raise ImageInvalid('not_an_image')
        width, height = image.size
        if width * height > MAX_PIXELS:
            raise ImageInvalid('too_many_pixels')
        if min(width, height) < MIN_SIDE:
            raise ImageInvalid('too_small')
        try:
            image.seek(0)                        # GIF: the first frame only
            image.load()
        except Exception as exc:
            raise ImageInvalid('damaged') from exc
    return image


def _webp(image: Image.Image) -> bytes:
    """`image` re-encoded from its bare pixels: no EXIF, XMP or ICC can travel along."""
    bare = Image.frombytes(image.mode, image.size, image.tobytes())
    buffer = io.BytesIO()
    bare.save(buffer, 'WEBP', quality=WEBP_QUALITY)
    return buffer.getvalue()


def process_image(blob: bytes) -> dict:
    """`{256: webp bytes, 64: webp bytes}` from an uploaded file (S4, S5), or raise
    `ImageInvalid`. Pure: writes nothing."""
    image = _decode(blob)
    try:
        upright = ImageOps.exif_transpose(image)
        mode = 'RGBA' if upright.has_transparency_data else 'RGB'
        upright = upright.convert(mode)
        width, height = upright.size
        side = min(width, height)
        left, top = (width - side) // 2, (height - side) // 2
        square = upright.crop((left, top, left + side, top + side))
        return {size: _webp(square.resize((size, size), Image.Resampling.LANCZOS))
                for size in SIZES}
    except Exception as exc:
        raise ImageInvalid('damaged') from exc


# --- storage --------------------------------------------------------------------------

def _remove_quietly(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def _write_files(stem: str, renders: dict) -> None:
    """Write each render to a temporary name in the root and move it into place with
    `os.replace`. On any failure no temporary file and no new file is left."""
    os.makedirs(avatars_root(), exist_ok=True)
    placed = []
    try:
        for size, data in renders.items():
            dest = avatar_path(stem, size)
            handle, temp = tempfile.mkstemp(dir=os.path.dirname(dest), prefix='.upload-',
                                            suffix='.tmp')
            try:
                with os.fdopen(handle, 'wb') as out:
                    out.write(data)
                os.replace(temp, dest)
            except BaseException:
                _remove_quietly(temp)
                raise
            placed.append(dest)
    except BaseException:
        for path in placed:
            _remove_quietly(path)
        raise


def _delete_files(stem: str) -> None:
    """Delete both files of `stem`; a failure is logged, never raised (S6)."""
    for size in SIZES:
        try:
            path = avatar_path(stem, size)
        except ValueError:
            logger.warning('could not delete avatar %r: not a valid stem', stem)
            return
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        except OSError as exc:
            logger.warning('could not delete avatar file %s: %s', os.path.basename(path), exc)


def save_avatar(user_id: int, blob: bytes) -> str:
    """Store `blob` as the user's avatar (S6) and return its URL.

    The image is processed first (`ImageInvalid`: nothing written); then the new version's
    files are put in place, the profile row (created if missing) is committed, and the
    previous version's files are deleted. A failed commit removes the new files.
    """
    renders = process_image(blob)
    row = db.session.get(RbUserProfile, user_id)
    previous = row.rbupf_avatar_file if row is not None else None
    version = (row.rbupf_avatar_version or 0) + 1 if row is not None else 1
    stem = f'{int(user_id)}-{version}'
    _write_files(stem, renders)
    try:
        if row is None:
            row = RbUserProfile(rbupf_user_id=user_id)
            db.session.add(row)
        row.rbupf_avatar_file = stem
        row.rbupf_avatar_version = version
        row.rbupf_updated_at = clock.utcnow()
        db.session.commit()
    except BaseException:
        db.session.rollback()
        _delete_files(stem)
        raise
    if previous and previous != stem:
        _delete_files(previous)
    return avatar_url(user_id, version)


def remove_avatar(user_id: int) -> None:
    """Remove the user's avatar (S7): clear the file, bump the version so cached URLs
    change, commit, delete the files. Without an avatar nothing changes."""
    row = db.session.get(RbUserProfile, user_id)
    if row is None or not row.rbupf_avatar_file:
        return
    stem = row.rbupf_avatar_file
    row.rbupf_avatar_file = None
    row.rbupf_avatar_version = (row.rbupf_avatar_version or 0) + 1
    row.rbupf_updated_at = clock.utcnow()
    db.session.commit()
    _delete_files(stem)
