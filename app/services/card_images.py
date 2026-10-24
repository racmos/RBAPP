"""
Where card images live on disk (IMG-2, IMG-3, D13, M-d).

The images root is `CARD_IMAGES_DIR` (default `<static>/images/cards`, see
`config.py`); it is served at /riftbound/static/images/cards/ by
`app/routes/card_images.py`. Reading (`RbCard.image_src`), the admin upload and
the Riot scraper all share `app.models.card.card_image_folder`; every WRITE goes
through `card_image_path`, which refuses anything that would land outside the root.
"""
import os

from app.models.card import card_image_folder


def card_image_path(images_root: str, image: str, set_id=None) -> str:
    """Absolute path where `image` of a card in `set_id` must be stored.

    Raises ValueError when `image` is not a plain file name, when no safe folder
    can be derived (`card_image_folder` gives ''), or when the resolved path
    (symlinks followed) is not inside `images_root`. Creates nothing: the caller
    makes the directory and writes the file.
    """
    if (not isinstance(image, str) or image in ('', '.', '..')
            or image != os.path.basename(image) or '\\' in image or '\x00' in image):
        raise ValueError('the image name must be a plain file name')
    folder = card_image_folder(image, set_id)
    if not folder:
        raise ValueError('cannot derive a safe image folder (expected letters and digits only)')

    root = os.path.realpath(images_root)
    path = os.path.realpath(os.path.join(root, folder, image))
    if os.path.commonpath([root, path]) != root:
        raise ValueError('the image path escapes the card images folder')
    return path
