"""F5-f: GET /decks/<id>/vs-collection and POST /decks/<id>/missing-to-wishlist (F5-R11 and its
2026-11-11 amendment; owner decision 5 of docs/requirements/F3/F3-f-wishlists-design.md).

Copies count per card NAME across printings (DECK-1); the workbench is not part of the deck.
Catalog and prices: tests/deck_api_helpers.py (AZIR: legend 5, champion 10, Shurima Guard
OGN/U1 2 and SFD/U1 1, Sandstorm unpriced, Calm Rune 0.1, Order Rune unpriced, Field 1 0.2,
Field 2 unpriced, Desert Scout 0.5).
"""
from datetime import datetime

import pytest

from app import db
from app.models import RbCard, RbCollection, RbDeckVersion, RbWishlist, RbWishlistLine
from app.services.bans import name_key
from tests.conftest import login_as
from tests.deck_api_helpers import (AZIR, BASE, NOT_FOUND, content, data, line, make_deck, ref,
                                    seed_catalog, user_id, versions)
from tests.product_helpers import count_statements

WISHLISTS = '/riftbound/api/v1/wishlists'
VS_KEYS = ['missing', 'complete', 'names', 'cost_eur', 'owned_value', 'unpriced']
ITEM_KEYS = ['card', 'zone', 'need', 'have', 'missing']
RESULT_KEYS = ['wishlist', 'added', 'merged', 'unchanged', 'skipped', 'total_missing_names']
CARD_MINI_KEYS = ['set_id', 'card_id', 'key', 'name', 'domains', 'type', 'supertype', 'rarity',
                  'image_src', 'image_thumb_src', 'is_base', 'market', 'owned_total']

# AZIR with nothing owned: names in section order, then by name inside a section.
AZIR_MISSING = [
    ('OGN-L1', 'legend', 1), ('OGN-C1', 'champion', 1),
    ('OGN-S1', 'main', 3), ('OGN-U1', 'main', 3),
    ('OGN-R1', 'runes', 6), ('OGN-R2', 'runes', 6),
    ('OGN-B1', 'battlefields', 1), ('OGN-B2', 'battlefields', 1),
    ('OGN-U2', 'sideboard', 2)]


@pytest.fixture
def api(app, authenticated_client, make_user):
    make_user('otheruser')
    seed_catalog()
    return authenticated_client


def own(set_id, card_id, qty, *, foil='N', user='testuser', sell=0):
    db.session.add(RbCollection(
        rbcol_rbset_id=set_id, rbcol_rbcar_id=card_id, rbcol_foil=foil, rbcol_user=user,
        rbcol_quantity=qty, rbcol_condition='NM', rbcol_language='English',
        rbcol_selling='Y' if sell else 'N', rbcol_sell_qty=sell,
        rbcol_chadat=datetime(2026, 10, 1, 9, 0)))
    db.session.commit()


def vs(api, deck_id):
    return data(api.get(f'{BASE}/{deck_id}/vs-collection'))


def rows(result):
    return [(item['card']['key'], item['zone'], item['missing']) for item in result['missing']]


def fillers(count, start=100):
    ids = [f'X{n}' for n in range(start, start + count)]
    db.session.add_all([RbCard(rbcar_rbset_id='OGN', rbcar_id=card_id,
                               rbcar_name=f'Filler {card_id}', rbcar_type='Unit',
                               rbcar_domain='Calm', rbcar_rarity='Common') for card_id in ids])
    db.session.commit()
    return ids


def wish_lines(list_id):
    db.session.expire_all()
    return [(l.rbwsl_name_key, l.rbwsl_rbset_id, l.rbwsl_rbcar_id, l.rbwsl_foil, l.rbwsl_qty,
             l.rbwsl_max_price, l.rbwsl_note)
            for l in RbWishlistLine.query.filter_by(rbwsl_list_id=list_id)
            .order_by(RbWishlistLine.rbwsl_id)]


def lists_of(name='testuser'):
    db.session.expire_all()
    return RbWishlist.query.filter_by(rbwls_user_id=user_id(name)).order_by(
        RbWishlist.rbwls_position).all()


def to_wishlist(api, deck_id, body=None, status=200):
    resp = (api.post(f'{BASE}/{deck_id}/missing-to-wishlist', json=body) if body is not None
            else api.post(f'{BASE}/{deck_id}/missing-to-wishlist'))
    return data(resp, status)


# --- GET /decks/<id>/vs-collection -----------------------------------------------------------

class TestVsCollection:
    def test_nothing_owned_lists_every_name_of_the_deck(self, api):
        deck_id = make_deck('Azir', AZIR)
        result = vs(api, deck_id)
        assert list(result) == VS_KEYS
        assert rows(result) == AZIR_MISSING
        first = result['missing'][0]
        assert list(first) == ITEM_KEYS and list(first['card']) == CARD_MINI_KEYS
        assert (first['need'], first['have'], first['missing']) == (1, 0, 1)
        assert result['complete'] == 0 and result['names'] == 9
        # 5 + 10 + 3 x 2 (OGN/U1, the first printing in the deck) + 6 x 0.1 + 0.2 + 2 x 0.5
        assert result['cost_eur'] == 22.8
        assert result['unpriced'] == 3                  # Sandstorm, Order Rune, Field 2
        assert result['owned_value'] == 0

    def test_need_counts_a_name_across_printings_and_zones_without_the_workbench(self, api):
        body = content(main=[line('OGN', 'U1', 2), line('SFD', 'U1', 1)],
                       sideboard=[line('SFD', 'U1', 1), line('OGN', 'U2', 1)],
                       workbench=[line('OGN', 'U1', 3), line('OGN', 'F1', 2),
                                  line('OGN', 'U2', 2)])
        result = vs(api, make_deck('Guards', body))
        guard = result['missing'][0]
        assert guard['card']['key'] == 'OGN-U1' and guard['zone'] == 'main'
        assert (guard['need'], guard['have'], guard['missing']) == (4, 0, 4)
        assert rows(result) == [('OGN-U1', 'main', 4), ('OGN-U2', 'sideboard', 1)]
        assert result['names'] == 2

    def test_have_counts_every_printing_foil_and_for_sale_copies(self, api):
        own('SFD', 'U1', 1, foil='S')
        own('OGN', 'U1', 1, sell=1)
        own('OGN', 'L1', 1)
        own('OGN', 'U2', 5)
        own('OGN', 'U1', 9, user='otheruser')          # another user's copies never count
        result = vs(api, make_deck('Azir', AZIR))
        guard = next(i for i in result['missing'] if i['card']['key'] == 'OGN-U1')
        assert (guard['need'], guard['have'], guard['missing']) == (3, 2, 1)
        assert [key for key, _z, _m in rows(result)] == [
            'OGN-C1', 'OGN-S1', 'OGN-U1', 'OGN-R1', 'OGN-R2', 'OGN-B1', 'OGN-B2']
        assert result['complete'] == 2 and result['names'] == 9
        # 10 + 1 x 2 + 6 x 0.1 + 0.2
        assert result['cost_eur'] == 12.8 and result['unpriced'] == 3
        # min(need, have) x price: legend 5 + Shurima Guard 2 x 2 + Desert Scout 2 x 0.5
        assert result['owned_value'] == 10

    def test_a_fully_owned_deck_has_nothing_missing(self, api):
        body = content(legend=ref('OGN', 'L1'), main=[line('OGN', 'U1', 3)])
        own('OGN', 'L1', 2)
        own('SFD', 'U1', 3)
        result = vs(api, make_deck('Mine', body))
        assert result == {'missing': [], 'complete': 2, 'names': 2, 'cost_eur': 0,
                          'owned_value': 11, 'unpriced': 0}

    def test_an_empty_deck(self, api):
        assert vs(api, make_deck('Empty')) == {'missing': [], 'complete': 0, 'names': 0,
                                                'cost_eur': 0, 'owned_value': 0, 'unpriced': 0}

    def test_cards_missing_from_the_catalog_are_left_out(self, api):
        body = content(main=[line('OGN', 'ZZ', 2), line('OGN', 'U2', 1)])
        result = vs(api, make_deck('Odd', body))
        assert rows(result) == [('OGN-U2', 'main', 1)] and result['names'] == 1

    def test_reads_the_current_version(self, api):
        deck_id = make_deck('Azir', content(main=[line('OGN', 'U2', 1)]), seqs=(1, 2))
        first = RbDeckVersion.query.filter_by(rbdkv_deck_id=deck_id, rbdkv_seq=1).one()
        first.rbdkv_content = AZIR
        db.session.commit()
        assert rows(vs(api, deck_id)) == [('OGN-U2', 'main', 1)]

    def test_another_users_deck_and_unknown_ids_are_404(self, api):
        theirs = make_deck('Azir', AZIR, user='otheruser')
        for deck_id in (theirs, theirs + 100):
            resp = api.get(f'{BASE}/{deck_id}/vs-collection')
            assert resp.status_code == 404 and resp.get_json() == NOT_FOUND

    def test_anonymous_is_401(self, app, api):
        deck_id = make_deck('Azir', AZIR)
        resp = app.test_client().get(f'{BASE}/{deck_id}/vs-collection')
        assert resp.status_code == 401 and resp.get_json()['code'] == 'unauthenticated'

    def test_sql_statements_do_not_grow_with_the_deck(self, app, api):
        ids = fillers(30)
        small = make_deck('Small', content(main=[line('OGN', ids[0], 3)],
                                           sideboard=[line('OGN', 'U2', 1)]))
        big = make_deck('Big', content(legend=ref('OGN', 'L1'), champion=ref('OGN', 'C1'),
                                       main=[line('OGN', i, 3) for i in ids[1:]],
                                       runes=[line('OGN', 'R1', 12)],
                                       sideboard=[line('OGN', 'U2', 2)]))
        for card_id in ids[:10]:
            own('OGN', card_id, 1)
        _, one = count_statements(app, lambda: api.get(f'{BASE}/{small}/vs-collection'))
        resp, many = count_statements(app, lambda: api.get(f'{BASE}/{big}/vs-collection'))
        assert len(resp.get_json()['data']['missing']) == 33
        # user, head, version, cards, sets, prices (2), owned copies
        assert many == one == 8


# --- POST /decks/<id>/missing-to-wishlist ----------------------------------------------------

class TestMissingToWishlist:
    def test_adds_the_missing_count_to_the_default_list_created_lazily(self, api):
        own('OGN', 'U1', 1)
        deck_id = make_deck('Azir', AZIR)
        assert lists_of() == []
        result = to_wishlist(api, deck_id)
        assert list(result) == RESULT_KEYS
        wishlist = lists_of()
        assert len(wishlist) == 1 and wishlist[0].rbwls_is_default
        assert result['wishlist'] == {'id': wishlist[0].rbwls_id, 'name': 'Wishlist'}
        assert result['added'] == 9 and result['merged'] == 0 and result['unchanged'] == 0
        assert result['skipped'] == [] and result['total_missing_names'] == 9
        assert [(k, s, c, f, q) for k, s, c, f, q, _p, _n in wish_lines(wishlist[0].rbwls_id)] == [
            ('azir, emperor', 'OGN', 'L1', 'any', 1), ('azir, ascendant', 'OGN', 'C1', 'any', 1),
            ('sandstorm', 'OGN', 'S1', 'any', 3), ('shurima guard', 'OGN', 'U1', 'any', 2),
            ('calm rune', 'OGN', 'R1', 'any', 6), ('order rune', 'OGN', 'R2', 'any', 6),
            ('field 1', 'OGN', 'B1', 'any', 1), ('field 2', 'OGN', 'B2', 'any', 1),
            ('desert scout', 'OGN', 'U2', 'any', 2)]
        # by printing, foil any, no max price, no note
        assert {(p, n) for *_rest, p, n in wish_lines(wishlist[0].rbwls_id)} == {(None, None)}

    def test_an_explicit_list_and_the_deck_stays_unchanged(self, api):
        api.get(WISHLISTS)
        target = data(api.post(WISHLISTS, json={'name': 'For Azir'}), 201)['id']
        deck_id = make_deck('Azir', content(main=[line('OGN', 'U2', 2)]))
        before = versions(deck_id)
        result = to_wishlist(api, deck_id, {'wishlist_id': target})
        assert result['wishlist'] == {'id': target, 'name': 'For Azir'} and result['added'] == 1
        assert [q for *_r, q, _p, _n in wish_lines(target)] == [2]
        default = next(w for w in lists_of() if w.rbwls_is_default)
        assert wish_lines(default.rbwls_id) == []
        assert versions(deck_id) == before

    def test_another_users_list_or_an_unknown_list_is_404(self, api, app):
        other = login_as(app.test_client(), 'otheruser')
        theirs = data(other.post(WISHLISTS, json={'name': 'Theirs'}), 201)['id']
        deck_id = make_deck('Azir', AZIR)
        for list_id in (theirs, theirs + 100):
            resp = api.post(f'{BASE}/{deck_id}/missing-to-wishlist',
                            json={'wishlist_id': list_id})
            assert resp.status_code == 404 and resp.get_json() == NOT_FOUND
        assert RbWishlistLine.query.count() == 0

    def test_another_users_deck_and_unknown_ids_are_404(self, api):
        theirs = make_deck('Azir', AZIR, user='otheruser')
        for deck_id in (theirs, theirs + 100):
            resp = api.post(f'{BASE}/{deck_id}/missing-to-wishlist')
            assert resp.status_code == 404 and resp.get_json() == NOT_FOUND
        assert RbWishlistLine.query.count() == 0 and lists_of() == []

    def test_an_invalid_wishlist_id_is_a_validation_error(self, api):
        deck_id = make_deck('Azir', AZIR)
        for bad in ('3', 0, True):
            resp = api.post(f'{BASE}/{deck_id}/missing-to-wishlist', json={'wishlist_id': bad})
            assert resp.status_code == 400 and resp.get_json()['code'] == 'validation_error'
        assert RbWishlistLine.query.count() == 0

    def test_a_null_wishlist_id_means_the_default_list(self, api):
        deck_id = make_deck('Azir', content(main=[line('OGN', 'U2', 2)]))
        result = to_wishlist(api, deck_id, {'wishlist_id': None})
        assert result['wishlist']['name'] == 'Wishlist' and result['added'] == 1

    def test_an_existing_line_is_raised_to_the_missing_count_never_summed(self, api):
        api.get(WISHLISTS)
        default = lists_of()[0].rbwls_id
        api.post(f'{WISHLISTS}/{default}/lines',
                 json={'set_id': 'OGN', 'card_id': 'U1', 'qty': 1, 'max_price': 1.5,
                       'note': 'mine'})
        api.post(f'{WISHLISTS}/{default}/lines',
                 json={'set_id': 'OGN', 'card_id': 'U2', 'qty': 5})
        api.post(f'{WISHLISTS}/{default}/lines',
                 json={'set_id': 'OGN', 'card_id': 'S1', 'qty': 1, 'foil': 'N'})
        deck_id = make_deck('Azir', content(main=[line('OGN', 'U1', 3), line('OGN', 'S1', 2)],
                                            sideboard=[line('OGN', 'U2', 2)]))
        result = to_wishlist(api, deck_id)
        # U1: 1 -> 3 (merged); U2: 5 >= 2 (unchanged); S1 any is another target than S1 N (added)
        assert (result['added'], result['merged'], result['unchanged']) == (1, 1, 1)
        got = {(s, c, f): (q, p, n) for _k, s, c, f, q, p, n in wish_lines(default)}
        assert got[('OGN', 'U1', 'any')][0] == 3
        assert float(got[('OGN', 'U1', 'any')][1]) == 1.5 and got[('OGN', 'U1', 'any')][2] == 'mine'
        assert got[('OGN', 'U2', 'any')][0] == 5
        assert got[('OGN', 'S1', 'N')][0] == 1 and got[('OGN', 'S1', 'any')][0] == 2

    def test_a_second_click_changes_nothing(self, api):
        deck_id = make_deck('Azir', AZIR)
        to_wishlist(api, deck_id)
        default = lists_of()[0].rbwls_id
        before = wish_lines(default)
        again = to_wishlist(api, deck_id)
        assert (again['added'], again['merged'], again['unchanged']) == (0, 0, 9)
        assert wish_lines(default) == before

    def test_a_full_list_adds_what_fits_in_order_and_reports_the_rest(self, api):
        api.get(WISHLISTS)
        default = lists_of()[0].rbwls_id
        now = datetime(2026, 10, 1)
        db.session.add_all([RbWishlistLine(
            rbwsl_list_id=default, rbwsl_name_key=f'filler {n}', rbwsl_name=f'Filler {n}',
            rbwsl_foil='any', rbwsl_qty=1, rbwsl_created_at=now, rbwsl_updated_at=now)
            for n in range(98)])
        db.session.commit()
        own('OGN', 'L1', 1)
        deck_id = make_deck('Azir', AZIR)
        result = to_wishlist(api, deck_id)
        assert result['added'] == 2 and result['total_missing_names'] == 8
        assert [(s['card']['key'], s['missing'], s['reason']) for s in result['skipped']] == [
            ('OGN-U1', 3, 'list_full'), ('OGN-R1', 6, 'list_full'), ('OGN-R2', 6, 'list_full'),
            ('OGN-B1', 1, 'list_full'), ('OGN-B2', 1, 'list_full'),
            ('OGN-U2', 2, 'list_full')]
        assert list(result['skipped'][0]['card']) == CARD_MINI_KEYS
        assert len(wish_lines(default)) == 100
        assert [c for _k, _s, c, *_r in wish_lines(default)][-2:] == ['C1', 'S1']

    def test_a_full_list_still_raises_its_existing_lines(self, api):
        api.get(WISHLISTS)
        default = lists_of()[0].rbwls_id
        api.post(f'{WISHLISTS}/{default}/lines', json={'set_id': 'OGN', 'card_id': 'U2'})
        now = datetime(2026, 10, 1)
        db.session.add_all([RbWishlistLine(
            rbwsl_list_id=default, rbwsl_name_key=f'filler {n}', rbwsl_name=f'Filler {n}',
            rbwsl_foil='any', rbwsl_qty=1, rbwsl_created_at=now, rbwsl_updated_at=now)
            for n in range(99)])
        db.session.commit()
        deck_id = make_deck('Azir', content(main=[line('OGN', 'U1', 3)],
                                            sideboard=[line('OGN', 'U2', 2)]))
        result = to_wishlist(api, deck_id)
        assert (result['added'], result['merged']) == (0, 1)
        assert [(s['card']['key'], s['reason']) for s in result['skipped']] == [
            ('OGN-U1', 'list_full')]

    def test_quantities_are_capped_at_99_and_the_rest_is_reported(self, api):
        deck_id = make_deck('Runes', content(runes=[line('OGN', 'R1', 120)]))
        result = to_wishlist(api, deck_id)
        default = lists_of()[0].rbwls_id
        assert result['added'] == 1
        assert [(s['card']['key'], s['missing'], s['reason']) for s in result['skipped']] == [
            ('OGN-R1', 21, 'qty_cap')]
        assert [q for *_r, q, _p, _n in wish_lines(default)] == [99]

    def test_nothing_missing_adds_nothing(self, api):
        own('OGN', 'U2', 3)
        deck_id = make_deck('Mine', content(main=[line('OGN', 'U2', 3)]))
        result = to_wishlist(api, deck_id)
        assert result == {'wishlist': {'id': lists_of()[0].rbwls_id, 'name': 'Wishlist'},
                          'added': 0, 'merged': 0, 'unchanged': 0, 'skipped': [],
                          'total_missing_names': 0}
        assert RbWishlistLine.query.count() == 0

    def test_the_line_name_key_matches_a_line_added_by_hand(self, api):
        deck_id = make_deck('Azir', content(main=[line('SFD', 'U1', 2)]))
        to_wishlist(api, deck_id)
        default = lists_of()[0].rbwls_id
        resp = api.post(f'{WISHLISTS}/{default}/lines', json={'set_id': 'SFD', 'card_id': 'U1'})
        assert data(resp)['line']['qty'] == 3 and data(resp)['merged'] is True
        assert wish_lines(default)[0][0] == name_key('Shurima Guard')

    def test_sql_statements_do_not_grow_with_the_missing_cards(self, app, api):
        api.get(WISHLISTS)
        ids = fillers(30)
        small = make_deck('Small', content(main=[line('OGN', ids[0], 3)],
                                           sideboard=[line('OGN', 'U2', 1)]))
        big = make_deck('Big', content(legend=ref('OGN', 'L1'), champion=ref('OGN', 'C1'),
                                       main=[line('OGN', i, 3) for i in ids[1:]],
                                       runes=[line('OGN', 'R1', 12)],
                                       sideboard=[line('OGN', 'U1', 2)]))
        _, one = count_statements(
            app, lambda: api.post(f'{BASE}/{small}/missing-to-wishlist'))
        resp, many = count_statements(
            app, lambda: api.post(f'{BASE}/{big}/missing-to-wishlist'))
        assert resp.get_json()['data']['added'] == 33
        # user, head, version, cards, sets, prices (2), owned copies, lists, lines of the list,
        # the new lines (one INSERT), the list's date
        assert many == one == 12

    def test_anonymous_is_401(self, app, api):
        deck_id = make_deck('Azir', AZIR)
        resp = app.test_client().post(f'{BASE}/{deck_id}/missing-to-wishlist')
        assert resp.status_code == 401 and resp.get_json()['code'] == 'unauthenticated'
        assert RbWishlistLine.query.count() == 0

    def test_csrf_is_required(self, api, csrf_app):
        deck_id = make_deck('Azir', content(main=[line('OGN', 'U2', 1)]))
        resp = api.post(f'{BASE}/{deck_id}/missing-to-wishlist')
        assert resp.status_code == 400 and resp.get_json()['code'] == 'csrf_invalid'
        assert RbWishlistLine.query.count() == 0
        token = data(api.get('/riftbound/api/v1/auth/session'))['csrf_token']
        resp = api.post(f'{BASE}/{deck_id}/missing-to-wishlist',
                        headers={'X-CSRFToken': token})
        assert data(resp)['added'] == 1
