"""F5-g: share link of a deck (POST/DELETE /decks/<id>/share, U) and the public read-only
deck (GET /public/decks/<slug>, P, rate limited, never cached)."""
import re

import pytest

from app import db
from app.models import RbCardBan, RbCollection, RbDeckHead
from app.services import deck_share
from tests.deck_api_helpers import (AZIR, BASE, NOT_FOUND, data, head_row, make_deck,
                                    seed_catalog)
from tests.product_helpers import count_statements

PUBLIC = '/riftbound/api/v1/public/decks'
SLUG = re.compile(r'^[A-Za-z0-9_-]{22}$')
PUBLIC_KEYS = ['name', 'mode', 'visibility', 'owner', 'updated_at', 'content', 'cards',
               'unknown_cards', 'domains', 'counts', 'value', 'value_unpriced', 'legality']
PUBLIC_CONTENT_KEYS = ['v', 'legend', 'champion', 'main', 'runes', 'battlefields', 'sideboard']
CARD_KEYS = ['set_id', 'card_id', 'key', 'name', 'domains', 'type', 'supertype', 'rarity',
             'image_src', 'image_thumb_src', 'is_base', 'market', 'owned_total', 'tags',
             'energy', 'power', 'might', 'variants', 'keywords']  # F5-i


@pytest.fixture
def api(app, authenticated_client, make_user):
    make_user('otheruser')
    seed_catalog()
    return authenticated_client


@pytest.fixture
def anon(app):
    """A client with no cookie at all."""
    return app.test_client()


def _share(api, deck_id):
    return data(api.post(f'{BASE}/{deck_id}/share'))


def _ban(name, mode):
    from datetime import date
    from app.services.bans import name_key
    db.session.add(RbCardBan(rbban_name_key=name_key(name), rbban_name=name, rbban_mode=mode,
                             rbban_since=date(2026, 1, 1)))
    db.session.commit()


class TestShare:
    def test_gives_a_22_character_url_safe_slug_and_its_app_url(self, api):
        deck_id = make_deck('Azir', AZIR)
        share = _share(api, deck_id)
        assert list(share) == ['slug', 'url']
        assert SLUG.match(share['slug'])
        assert share['url'] == f"http://localhost/riftbound/app/d/{share['slug']}"
        assert head_row(deck_id).rbdkh_share_slug == share['slug']

    def test_the_url_follows_the_request_host(self, app, api):
        deck_id = make_deck('Azir', AZIR)
        host = 'https://rift.example'
        client = app.test_client()
        client.post('/riftbound/login', base_url=host,
                    data={'username': 'testuser', 'password': 'testpass123'})
        share = data(client.post(f'{BASE}/{deck_id}/share', base_url=host))
        assert share['url'] == f"https://rift.example/riftbound/app/d/{share['slug']}"

    def test_sharing_again_returns_the_same_slug_and_keeps_updated_at(self, api):
        deck_id = make_deck('Azir', AZIR)
        before = head_row(deck_id).rbdkh_updated_at
        first = _share(api, deck_id)
        assert _share(api, deck_id) == first
        assert head_row(deck_id).rbdkh_updated_at == before

    def test_slugs_are_different_per_deck(self, api):
        slugs = {_share(api, make_deck(f'Deck {n}'))['slug'] for n in range(5)}
        assert len(slugs) == 5

    def test_a_colliding_slug_is_drawn_again(self, api, monkeypatch):
        taken = make_deck('Taken')
        head = head_row(taken)
        head.rbdkh_share_slug = 'A' * 22
        db.session.commit()
        draws = iter(['A' * 22, 'B' * 22])
        monkeypatch.setattr(deck_share.secrets, 'token_urlsafe', lambda n: next(draws))
        assert _share(api, make_deck('Azir'))['slug'] == 'B' * 22

    def test_the_deck_detail_and_list_carry_the_share(self, api):
        shared, plain = make_deck('Shared', AZIR), make_deck('Plain')
        share = _share(api, shared)
        assert data(api.get(f'{BASE}/{shared}'))['share'] == share
        assert data(api.get(f'{BASE}/{plain}'))['share'] is None
        items = {item['id']: item for item in data(api.get(BASE))['items']}
        assert items[shared]['share'] == share and items[plain]['share'] is None

    def test_another_users_deck_and_unknown_ids_are_404_and_unchanged(self, api):
        theirs = make_deck('Azir', user='otheruser')
        for deck_id in (theirs, theirs + 100):
            for method in ('post', 'delete'):
                resp = getattr(api, method)(f'{BASE}/{deck_id}/share')
                assert resp.status_code == 404 and resp.get_json() == NOT_FOUND
        assert head_row(theirs).rbdkh_share_slug is None

    def test_another_user_cannot_revoke_my_link(self, app, api, make_user):
        from tests.conftest import login_as
        deck_id = make_deck('Azir', AZIR)
        slug = _share(api, deck_id)['slug']
        other = login_as(app.test_client(), 'otheruser')
        assert other.delete(f'{BASE}/{deck_id}/share').status_code == 404
        assert head_row(deck_id).rbdkh_share_slug == slug

    def test_anonymous_is_401(self, api, anon):
        deck_id = make_deck('Azir')
        for method in ('post', 'delete'):
            assert getattr(anon, method)(f'{BASE}/{deck_id}/share').status_code == 401


class TestRevoke:
    def test_revoking_clears_the_slug_and_the_old_url_is_404_at_once(self, api, anon):
        deck_id = make_deck('Azir', AZIR)
        slug = _share(api, deck_id)['slug']
        assert anon.get(f'{PUBLIC}/{slug}').status_code == 200
        assert data(api.delete(f'{BASE}/{deck_id}/share')) == {'share': None}
        assert head_row(deck_id).rbdkh_share_slug is None
        resp = anon.get(f'{PUBLIC}/{slug}')
        assert resp.status_code == 404 and resp.get_json() == NOT_FOUND
        assert data(api.get(f'{BASE}/{deck_id}'))['share'] is None

    def test_revoking_a_deck_that_is_not_shared_is_a_no_op(self, api):
        deck_id = make_deck('Azir')
        assert data(api.delete(f'{BASE}/{deck_id}/share')) == {'share': None}

    def test_sharing_again_gives_a_new_slug_and_the_old_one_stays_dead(self, api, anon):
        deck_id = make_deck('Azir', AZIR)
        old = _share(api, deck_id)['slug']
        api.delete(f'{BASE}/{deck_id}/share')
        new = _share(api, deck_id)['slug']
        assert new != old and SLUG.match(new)
        assert anon.get(f'{PUBLIC}/{old}').status_code == 404
        assert anon.get(f'{PUBLIC}/{new}').status_code == 200

    def test_deleting_the_deck_kills_its_link(self, api, anon):
        deck_id = make_deck('Azir', AZIR)
        slug = _share(api, deck_id)['slug']
        data(api.delete(f'{BASE}/{deck_id}'))
        assert anon.get(f'{PUBLIC}/{slug}').status_code == 404


class TestPublicDeck:
    def test_anonymous_reads_a_shared_private_deck_without_its_owner(self, api, anon):
        db.session.add(RbCollection(rbcol_rbset_id='OGN', rbcol_rbcar_id='L1', rbcol_foil='N',
                                    rbcol_user='testuser', rbcol_quantity=2))
        db.session.commit()
        deck_id = make_deck('Azir', AZIR)
        slug = _share(api, deck_id)['slug']
        mine = data(api.get(f'{BASE}/{deck_id}'))
        resp = anon.get(f'{PUBLIC}/{slug}')
        deck = data(resp)
        assert list(deck) == PUBLIC_KEYS
        assert deck['owner'] is None
        assert (deck['name'], deck['mode'], deck['visibility']) == ('Azir', '1v1', 'private')
        assert deck['updated_at'] == mine['updated_at']
        assert list(deck['content']) == PUBLIC_CONTENT_KEYS
        assert deck['content'] == {k: v for k, v in AZIR.items() if k != 'workbench'}
        # Fury Bolt and the token are only in the workbench: never shown.
        assert sorted(deck['cards']) == sorted({
            'OGN-L1', 'OGN-C1', 'OGN-U1', 'SFD-U1', 'OGN-S1', 'OGN-R1', 'OGN-R2', 'OGN-B1',
            'OGN-B2', 'OGN-U2'})
        legend = deck['cards']['OGN-L1']
        assert list(legend) == CARD_KEYS
        assert legend['owned_total'] is None and legend['market'] == 5
        assert deck['unknown_cards'] == []
        assert deck['domains'] == ['Calm', 'Order']
        assert deck['counts'] == {'main': 6, 'runes': 12, 'battlefields': 2, 'sideboard': 2}
        assert deck['value'] == mine['value'] == 21.8 and deck['value_unpriced'] == 10
        assert deck['legality'] == mine['legality']
        assert list(deck['legality']['1v1']) == ['legal', 'issues', 'completeness']

    def test_a_public_deck_names_its_owner(self, api, anon):
        deck_id = make_deck('Azir', AZIR)
        data(api.patch(f'{BASE}/{deck_id}', json={'visibility': 'public'}))
        deck = data(anon.get(f"{PUBLIC}/{_share(api, deck_id)['slug']}"))
        assert deck['visibility'] == 'public' and deck['owner'] == {'username': 'testuser'}

    def test_no_cookie_no_cache_and_no_private_data(self, api, anon):
        deck_id = make_deck('Azir', AZIR)
        data(api.patch(f'{BASE}/{deck_id}', json={'visibility': 'public'}))
        other = make_deck('Other')
        other_slug = _share(api, other)['slug']
        slug = _share(api, deck_id)['slug']
        resp = anon.get(f'{PUBLIC}/{slug}')
        assert resp.status_code == 200
        assert 'Set-Cookie' not in resp.headers
        assert resp.headers['Cache-Control'] == 'no-store'
        text = resp.get_data(as_text=True)
        for secret in ('test@test.com', slug, other_slug, 'user_id', 'email', 'note',
                       'current_seq', 'created_at', 'workbench'):
            assert secret not in text

    @pytest.mark.parametrize('slug', ['A' * 22, 'short', 'A' * 23, 'A' * 21 + '.', 'A' * 21 + '~'])
    def test_unknown_or_malformed_slugs_are_the_same_404(self, api, anon, slug):
        make_deck('Azir', AZIR)
        resp = anon.get(f'{PUBLIC}/{slug}')
        assert resp.status_code == 404 and resp.get_json() == NOT_FOUND
        assert resp.headers['Cache-Control'] == 'no-store'
        assert 'Set-Cookie' not in resp.headers

    def test_signed_in_users_read_it_too(self, app, api, make_user):
        from tests.conftest import login_as
        slug = _share(api, make_deck('Azir', AZIR))['slug']
        other = login_as(app.test_client(), 'otheruser')
        assert data(other.get(f'{PUBLIC}/{slug}'))['owner'] is None

    def test_legality_uses_the_bans_of_the_moment(self, api, anon):
        slug = _share(api, make_deck('Azir', AZIR))['slug']
        assert data(anon.get(f'{PUBLIC}/{slug}'))['legality']['1v1']['issues'][-1][
            'code'] == 'sideboard_size'
        _ban('Azir, Emperor', '1v1')
        assert data(anon.get(f'{PUBLIC}/{slug}'))['legality']['1v1']['issues'][-1] == {
            'code': 'banned', 'params': {'name': 'Azir, Emperor', 'mode': '1v1'}}

    def test_sql_statements(self, app, api, anon):
        slug = _share(api, make_deck('Azir', AZIR))['slug']
        resp, count = count_statements(app, lambda: anon.get(f'{PUBLIC}/{slug}'))
        assert resp.status_code == 200
        # head + owner, current version, cards, sets, bans, prices (2); no owned copies
        assert count == 7

    def test_a_malformed_slug_never_reaches_the_database(self, app, api, anon):
        resp, count = count_statements(app, lambda: anon.get(f'{PUBLIC}/short'))
        assert resp.status_code == 404 and count == 0

    def test_writes_are_not_allowed(self, api, anon):
        slug = _share(api, make_deck('Azir', AZIR))['slug']
        assert anon.post(f'{PUBLIC}/{slug}').status_code == 405
        assert RbDeckHead.query.count() == 1


class TestRateLimit:
    def test_the_61st_request_in_a_minute_is_429(self, limited_app, api, anon):
        slug = _share(api, make_deck('Azir', AZIR))['slug']
        for _ in range(60):
            assert anon.get(f'{PUBLIC}/{slug}').status_code == 200
        resp = anon.get(f'{PUBLIC}/{slug}')
        assert resp.status_code == 429
        body = resp.get_json()
        assert body['success'] is False and body['error'] == 'Too Many Requests'
        assert body['code'] == 'rate_limited' and int(resp.headers['Retry-After']) >= 1

    def test_unknown_slugs_count_too(self, limited_app, api, anon):
        for _ in range(60):
            assert anon.get(f"{PUBLIC}/{'A' * 22}").status_code == 404
        assert anon.get(f"{PUBLIC}/{'B' * 22}").status_code == 429
