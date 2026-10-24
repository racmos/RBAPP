"""Every backend error code can be translated in both frontend languages (M-c S4).

Only committed JSON is read: no Node, no network.
"""
import json
from pathlib import Path

import pytest

from app.api.error_codes import ErrorCode

LOCALES = Path(__file__).resolve().parent.parent / 'frontend' / 'src' / 'i18n' / 'locales'


def _codes(lang):
    return json.loads((LOCALES / lang / 'errors.json').read_text(encoding='utf-8'))['code']


@pytest.mark.parametrize('lang', ('es', 'en'))
@pytest.mark.parametrize('code', [c.value for c in ErrorCode])
def test_every_error_code_has_a_catalog_entry(lang, code):
    entry = _codes(lang).get(code)
    assert isinstance(entry, str) and entry.strip(), f'errors.json[{lang}] lacks code.{code}'
