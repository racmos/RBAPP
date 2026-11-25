"""
Where card images live on disk and on the web (IMG-1, IMG-2, IMG-3, D13, M-d).

This is the only module that knows the images root: `CARD_IMAGES_DIR` (default
`<project>/data/card-images`, see `config.py`), a data directory outside git.
Pages read `RbCard.image_src` (= `card_image_url`), served by
`app/routes/media.py` at /riftbound/media/cards/<folder>/<image>; the admin
upload and the Riot scraper write through `card_image_path`, which refuses
anything that would land outside the root. The folder rule is
`app.models.card.card_image_folder`.
"""
import os
import shutil

from flask import current_app

from app.models.card import card_image_folder, is_safe_folder

MEDIA_URL_PREFIX = '/riftbound/media/cards'


def images_root() -> str:
    """The card images root (`CARD_IMAGES_DIR`)."""
    return current_app.config['CARD_IMAGES_DIR']


def is_plain_file_name(name) -> bool:
    """True when `name` is a single path segment without control characters.

    Separators, NUL and C0/DEL control characters are refused: the latter can
    make the HTTP server reject an otherwise valid on-disk name with a 500.
    """
    return (isinstance(name, str) and name not in ('', '.', '..')
            and name == os.path.basename(name) and '\\' not in name
            and all(ord(char) >= 0x20 and ord(char) != 0x7f for char in name))


def _inside(root: str, path: str) -> bool:
    """True when `path` (symlinks followed) is `root` or below it."""
    root = os.path.realpath(root)
    return os.path.commonpath([root, os.path.realpath(path)]) == root


def card_image_path(image: str, set_id=None) -> str:
    """Absolute path where `image` of a card in `set_id` must be stored.

    Raises ValueError when `image` is not a plain file name, when no safe folder
    can be derived (`card_image_folder` gives ''), or when the resolved path
    (symlinks followed) is not inside `images_root()`. Creates nothing: the
    caller makes the directory and writes the file.
    """
    if not is_plain_file_name(image):
        raise ValueError('the image name must be a plain file name')
    folder = card_image_folder(image, set_id)
    if not folder:
        raise ValueError('cannot derive a safe image folder (expected letters and digits only)')

    root = os.path.realpath(images_root())
    path = os.path.realpath(os.path.join(root, folder, image))
    if os.path.commonpath([root, path]) != root:
        raise ValueError('the image path escapes the card images folder')
    return path


def card_image_url(image, set_id=None):
    """`/riftbound/media/cards/<folder>/<image>`, or None when there is no image
    or no safe folder."""
    if not image:
        return None
    folder = card_image_folder(image, set_id)
    if not folder:
        return None
    return f'{MEDIA_URL_PREFIX}/{folder}/{image}'


def stored_card_image(folder: str, filename: str):
    """Relative path `<folder>/<filename>` of an existing image under the root, or
    None when a name is unsafe, the file is missing or is not a regular file, or
    it resolves (symlinks followed) outside the root."""
    if not is_safe_folder(folder) or not is_plain_file_name(filename):
        return None
    root = images_root()
    path = os.path.join(root, folder, filename)
    if not os.path.isfile(path) or not _inside(root, path):
        return None
    return f'{folder}/{filename}'


def files_in(folder_path: str, root: str) -> set:
    """Names of the regular files directly in `folder_path` (one `os.scandir`, F13-h S2).

    A symlink counts only when it resolves to a regular file inside `root` (what the media
    route serves). A missing or unreadable folder has no files.
    """
    names = set()
    try:
        entries = os.scandir(folder_path)
    except OSError:
        return names
    with entries:
        for entry in entries:
            try:
                if not entry.is_file():
                    continue
                if entry.is_symlink() and not _inside(root, entry.path):
                    continue
            except OSError:
                continue
            names.add(entry.name)
    return names


def existing_files(folders) -> dict:
    """`{folder: set of file names}` of the safe `folders` under the root: one directory scan
    per folder, whatever the number of cards (F13-h S2)."""
    root = images_root()
    return {folder: files_in(os.path.join(root, folder), root)
            for folder in set(folders) if is_safe_folder(folder)}


def card_has_file(image, set_id, existing: dict) -> bool:
    """True when the card's `image` names a file present in `existing` (`existing_files`)."""
    if not image or not is_plain_file_name(image):
        return False
    return image in existing.get(card_image_folder(image, set_id), ())


def cards_with_files(pairs) -> list:
    """`[has file]` for each `(image, set_id)` of `pairs`, one directory scan per folder."""
    pairs = list(pairs)
    existing = existing_files(card_image_folder(image, set_id)
                              for image, set_id in pairs if image)
    return [card_has_file(image, set_id, existing) for image, set_id in pairs]


def import_legacy(source: str) -> tuple[int, int, int]:
    """Copy `<source>/<folder>/<file>` into the images root (S7, D-Md-3).

    Only regular files (not symlinks) with a plain name, directly inside a
    letters-and-digits folder, are copied; an existing destination is never
    overwritten. Returns (copied, skipped existing, ignored).
    """
    root = images_root()
    copied = skipped = ignored = 0
    for folder_path, dirs, files in os.walk(source):
        dirs.sort()
        relative = os.path.relpath(folder_path, source)
        for name in sorted(files):
            src = os.path.join(folder_path, name)
            if (relative == '.' or os.sep in relative or not is_safe_folder(relative)
                    or not is_plain_file_name(name) or os.path.islink(src)
                    or not os.path.isfile(src)):
                ignored += 1
                continue
            dest = os.path.join(root, relative, name)
            if os.path.lexists(dest):
                skipped += 1
                continue
            if not _inside(root, dest):
                ignored += 1
                continue
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(src, dest)
            copied += 1
    return copied, skipped, ignored
