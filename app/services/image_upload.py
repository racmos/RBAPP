"""Card and product image upload (F13-h S4, S5, S7): one pipeline for both admin routes.

The upload is untrusted. Its type comes from the magic bytes and Pillow only (never the client
file name or content type): PNG, JPEG or WebP, at most `MAX_FILE_BYTES` (10 MB) and
`MAX_PIXELS` (25 megapixels, checked on the header before any pixel is decoded; Pillow's
decompression-bomb warning is an error too), with a short side of at least 200 px (cards) or
120 px (products). The image is turned upright from its EXIF orientation, fitted inside 640 x 894
(cards, ratio 63:88) or 640 x 640 (products) with LANCZOS, never upscaled or cropped, and
re-encoded from bare pixels as WebP quality 85, `method=6`: no metadata (EXIF and GPS, XMP,
ICC) survives. Anything else raises `ImageRejected` and nothing is written.

Names (S5): a new file is always created, never overwritten: cards
`CARD_IMAGES_DIR/<folder>/<set lower>_<card id lower>.webp` (the folder is
`card_image_folder` of that name), products `PRODUCT_IMAGES_DIR/<id>.webp`; when the name is
taken the file is `<stem>-<n>.webp` (n = 2, 3, ...). The file is written to a temporary name
in its folder and moved into place with `os.replace`.

Previous files (S7) are never deleted at upload: `discard` deletes one when the Undo toast
expires (`POST /admin/images/finalize`), `discard_family` deletes the item's older files at
its next upload, and `orphans` / `flask images prune-orphans` lists or removes the files no
row references. A file is deleted only when it is a regular file inside its images root and
no row of its table names it.
"""
import io
import os
import re
import tempfile
import warnings
from dataclasses import dataclass
from typing import Callable, Optional

from PIL import Image, ImageOps
from sqlalchemy import select

from app import db
from app.api.error_codes import DetailCode
from app.models import RbProducts
from app.models.card import RbCard, card_image_folder, is_safe_folder
from app.services import card_images, product_images
from app.services.catalog_admin import detect_image_ext

MAX_FILE_MB = 10
MAX_FILE_BYTES = MAX_FILE_MB * 1024 * 1024          # 10,485,760: the largest file accepted
MAX_PIXELS = 25_000_000
WEBP_QUALITY = 85
WEBP_METHOD = 6
FORMATS = {'png': 'PNG', 'jpg': 'JPEG', 'webp': 'WEBP'}
# Extensions a stored image may have (the old uploads kept the source type).
STORED_EXTENSIONS = ('webp', 'png', 'jpg', 'jpeg')


@dataclass(frozen=True)
class Profile:
    """Limits of one kind of image: minimum short side and the box to fit inside."""
    min_side: int
    max_width: int
    max_height: int


CARD = Profile(min_side=200, max_width=640, max_height=894)
PRODUCT = Profile(min_side=120, max_width=640, max_height=640)


class ImageRejected(ValueError):
    """The upload is refused; `detail` is the `details[]` item of the 400 answer."""

    def __init__(self, message: str, code: DetailCode, params: Optional[dict] = None):
        super().__init__(message)
        self.detail = {'field': 'file', 'message': message, 'type': 'value_error',
                       'code': code.value}
        if params:
            self.detail['params'] = params


@dataclass(frozen=True)
class Processed:
    """A clean WebP rendering of an upload."""
    data: bytes
    width: int
    height: int
    bytes_in: int

    @property
    def bytes_out(self) -> int:
        return len(self.data)


@dataclass(frozen=True)
class Stored:
    """What an upload changed: the new file name, the one it replaced, and the figures."""
    image: str
    previous: Optional[str]
    width: int
    height: int
    bytes_in: int
    bytes_out: int

    def audit(self) -> dict:
        """The S8 audit details."""
        return {'image': self.image, 'bytes_in': self.bytes_in, 'bytes_out': self.bytes_out,
                'width': self.width, 'height': self.height}

    def payload(self) -> dict:
        """The keys the upload routes add to the item."""
        return {'image': self.image, 'previous': self.previous, 'width': self.width,
                'height': self.height, 'bytes': self.bytes_out}


def _invalid():
    return ImageRejected('unsupported image type', DetailCode.INVALID_FORMAT)


def _too_many_pixels():
    return ImageRejected('image has too many pixels', DetailCode.OUT_OF_RANGE,
                         {'max_pixels': MAX_PIXELS})


# --- untrusted bytes -> a clean WebP ----------------------------------------------------

def _decode(blob: bytes, profile: Profile) -> Image.Image:
    if len(blob) > MAX_FILE_BYTES:
        raise ImageRejected('file is too large', DetailCode.OUT_OF_RANGE,
                            {'max': MAX_FILE_BYTES})
    ext = detect_image_ext(blob[:12])
    if ext is None:
        raise _invalid()
    with warnings.catch_warnings():
        warnings.simplefilter('error', Image.DecompressionBombWarning)
        try:
            image = Image.open(io.BytesIO(blob), formats=(FORMATS[ext],))
        except (Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
            raise _too_many_pixels() from exc
        except Exception as exc:                 # any parser failure: not an image we take
            raise _invalid() from exc
        width, height = image.size
        if width * height > MAX_PIXELS:
            raise _too_many_pixels()
        if min(width, height) < profile.min_side:
            raise ImageRejected('image is too small', DetailCode.TOO_SMALL,
                                {'min': profile.min_side})
        try:
            image.load()
        except Exception as exc:
            raise _invalid() from exc
    return image


def _fit(width: int, height: int, profile: Profile) -> tuple:
    """The largest size inside the profile's box with the same ratio, never bigger."""
    scale = min(1.0, profile.max_width / width, profile.max_height / height)
    if scale >= 1.0:
        return width, height
    return (min(profile.max_width, max(1, round(width * scale))),
            min(profile.max_height, max(1, round(height * scale))))


def process(blob: bytes, profile: Profile) -> Processed:
    """A clean WebP of the upload `blob` (S4), or raise `ImageRejected`. Writes nothing."""
    image = _decode(blob, profile)
    try:
        upright = ImageOps.exif_transpose(image)
        mode = 'RGBA' if upright.has_transparency_data else 'RGB'
        upright = upright.convert(mode)
        size = _fit(*upright.size, profile)
        if size != upright.size:
            upright = upright.resize(size, Image.Resampling.LANCZOS)
        bare = Image.frombytes(upright.mode, upright.size, upright.tobytes())
        buffer = io.BytesIO()
        bare.save(buffer, 'WEBP', quality=WEBP_QUALITY, method=WEBP_METHOD)
    except Exception as exc:
        raise _invalid() from exc
    return Processed(data=buffer.getvalue(), width=size[0], height=size[1],
                     bytes_in=len(blob))


# --- names ------------------------------------------------------------------------------

def card_stem(set_id: str, card_id: str) -> str:
    """`<set lower>_<card id lower>` (S5)."""
    return f'{set_id.lower()}_{card_id.lower()}'


def free_name(stem: str, taken: Callable[[str], bool]) -> str:
    """`<stem>.webp`, or `<stem>-<n>.webp` with the first free n from 2 (S5)."""
    name = f'{stem}.webp'
    number = 2
    while taken(name):
        name = f'{stem}-{number}.webp'
        number += 1
    return name


def _family(stem: str) -> re.Pattern:
    """The files an item's uploads may have left: `<stem>.<ext>` and `<stem>-<n>.webp`."""
    extensions = '|'.join(STORED_EXTENSIONS)
    return re.compile(rf'{re.escape(stem)}(?:\.(?:{extensions})|-[0-9]+\.webp)',
                      re.IGNORECASE)


# --- writing ----------------------------------------------------------------------------

def _remove_quietly(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def _write(dest: str, data: bytes) -> None:
    """`data` to a temporary file in `dest`'s folder, then `os.replace` (atomic)."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=os.path.dirname(dest), prefix='.upload-', suffix='.tmp')
    try:
        with os.fdopen(handle, 'wb') as out:
            out.write(data)
        os.replace(temp, dest)
    except BaseException:
        _remove_quietly(temp)
        raise


def _card_path(name: str, set_id: str) -> str:
    try:
        return card_images.card_image_path(name, set_id)
    except ValueError as exc:
        raise ImageRejected('the card has no valid image name', DetailCode.INVALID_VALUE) \
            from exc


def store_card_image(card: RbCard, blob: bytes) -> Stored:
    """Process `blob` and write it as the card's new image file; set `card.image` (the caller
    audits and commits, and calls `discard_card_family` after the commit)."""
    processed = process(blob, CARD)
    stem = card_stem(card.rbcar_rbset_id, card.rbcar_id)
    previous = card.image or None
    name = free_name(stem, lambda candidate: candidate == previous or os.path.lexists(
        _card_path(candidate, card.rbcar_rbset_id)))
    dest = _card_path(name, card.rbcar_rbset_id)
    _write(dest, processed.data)
    card.image = name
    return Stored(image=name, previous=previous, width=processed.width,
                  height=processed.height, bytes_in=processed.bytes_in,
                  bytes_out=processed.bytes_out)


def store_product_image(product: RbProducts, blob: bytes) -> Stored:
    """Process `blob` and write it as the product's new image file; set `rbpdt_image`."""
    processed = process(blob, PRODUCT)
    previous = product.rbpdt_image or None
    name = free_name(str(product.rbpdt_id_product), lambda candidate: candidate == previous or
                     os.path.lexists(product_images.product_image_path(candidate)))
    _write(product_images.product_image_path(name), processed.data)
    product.rbpdt_image = name
    return Stored(image=name, previous=previous, width=processed.width,
                  height=processed.height, bytes_in=processed.bytes_in,
                  bytes_out=processed.bytes_out)


def remove_written(kind: str, stored: Stored, set_id: Optional[str] = None) -> None:
    """Delete the file of a failed upload (the commit did not happen)."""
    try:
        path = (_card_path(stored.image, set_id) if kind == 'card'
                else product_images.product_image_path(stored.image))
    except (ValueError, ImageRejected):
        return
    _remove_quietly(path)


# --- deleting (S7) ----------------------------------------------------------------------

def _card_names_in_use(names) -> set:
    names = list(names)
    if not names:
        return set()
    return set(db.session.execute(
        select(RbCard.image).where(RbCard.image.in_(names))).scalars())


def _product_names_in_use(names) -> set:
    names = list(names)
    if not names:
        return set()
    return set(db.session.execute(
        select(RbProducts.rbpdt_image).where(RbProducts.rbpdt_image.in_(names))).scalars())


def _delete_regular(root: str, path: str) -> bool:
    """Delete `path` when it is a regular file (not a symlink) inside `root`."""
    if not card_images._inside(root, path) or os.path.islink(path) or \
            not os.path.isfile(path):
        return False
    try:
        os.remove(path)
    except OSError:
        return False
    return True


def discard(kind: str, name: str, set_id: Optional[str] = None) -> bool:
    """Delete the image file `name` of a card (`set_id` for the folder of a name without a
    prefix) or a product when no row names it (S7). True when a file was deleted."""
    if not card_images.is_plain_file_name(name):
        return False
    if kind == 'card':
        if _card_names_in_use([name]):
            return False
        try:
            path = card_images.card_image_path(name, set_id)
        except ValueError:
            return False
        return _delete_regular(card_images.images_root(), path)
    if _product_names_in_use([name]):
        return False
    try:
        path = product_images.product_image_path(name)
    except ValueError:
        return False
    return _delete_regular(product_images.images_root(), path)


def _discard_family(root: str, folder_path: str, pattern: re.Pattern, keep: set,
                    in_use: Callable) -> None:
    candidates = [name for name in card_images.files_in(folder_path, root)
                  if pattern.fullmatch(name) and name not in keep]
    used = in_use(candidates)
    for name in candidates:
        if name not in used:
            _delete_regular(root, os.path.join(folder_path, name))


def discard_card_family(card: RbCard, keep) -> None:
    """At an upload (S7): delete the card's older files (`<stem>.<ext>`, `<stem>-<n>.webp`)
    but those in `keep` (the new file and the one the Undo may restore) and any a row uses."""
    stem = card_stem(card.rbcar_rbset_id, card.rbcar_id)
    folder = card_image_folder(f'{stem}.webp', card.rbcar_rbset_id)
    if not is_safe_folder(folder):
        return
    root = card_images.images_root()
    _discard_family(root, os.path.join(root, folder), _family(stem), set(keep),
                    _card_names_in_use)


def discard_product_family(product: RbProducts, keep) -> None:
    """Same as `discard_card_family` for a product (`<id>.<ext>`, `<id>-<n>.webp`)."""
    root = product_images.images_root()
    _discard_family(root, root, _family(str(product.rbpdt_id_product)), set(keep),
                    _product_names_in_use)


# --- orphans (flask images prune-orphans) -----------------------------------------------

def _is_image_name(name: str) -> bool:
    return os.path.splitext(name)[1][1:].lower() in STORED_EXTENSIONS


def _regular_files(folder_path: str):
    try:
        entries = os.scandir(folder_path)
    except OSError:
        return []
    with entries:
        return sorted(entry.name for entry in entries
                      if entry.is_file(follow_symlinks=False) and _is_image_name(entry.name)
                      and card_images.is_plain_file_name(entry.name))


def orphans() -> list:
    """`[(label, absolute path)]` of the image files no row references, cards first
    (`cards/<folder>/<file>`, then `products/<file>`). Only regular image files (png, jpg,
    jpeg, webp; never a symlink) directly inside a safe card folder or the products root."""
    found = []
    card_root = card_images.images_root()
    used_cards = {(card_image_folder(image, set_id), image) for image, set_id in
                  db.session.execute(select(RbCard.image, RbCard.rbcar_rbset_id)
                                     .where(RbCard.image.isnot(None)))}
    try:
        folders = sorted(entry.name for entry in os.scandir(card_root)
                         if entry.is_dir(follow_symlinks=False) and is_safe_folder(entry.name))
    except OSError:
        folders = []
    for folder in folders:
        for name in _regular_files(os.path.join(card_root, folder)):
            if (folder, name) not in used_cards:
                found.append((f'cards/{folder}/{name}', os.path.join(card_root, folder, name)))
    product_root = product_images.images_root()
    used_products = set(db.session.execute(
        select(RbProducts.rbpdt_image).where(RbProducts.rbpdt_image.isnot(None))).scalars())
    for name in _regular_files(product_root):
        if name not in used_products:
            found.append((f'products/{name}', os.path.join(product_root, name)))
    return found


# --- the Images screen ------------------------------------------------------------------

def summary() -> dict:
    """`{cards: {missing, total}, products: {missing, total}}` (S1 counters): missing = no
    image name or its file is not on disk. Two statements and one directory scan per card
    folder plus one of the products root."""
    cards = db.session.execute(select(RbCard.image, RbCard.rbcar_rbset_id)).all()
    present = card_images.cards_with_files((image, set_id) for image, set_id in cards)
    products = db.session.execute(select(RbProducts.rbpdt_image)
                                  .where(RbProducts.rbpdt_type == 'nonsingle')).scalars().all()
    files = product_images.existing_files()
    return {'cards': {'missing': present.count(False), 'total': len(cards)},
            'products': {'missing': sum(not product_images.product_has_file(name, files)
                                        for name in products),
                         'total': len(products)}}


class UndoStale(Exception):
    """The item's image is no longer the one the Undo was made for."""


def undo(item, kind: str, image: str, previous: Optional[str]) -> str:
    """Give `item` (a card or a product) its `previous` image back when its image is still
    `image`; the caller audits and commits, then calls `discard(kind, image, ...)`. Returns
    the replaced name. Raises UndoStale."""
    column = 'image' if kind == 'card' else 'rbpdt_image'
    if getattr(item, column) != image:
        raise UndoStale(image)
    setattr(item, column, previous or None)
    return image
