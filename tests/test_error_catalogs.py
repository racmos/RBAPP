"""Every backend error code can be translated by the frontend (M-c S4; English only since S21).

Only committed JSON is read: no Node, no network.
"""
import json
from pathlib import Path

import pytest

from app.api.error_codes import DetailCode, ErrorCode

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


def test_the_mfa_invalid_code_has_its_text():
    """F9-d S17."""
    assert ErrorCode('mfa_invalid').value == 'mfa_invalid'
    assert _codes()['mfa_invalid'] == ('That code is not valid. Check your authenticator app '
                                       'and try again.')


def test_the_mfa_expired_code_has_its_text():
    """F9-e S9."""
    assert ErrorCode('mfa_expired').value == 'mfa_expired'
    assert _codes()['mfa_expired'] == 'The sign-in step expired. Sign in again.'


@pytest.mark.parametrize('code, text', [
    ('api_key_invalid', 'The API key is not valid.'),
    ('api_key_read_only', 'API keys can only read data.'),
])
def test_the_api_key_codes_have_their_text(code, text):
    """F9-h S13."""
    assert ErrorCode(code).value == code
    assert _codes()[code] == text


def _validation():
    return json.loads((LOCALES / 'en' / 'errors.json').read_text(encoding='utf-8'))['validation']


@pytest.mark.parametrize('code', [c.value for c in DetailCode])
def test_every_detail_code_has_a_catalog_entry(code):
    """F13-h S10: a field error is translated by its code (`validation.<code>`)."""
    entry = _validation().get(code)
    assert isinstance(entry, str) and entry.strip(), f'errors.json[en] lacks validation.{code}'


@pytest.mark.parametrize('code, text', [
    ('too_small', 'The image is too small: its short side must be at least {{min}} px.'),
    ('invalid_format', 'That file is not a supported image. Use a PNG, JPEG or WebP image.'),
    ('out_of_range', 'The image is too large (at most 10 MB and 25 megapixels).'),
])
def test_the_image_upload_codes_have_their_text(code, text):
    """F13-h S4, S10: the upload refusals on the field `file`."""
    assert DetailCode(code).value == code
    assert _validation()['file'][code] == text
    assert _validation()['too_small'] == 'The image is too small (at least {{min}} px).'
