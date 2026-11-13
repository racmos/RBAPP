"""Every backend error code can be translated by the frontend (M-c S4; English only since S21).

Only committed JSON is read: no Node, no network.
"""
import json
from pathlib import Path

import pytest

from app.api.error_codes import ErrorCode

LOCALES = Path(__file__).resolve().parent.parent / 'frontend' / 'src' / 'i18n' / 'locales'


def _codes():
    return json.loads((LOCALES / 'en' / 'errors.json').read_text(encoding='utf-8'))['code']


def test_english_is_the_only_catalog():
    assert sorted(path.name for path in LOCALES.iterdir() if path.is_dir()) == ['en']


@pytest.mark.parametrize('code', [c.value for c in ErrorCode])
def test_every_error_code_has_a_catalog_entry(code):
    entry = _codes().get(code)
    assert isinstance(entry, str) and entry.strip(), f'errors.json[en] lacks code.{code}'


@pytest.mark.parametrize('code, text', [
    ('image_invalid', 'That file is not a supported image. Use a JPEG, PNG, WebP or GIF of at '
                      'least 64 by 64 pixels.'),
    ('file_too_large', 'The file is too large (maximum {{max_mb}} MB).'),
])
def test_the_avatar_codes_have_their_text(code, text):
    """F9-c S11."""
    assert ErrorCode(code).value == code
    assert _codes()[code] == text
