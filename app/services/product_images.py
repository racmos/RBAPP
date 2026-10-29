"""
Where product images live on disk and on the web (F14-d S1, S4).

The only module that knows the product images root: `PRODUCT_IMAGES_DIR` (default
`<project>/data/product-images`, see `config.py`), a data directory outside git.
The files sit directly in the root, named `<product id>.<ext>` by the admin upload
(`app/api/admin/products.py`), and are served by `app/routes/media.py` at
/riftbound/media/products/<filename> (`ProductSummary.image_src`).
"""
import os

from flask import current_app

from app.services.card_images import _inside, is_plain_file_name

MEDIA_URL_PREFIX = '/riftbound/media/products'

# Extensions the media route serves; the upload writes only these (from the magic bytes).
IMAGE_EXTENSIONS = ('png', 'jpg', 'jpeg', 'webp')


def images_root() -> str:
    """The product images root (`PRODUCT_IMAGES_DIR`)."""
    return current_app.config['PRODUCT_IMAGES_DIR']


def product_image_path(filename: str) -> str:
    """Absolute path where `filename` must be stored.

    Raises ValueError when `filename` is not a plain file name or when the resolved
    path (symlinks followed) is not inside `images_root()`. Creates nothing: the
    caller makes the directory and writes the file.
    """
    if not is_plain_file_name(filename):
        raise ValueError('the image name must be a plain file name')
    root = os.path.realpath(images_root())
    path = os.path.realpath(os.path.join(root, filename))
    if os.path.commonpath([root, path]) != root:
        raise ValueError('the image path escapes the product images folder')
    return path


def product_image_url(filename):
    """`/riftbound/media/products/<filename>`, or None when there is no image or the
    name is not a plain file name."""
    if not filename or not is_plain_file_name(filename):
        return None
    return f'{MEDIA_URL_PREFIX}/{filename}'


def has_image_extension(filename: str) -> bool:
    """True when the extension (any case) is one of `IMAGE_EXTENSIONS`."""
    _, ext = os.path.splitext(filename)
    return ext[1:].lower() in IMAGE_EXTENSIONS


def stored_product_image(filename: str):
    """`filename` when it is a plain name with an image extension and an existing
    regular file inside the root (symlinks followed), else None."""
    if not is_plain_file_name(filename) or not has_image_extension(filename):
        return None
    root = images_root()
    path = os.path.join(root, filename)
    if not os.path.isfile(path) or not _inside(root, path):
        return None
    return filename
