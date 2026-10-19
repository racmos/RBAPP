"""Every page carries the CSRF token and the fetch wrapper (CSRF-3, CSRF-4).

Static part: every template outside `landing/` extends `base.html`, so one edit
there covers all pages. Rendered part: the pages a browser actually gets.
"""
import re
from pathlib import Path

import pytest

from app import db
from app.models import RbDeck
from tests.auth_helpers import META_TOKEN, form_token, meta_token

TEMPLATES = Path(__file__).resolve().parent.parent / 'app' / 'templates'
NON_LANDING = sorted(
    p for p in TEMPLATES.rglob('*.html')
    if 'landing' not in p.relative_to(TEMPLATES).parts and p.name != 'base.html')

WRAPPER = re.compile(r'<script[^>]*src="/riftbound/static/js/csrf\.js"')


class TestStaticTemplates:
    def test_the_scan_finds_the_templates(self):
        names = {p.relative_to(TEMPLATES).as_posix() for p in NON_LANDING}
        assert {'login.html', 'register.html', 'dashboard.html', 'deck_view.html',
                'errors/404.html'} <= names

    @pytest.mark.parametrize('path', NON_LANDING, ids=lambda p: p.relative_to(TEMPLATES).as_posix())
    def test_extends_base(self, path):
        assert re.search(r'^\s*{%\s*extends\s+"base\.html"\s*%}', path.read_text(encoding='utf-8'))

    def test_base_has_the_meta_tag_and_the_wrapper_in_the_head(self):
        base = (TEMPLATES / 'base.html').read_text(encoding='utf-8')
        head = base.split('</head>')[0]
        assert '<meta name="csrf-token" content="{{ csrf_token() }}">' in head
        assert 'js/csrf.js' in head

    def test_the_wrapper_file_exists(self):
        assert (TEMPLATES.parent / 'static' / 'js' / 'csrf.js').is_file()


@pytest.fixture
def deck_id(admin_client):
    deck = RbDeck(rbdck_user='admin', rbdck_name='Tpl', rbdck_seq=1,
                  rbdck_cards={'main': [], 'sideboard': []}, rbdck_ncards=0)
    db.session.add(deck)
    db.session.commit()
    return deck.id


AUTHENTICATED_PAGES = ['/riftbound/', '/riftbound/set', '/riftbound/card',
                       '/riftbound/collection', '/riftbound/deck', '/riftbound/profile',
                       '/riftbound/price', '/riftbound/no-such-page']


class TestRenderedPages:
    def assert_page(self, resp):
        html = resp.get_data(as_text=True)
        match = META_TOKEN.search(html)
        assert match and match.group(1), 'meta tag missing or empty'
        assert WRAPPER.search(html), 'wrapper script missing'
        assert html.index('csrf.js') < html.index('</head>')
        return html

    @pytest.mark.parametrize('path', ['/riftbound/login', '/riftbound/register'])
    def test_anonymous_pages(self, client, csrf_app, path):
        self.assert_page(client.get(path))

    @pytest.mark.parametrize('path', AUTHENTICATED_PAGES)
    def test_authenticated_pages(self, admin_client, csrf_app, path):
        resp = admin_client.get(path)
        assert resp.status_code in (200, 404)
        self.assert_page(resp)

    def test_deck_view_page(self, admin_client, deck_id, csrf_app):
        resp = admin_client.get(f'/riftbound/deck/view/{deck_id}')
        assert resp.status_code == 200
        self.assert_page(resp)

    def test_error_pages(self, other_user_client, csrf_app):
        forbidden = other_user_client.get('/riftbound/price')
        assert forbidden.status_code == 403
        self.assert_page(forbidden)

    def test_the_token_is_the_same_on_every_page_of_a_session(self, admin_client, csrf_app):
        first = meta_token(admin_client, '/riftbound/')
        assert meta_token(admin_client, '/riftbound/set') == first

    def test_pages_render_with_csrf_off_too(self, admin_client):
        self.assert_page(admin_client.get('/riftbound/'))


class TestLogoutControl:
    def nav(self, client):
        html = client.get('/riftbound/').get_data(as_text=True)
        return html, html.split('</nav>')[0]

    def test_logout_is_a_post_form_with_a_token(self, admin_client, csrf_app):
        html, nav = self.nav(admin_client)
        match = re.search(r'<form[^>]*method="post"[^>]*action="/riftbound/logout"[^>]*>(.*?)</form>',
                          nav, re.S | re.I)
        assert match, 'logout is not a POST form inside the nav'
        assert form_token(match.group(1)) == meta_token(admin_client, '/riftbound/')

    def test_no_link_points_at_logout(self, admin_client, csrf_app):
        html, _ = self.nav(admin_client)
        assert not re.search(r'<a\b[^>]*href="[^"]*/logout"', html)

    def test_login_and_register_forms_have_the_hidden_field(self, client, csrf_app):
        for path in ('/riftbound/login', '/riftbound/register'):
            assert form_token(client.get(path).get_data(as_text=True)), path
