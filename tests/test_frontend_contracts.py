"""Contracts between the Python lane and the frontend lane (D25).

Only committed JSON is read: no Node, no network (CI-9 "No Node in pytest").
"""
import json
import re
from pathlib import Path

import pytest

from app.api.error_codes import DetailCode, ErrorCode

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / 'frontend'
LANGUAGES = ('es', 'en')


def _requirements_pin(name):
    for line in (ROOT / 'requirements.txt').read_text().splitlines():
        match = re.match(rf'^{re.escape(name)}==(\S+)', line.strip(), re.IGNORECASE)
        if match:
            return match.group(1)
    raise AssertionError(f'{name} is not pinned in requirements.txt')


def _errors_catalog(lang):
    path = FRONTEND / 'src' / 'i18n' / 'locales' / lang / 'errors.json'
    return json.loads(path.read_text(encoding='utf-8'))


class TestAltchaPin:
    """FAUTH-4: the JS widget and the Python verifier speak the same PoW version."""

    def test_the_python_pin_is_an_exact_version(self):
        assert re.fullmatch(r'\d+\.\d+\.\d+', _requirements_pin('altcha'))

    def test_package_json_pins_the_same_version(self):
        manifest = json.loads((FRONTEND / 'package.json').read_text(encoding='utf-8'))
        assert manifest['dependencies']['altcha'] == _requirements_pin('altcha')

    def test_the_lockfile_resolves_the_same_version(self):
        lock = json.loads((FRONTEND / 'package-lock.json').read_text(encoding='utf-8'))
        assert lock['packages']['node_modules/altcha']['version'] == _requirements_pin('altcha')
        assert lock['packages']['']['dependencies']['altcha'] == _requirements_pin('altcha')


class TestErrorCodeCatalogs:
    """I18N-1/4: every backend error code can be translated in both languages."""

    @pytest.mark.parametrize('lang', LANGUAGES)
    @pytest.mark.parametrize('code', [c.value for c in ErrorCode])
    def test_every_error_code_has_a_catalog_entry(self, lang, code):
        entry = _errors_catalog(lang)['code'].get(code)
        assert isinstance(entry, str) and entry.strip(), f'errors.json[{lang}] lacks code.{code}'

    @pytest.mark.parametrize('lang', LANGUAGES)
    @pytest.mark.parametrize('code', [c.value for c in DetailCode])
    def test_every_validation_detail_code_has_a_catalog_entry(self, lang, code):
        entry = _errors_catalog(lang)['validation'].get(code)
        assert isinstance(entry, str) and entry.strip(), f'errors.json[{lang}] lacks validation.{code}'

    @pytest.mark.parametrize('lang', LANGUAGES)
    def test_the_catalog_has_no_entry_for_a_code_the_backend_dropped(self, lang):
        known = {c.value for c in ErrorCode}
        assert set(_errors_catalog(lang)['code']) <= known


LEGACY_ROUTES = FRONTEND / 'src' / 'shell' / 'legacy-routes.json'

# The Jinja pages the app shell links to, with the Flask endpoint that must answer each URL.
LEGACY_ENDPOINTS = {
    'dashboard': 'main.dashboard',
    'sets': 'sets.sets',
    'cards': 'cards.cards',
    'collection': 'collection.collection',
    'decks': 'deck.deck',
    'profile': 'profile.profile',
    'price': 'price.price',
}


def _legacy_routes():
    return json.loads(LEGACY_ROUTES.read_text(encoding='utf-8'))


class TestLegacyRoutes:
    """SHELL-5 (D25): the URLs the shell links to are real Flask GET routes."""

    def test_the_file_lists_every_module_of_the_hub(self):
        assert set(_legacy_routes()) == set(LEGACY_ENDPOINTS)

    @pytest.mark.parametrize('key', sorted(LEGACY_ENDPOINTS))
    def test_every_url_matches_a_get_rule_of_the_url_map(self, app, key):
        url = _legacy_routes()[key]
        assert url.startswith('/riftbound/')
        endpoint, _args = app.url_map.bind('localhost').match(url, method='GET')
        assert endpoint == LEGACY_ENDPOINTS[key]

    def test_a_url_that_does_not_exist_is_caught(self, app):
        from werkzeug.exceptions import NotFound
        with pytest.raises(NotFound):
            app.url_map.bind('localhost').match('/riftbound/no-such-page', method='GET')


class TestDocs:
    """PWA-5 'Documented': the rollback of the service worker is written down (task 6.21)."""

    @staticmethod
    def _docs():
        return (ROOT / 'docs' / 'frontend.md').read_text(encoding='utf-8')

    @staticmethod
    def _section(text, heading):
        match = re.search(rf'^## {re.escape(heading)}\n(.*?)(?=^## |\Z)', text, re.S | re.M)
        assert match, f'docs/frontend.md has no "## {heading}" section'
        return match.group(1)

    def test_it_describes_the_self_destroying_rollback(self):
        text = self._docs()
        assert 'self-destroying' in text.lower()
        rollback = self._section(text, 'Rolling back the PWA')
        assert 'VITE_PWA_SELF_DESTROY=true' in rollback
        assert 'revert' in rollback.lower()
        assert 'wait' in rollback.lower()
        assert 'plain revert' in rollback.lower()

    def test_the_rollback_steps_come_in_order(self):
        rollback = self._section(self._docs(), 'Rolling back the PWA')
        build = rollback.index('VITE_PWA_SELF_DESTROY=true')
        wait = rollback.lower().index('wait')
        revert = rollback.lower().index('revert', wait)
        assert build < wait < revert

    def test_it_documents_the_service_worker_scope_and_the_icons(self):
        text = self._docs()
        assert '/riftbound/app/sw.js' in text
        assert '/riftbound/app/' in self._section(text, 'Service worker and install')
        assert 'npm run icons' in text
        assert 'frontend/public' in text

    def test_it_has_a_device_checklist(self):
        checklist = self._section(self._docs(), 'PWA device checklist')
        for word in ('Android', 'iPhone', 'Lighthouse', 'offline', 'update'):
            assert word.lower() in checklist.lower(), word
