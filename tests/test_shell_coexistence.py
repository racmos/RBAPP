"""SHELL-10: the Jinja pages coexist with the new app and carry the new product name.

Task 5.34 pins what must not change (the landing page, the list of pages); 5.35 adds the
"Nueva app" link and the rename. The assertions look at `<title>` and at the brand text only,
never at whole pages.
"""
import re

import pytest

from tests.conftest import login_as

OLD_NAME = 'Riftbound Manager'
NEW_NAME = 'Rift Manager'

# (label, path, needs an admin). Every Jinja page except the landing `/`.
PAGES = [
    ('login', '/riftbound/login', False),
    ('register', '/riftbound/register', False),
    ('dashboard', '/riftbound/', False),
    ('set', '/riftbound/set', False),
    ('card', '/riftbound/card', False),
    ('collection', '/riftbound/collection', False),
    ('deck', '/riftbound/deck', False),
    ('price', '/riftbound/price', True),
    ('profile', '/riftbound/profile', False),
]
ANONYMOUS_PAGES = [page for page in PAGES if page[0] in ('login', 'register')]
SIGNED_IN_PAGES = [page for page in PAGES if page[0] not in ('login', 'register')]


def _title(html):
    match = re.search(r'<title>(.*?)</title>', html, re.DOTALL)
    assert match, 'the page has no <title>'
    return match.group(1).strip()


class TestLandingIsUntouched:
    """5.34 CHAR: `GET /` is pinned by stable markers; it changes only in F11."""

    def test_the_landing_page_is_served_as_it_was(self, client):
        response = client.get('/')
        html = response.get_data(as_text=True)
        assert response.status_code == 200
        assert _title(html) == 'DEMACIA HONOR — Riftbound TCG'
        assert 'Noticias Riftbound' in html

    def test_the_landing_page_knows_nothing_of_the_new_app(self, client):
        html = client.get('/').get_data(as_text=True)
        assert 'Nueva app' not in html
        assert '/riftbound/app/' not in html
        assert NEW_NAME not in html


class TestPagesList:
    """5.34 CHAR: the nine Jinja pages exist and answer."""

    @pytest.mark.parametrize('label,path', [(p[0], p[1]) for p in ANONYMOUS_PAGES])
    def test_anonymous_pages_answer(self, client, label, path):
        assert client.get(path).status_code == 200

    @pytest.mark.parametrize('label,path', [(p[0], p[1]) for p in SIGNED_IN_PAGES if not p[2]])
    def test_signed_in_pages_answer(self, make_user, client, label, path):
        make_user('ada')
        login_as(client, 'ada')
        assert client.get(path).status_code == 200

    def test_the_price_page_answers_for_an_admin(self, make_user, client):
        make_user('root', is_admin=True)
        login_as(client, 'root')
        assert client.get('/riftbound/price').status_code == 200


class TestNewAppLink:
    """5.35: base.html offers the way into the SPA."""

    def test_the_dashboard_links_to_the_new_app(self, make_user, client):
        make_user('ada')
        login_as(client, 'ada')
        html = client.get('/riftbound/').get_data(as_text=True)
        assert re.search(r'<a\s+href="/riftbound/app/"[^>]*>\s*Nueva app\s*</a>', html)

    def test_every_signed_in_page_has_the_link(self, make_user, client):
        make_user('ada')
        login_as(client, 'ada')
        for label, path, admin in SIGNED_IN_PAGES:
            if admin:
                continue
            html = client.get(path).get_data(as_text=True)
            assert 'href="/riftbound/app/"' in html, label

    def test_the_link_is_for_signed_in_users_only(self, client):
        html = client.get('/riftbound/login').get_data(as_text=True)
        assert 'Nueva app' not in html


class TestProductName:
    """5.35: titles and brand text say "Rift Manager"."""

    @pytest.mark.parametrize('label,path', [(p[0], p[1]) for p in ANONYMOUS_PAGES])
    def test_anonymous_page_titles(self, client, label, path):
        html = client.get(path).get_data(as_text=True)
        assert NEW_NAME in _title(html)
        assert OLD_NAME not in html

    @pytest.mark.parametrize('label,path', [(p[0], p[1]) for p in SIGNED_IN_PAGES if not p[2]])
    def test_signed_in_page_titles_and_brand(self, make_user, client, label, path):
        make_user('ada')
        login_as(client, 'ada')
        html = client.get(path).get_data(as_text=True)
        assert _title(html).endswith(NEW_NAME)
        assert re.search(r'class="logo">\s*Rift Manager\s*</a>', html)
        assert OLD_NAME not in html

    def test_the_price_page_title(self, make_user, client):
        make_user('root', is_admin=True)
        login_as(client, 'root')
        html = client.get('/riftbound/price').get_data(as_text=True)
        assert _title(html) == 'Price Generation - Rift Manager'
        assert OLD_NAME not in html

    def test_the_deck_view_title(self, make_user, client):
        from app import db
        from app.models import RbDeck
        make_user('ada')
        deck = RbDeck(rbdck_user='ada', rbdck_name='Mono Red', rbdck_seq=1,
                      rbdck_cards={'main': [], 'sideboard': []}, rbdck_ncards=0)
        db.session.add(deck)
        db.session.commit()
        login_as(client, 'ada')
        html = client.get(f'/riftbound/deck/view/{deck.id}').get_data(as_text=True)
        assert _title(html) == 'Mono Red - Rift Manager'
