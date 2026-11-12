"""F2-d S1-S7: GET /riftbound/api/v1/cards/<set_id>/<card_id> card detail."""
from datetime import date, datetime

import pytest
from sqlalchemy import event
from werkzeug.security import generate_password_hash

from app import db
from app.models import (RbCard, RbCollection, RbDeck, RbDeckHead, RbDeckVersion, RbSet,
                        RbWishlist, RbWishlistLine, RbcmPrice, RbcmProductCardMap, User)
from app.services import bans
from tests.deck_api_helpers import content, line, make_deck, ref

URL = '/riftbound/api/v1/cards/OGN/79'


def _seed_detail(app, decks=True):
    """Two sets, a two-printing name, related/unrelated cards, prices, lines and (when
    `decks`, which needs the signed-in testuser) decks v2."""
    with app.app_context():
        db.session.add_all([
            RbSet(rbset_id='OGN', rbset_name='Origins', rbset_outdat=date(2025, 10, 31)),
            RbSet(rbset_id='SFD', rbset_name='Spiritforged', rbset_outdat=date(2025, 11, 30)),
        ])
        db.session.add_all([
            RbCard(rbcar_rbset_id='OGN', rbcar_id='1', rbcar_name='Alpha Fury',
                   rbcar_domain='Fury', rbcar_type='Unit', rbcar_rarity='Common',
                   rbcar_energy=1, rbcar_power=1, rbcar_might=1,
                   rbcar_tags='Noxus', rbcar_ability='Charge.',
                   rbcar_artist='Art A'),
            RbCard(rbcar_rbset_id='OGN', rbcar_id='2', rbcar_name='Beta Calm',
                   rbcar_domain='Calm', rbcar_type='Spell', rbcar_rarity='Uncommon',
                   rbcar_energy=2, rbcar_power=None, rbcar_might=None,
                   rbcar_tags='Zaun', rbcar_ability='Heal.',
                   rbcar_artist='Art B'),
            RbCard(rbcar_rbset_id='OGN', rbcar_id='3', rbcar_name='Gamma Gear',
                   rbcar_domain='Order', rbcar_type='Gear', rbcar_rarity='Common',
                   rbcar_energy=None, rbcar_power=None, rbcar_might=6,
                   rbcar_tags='', rbcar_ability='Equip.',
                   rbcar_artist='Art C'),
            RbCard(rbcar_rbset_id='OGN', rbcar_id='4', rbcar_name='Delta Legend',
                   rbcar_domain='Mind', rbcar_type='Legend', rbcar_rarity='Showcase',
                   rbcar_energy=0, rbcar_power=None, rbcar_might=None,
                   rbcar_tags='Noxus, Zaun', rbcar_ability='Rule.',
                   rbcar_artist='Art D'),
            RbCard(rbcar_rbset_id='OGN', rbcar_id='79', rbcar_name='Jinx, Loose Cannon',
                   rbcar_domain='Chaos', rbcar_type='Champion Unit', rbcar_rarity='Rare',
                   rbcar_energy=3, rbcar_power=4, rbcar_might=5,
                   rbcar_tags='Zaun, Noxus', rbcar_ability='Boom.',
                   rbcar_artist='Art J'),
            RbCard(rbcar_rbset_id='SFD', rbcar_id='257', rbcar_name='Jinx, Loose Cannon',
                   rbcar_domain='Chaos', rbcar_type='Champion Unit', rbcar_rarity='Rare',
                   rbcar_energy=3, rbcar_power=4, rbcar_might=5,
                   rbcar_tags='Zaun', rbcar_ability='Boom v2.',
                   rbcar_artist='Art J'),
        ])
        db.session.add_all([
            # OGN/1: plain non-foil product with full columns on the latest date.
            RbcmProductCardMap(rbpcm_rbset_id='OGN', rbpcm_rbcar_id='1',
                               rbpcm_id_product=1, rbpcm_foil='N'),
            RbcmPrice(rbprc_date='20261010', rbprc_id_product=1,
                      rbprc_avg7=8, rbprc_low=7, rbprc_avg30=9),
            RbcmPrice(rbprc_date='20261020', rbprc_id_product=1,
                      rbprc_avg1=10.5, rbprc_avg7=10, rbprc_avg30=9.5,
                      rbprc_low=9, rbprc_trend=9.8, rbprc_low_ex=9.2),
            # OGN/2: foilable common with separate N and S products.
            RbcmProductCardMap(rbpcm_rbset_id='OGN', rbpcm_rbcar_id='2',
                               rbpcm_id_product=2, rbpcm_foil='N'),
            RbcmProductCardMap(rbpcm_rbset_id='OGN', rbpcm_rbcar_id='2',
                               rbpcm_id_product=22, rbpcm_foil='S'),
            RbcmPrice(rbprc_date='20261020', rbprc_id_product=2,
                      rbprc_avg7=5, rbprc_low=4),
            RbcmPrice(rbprc_date='20261020', rbprc_id_product=22,
                      rbprc_avg7_foil=7, rbprc_low_foil=6),
            # OGN/79: non-foil-mapped product carrying foil columns but no
            # separate foil product -> foil keys stay null.
            RbcmProductCardMap(rbpcm_rbset_id='OGN', rbpcm_rbcar_id='79',
                               rbpcm_id_product=79, rbpcm_foil='N'),
            RbcmPrice(rbprc_date='20261020', rbprc_id_product=79,
                      rbprc_avg1=1.3, rbprc_avg7=1.15, rbprc_avg30=1.05,
                      rbprc_low=0.9, rbprc_trend=1.2,
                      rbprc_avg1_foil=1.4, rbprc_avg7_foil=1.21,
                      rbprc_avg30_foil=1.1, rbprc_trend_foil=None,
                      rbprc_low_foil=None, rbprc_low_ex=1.0),
        ])
        # SFD/257 is unmapped on purpose: no price, price_detail null.
        db.session.add_all([
            RbCollection(rbcol_rbset_id='OGN', rbcol_rbcar_id='79',
                         rbcol_foil='S', rbcol_user='testuser', rbcol_quantity=1,
                         rbcol_selling='Y', rbcol_sell_price=5.5, rbcol_playset=1,
                         rbcol_purchase_price=7.5, rbcol_sell_qty=1,
                         rbcol_condition='EX', rbcol_language='Spanish',
                         rbcol_chadat=datetime(2026, 10, 2, 9, 30)),
            RbCollection(rbcol_rbset_id='OGN', rbcol_rbcar_id='79',
                         rbcol_foil='N', rbcol_user='testuser', rbcol_quantity=2,
                         rbcol_selling='N',
                         rbcol_condition='NM', rbcol_language='English',
                         rbcol_chadat=datetime(2026, 10, 1, 9, 30)),
            # Another user's rows must never leak into my_lines or owned.
            RbCollection(rbcol_rbset_id='OGN', rbcol_rbcar_id='79',
                         rbcol_foil='N', rbcol_user='otheruser', rbcol_quantity=9,
                         rbcol_condition='NM', rbcol_language='English'),
        ])
        db.session.add(User(username='otheruser', email='other@test.com',
                            password_hash=generate_password_hash(
                                'testpass123', method='pbkdf2:sha256:1000')))
        # A legacy `rbdecks` row is not a source any more: decks v2 are.
        db.session.add(RbDeck(rbdck_user='testuser', rbdck_name='Legacy', rbdck_seq=1,
                              rbdck_cards={'main': [{'set': 'OGN', 'id': '79', 'qty': 3}],
                                           'sideboard': []}))
        db.session.commit()
        bans.add_ban('Jinx, Loose Cannon', ['1v1'], reason='Too strong')
        if decks:
            _seed_decks()


def _seed_decks():
    """Decks v2 of testuser (and one of otheruser) around the name 'Jinx, Loose Cannon'."""
    # Current version: 2 + 1 in main (two printings), 1 in the sideboard, the missing
    # ZZZ/9 skipped, 3 on the workbench that never count.
    aggro = make_deck('Aggro', content(
        main=[line('OGN', '79', 2), line('SFD', '257', 1), line('OGN', '1', 3)],
        sideboard=[line('SFD', '257', 1), line('ZZZ', '9', 5)],
        workbench=[line('OGN', '79', 3)]))
    # A later version that is not the current one is never read.
    db.session.add(RbDeckVersion(rbdkv_deck_id=aggro, rbdkv_seq=2,
                                 rbdkv_content=content(main=[line('OGN', '79', 9)])))
    make_deck('Brawl', content(champion=ref('SFD', '257'), main=[line('OGN', '79', 2)]))
    make_deck('Bench only', content(workbench=[line('OGN', '79', 2)]))
    make_deck('Nope', content(main=[line('OGN', '1', 3)]))
    make_deck('Aggro', content(main=[line('OGN', '79', 3)]), user='otheruser')


class TestSummaryAnd404:
    def test_summary_keys_present(self, authenticated_client, app):
        _seed_detail(app)
        body = authenticated_client.get(URL).get_json()
        item = body['data']
        assert item['set_id'] == 'OGN'
        assert item['card_id'] == '79'
        assert item['key'] == 'OGN-79'
        assert item['name'] == 'Jinx, Loose Cannon'
        assert item['bans'] == {'1v1': True, '2v2': False}
        assert item['owned'] == {'total': 3, 'foil': 1}
        assert item['price']['market'] == 1.21
        assert item['price']['market_source'] == 'avg7_foil'
        assert item['ability'] == 'Boom.'
        assert item['artist'] == 'Art J'
        assert item['set'] == {'id': 'OGN', 'name': 'Origins',
                               'released_on': '2025-10-31'}

    def test_missing_card_is_a_404_envelope(self, authenticated_client, app):
        _seed_detail(app)
        resp = authenticated_client.get('/riftbound/api/v1/cards/NOPE/1')
        assert resp.status_code == 404
        assert resp.get_json() == {
            'success': False, 'error': 'Not Found',
            'message': 'The requested resource was not found'}


class TestPriceDetail:
    def test_full_columns_without_separate_foil_product(self, authenticated_client, app):
        _seed_detail(app)
        detail = authenticated_client.get(URL).get_json()['data']['price_detail']
        assert detail['date'] == '2026-10-20'
        assert detail['product_id'] == 79
        assert detail['columns'] == {
            'low': 0.9, 'avg1': 1.3, 'avg7': 1.15, 'avg30': 1.05,
            'trend': 1.2, 'low_foil': None, 'avg1_foil': 1.4,
            'avg7_foil': 1.21, 'avg30_foil': 1.1, 'trend_foil': None,
            'low_ex': 1.0}
        assert detail['foil_product_id'] is None
        assert detail['foil_columns'] is None

    def test_foil_product_columns(self, authenticated_client, app):
        _seed_detail(app)
        detail = authenticated_client.get(
            '/riftbound/api/v1/cards/OGN/2').get_json()['data']['price_detail']
        assert detail['product_id'] == 2
        assert detail['foil_product_id'] == 22
        assert detail['foil_columns']['avg7_foil'] == 7
        assert detail['foil_columns']['low_foil'] == 6

    def test_unmapped_card_has_null_price_detail(self, authenticated_client, app):
        _seed_detail(app)
        item = authenticated_client.get(
            '/riftbound/api/v1/cards/SFD/257').get_json()['data']
        assert item['price_detail'] is None
        assert item['price'] is None


class TestPrintingsAndRelated:
    def test_printings_ordered_by_natural_key_with_owned(self, authenticated_client, app):
        _seed_detail(app)
        item = authenticated_client.get(URL).get_json()['data']
        assert [p['key'] for p in item['printings']] == ['OGN-79', 'SFD-257']
        first = item['printings'][0]
        assert first['name'] == 'Jinx, Loose Cannon'
        assert first['market'] == 1.21
        assert first['owned_total'] == 3
        assert set(first) == {'set_id', 'card_id', 'key', 'name', 'domains',
                              'type', 'supertype', 'rarity', 'image_src',
                              'image_thumb_src', 'is_base', 'market',
                              'owned_total'}

    def test_related_shared_tags_base_only_other_names(self, authenticated_client, app):
        _seed_detail(app)
        related = authenticated_client.get(URL).get_json()['data']['related']
        # Delta shares 2 tags, Alpha and Beta share 1 (name order breaks ties);
        # the other printing of Jinx and tagless Gamma are excluded.
        assert [c['key'] for c in related] == ['OGN-4', 'OGN-1', 'OGN-2']
        assert len(related) <= 12

    def test_no_tags_means_no_related(self, authenticated_client, app):
        _seed_detail(app)
        related = authenticated_client.get(
            '/riftbound/api/v1/cards/OGN/3').get_json()['data']['related']
        assert related == []


class TestBansOwnedAndDecks:
    def test_ban_info(self, authenticated_client, app):
        _seed_detail(app)
        item = authenticated_client.get(URL).get_json()['data']
        assert {'mode': '1v1', 'reason': 'Too strong'}.items() <= item['ban_info'][0].items()

    def test_my_lines_order_and_fields(self, authenticated_client, app):
        _seed_detail(app)
        lines = authenticated_client.get(URL).get_json()['data']['my_lines']
        assert [(line['foil'], line['qty']) for line in lines] == [
            (False, 2), (True, 1)]
        foil_line = lines[1]
        assert foil_line['selling'] is True
        assert foil_line['sell_price'] == 5.5
        assert foil_line['playset'] == 1
        assert foil_line['condition'] == 'EX'
        assert foil_line['language'] == 'Spanish'
        assert foil_line['updated_at'] == '2026-10-02T09:30:00Z'
        assert foil_line['purchase_price'] == 7.5
        assert foil_line['sell_qty'] == 1
        assert set(foil_line) == {'id', 'foil', 'qty', 'condition', 'language',
                                  'selling', 'sell_price', 'playset', 'updated_at',
                                  'purchase_price', 'sell_qty'}

    def test_in_decks_reads_the_current_version_of_my_v2_decks(self, authenticated_client,
                                                                 app):
        _seed_detail(app)
        decks = authenticated_client.get(URL).get_json()['data']['in_decks']
        # Aggro: two printings in main (2 + 1) and the sideboard (1); the workbench and the
        # non-current version are left out. Brawl: the champion slot (1) and main (2).
        # Bench only, Nope, the legacy row and otheruser's deck never appear.
        assert [(d['name'], d['qty']) for d in decks] == [('Aggro', 4), ('Brawl', 3)]
        assert all(set(d) == {'deck_id', 'name', 'qty'} for d in decks)

    def test_in_decks_deck_id_is_the_v2_head_id(self, authenticated_client, app):
        _seed_detail(app)
        decks = authenticated_client.get(URL).get_json()['data']['in_decks']
        with app.app_context():
            mine = {name: deck_id for deck_id, name in db.session.query(
                RbDeckHead.rbdkh_id, RbDeckHead.rbdkh_name).filter(
                RbDeckHead.rbdkh_user_id == User.query.filter_by(
                    username='testuser').one().id)}
        assert [d['deck_id'] for d in decks] == [mine['Aggro'], mine['Brawl']]
        for deck in decks:
            resp = authenticated_client.get(f'/riftbound/api/v1/decks/{deck["deck_id"]}')
            assert resp.status_code == 200
            assert resp.get_json()['data']['name'] == deck['name']

    def test_in_decks_ignores_legacy_only_decks(self, authenticated_client, app):
        _seed_detail(app)
        with app.app_context():
            db.session.add(RbDeck(rbdck_user='testuser', rbdck_name='Zeta', rbdck_seq=1,
                                  rbdck_cards={'main': [{'set': 'SFD', 'id': '257',
                                                         'qty': 2}], 'sideboard': []}))
            db.session.commit()
        decks = authenticated_client.get(URL).get_json()['data']['in_decks']
        assert 'Legacy' not in [d['name'] for d in decks]
        assert 'Zeta' not in [d['name'] for d in decks]

    def test_in_decks_of_the_other_user(self, authenticated_client, app):
        _seed_detail(app)
        from tests.conftest import login_as
        other = login_as(app.test_client(), 'otheruser')
        decks = other.get(URL).get_json()['data']['in_decks']
        assert [(d['name'], d['qty']) for d in decks] == [('Aggro', 3)]


def _wishlist(name, position, lines, *, user='testuser', is_default=False):
    """A wishlist of `user` with `lines` = [(name, set_id, card_id, foil, qty)]
    (set_id/card_id None = any printing); returns its id."""
    owner = User.query.filter_by(username=user).one()
    wishlist = RbWishlist(rbwls_user_id=owner.id, rbwls_name=name, rbwls_position=position,
                          rbwls_is_default=is_default)
    db.session.add(wishlist)
    db.session.flush()
    for card_name, set_id, card_id, foil, qty in lines:
        db.session.add(RbWishlistLine(rbwsl_list_id=wishlist.rbwls_id,
                                      rbwsl_name_key=bans.name_key(card_name),
                                      rbwsl_name=card_name, rbwsl_rbset_id=set_id,
                                      rbwsl_rbcar_id=card_id, rbwsl_foil=foil, rbwsl_qty=qty))
    db.session.commit()
    return wishlist.rbwls_id


JINX = 'Jinx, Loose Cannon'


class TestInWishlists:
    """F3-j follow-ups: the caller's wishlists that hold the card now."""

    def _in_wishlists(self, client, url=URL):
        return client.get(url).get_json()['data']['in_wishlists']

    def test_a_printing_line_shows_with_its_list(self, authenticated_client, app):
        _seed_detail(app)
        with app.app_context():
            list_id = _wishlist('Wanted', 1, [(JINX, 'OGN', '79', 'any', 2)],
                                is_default=True)
        assert self._in_wishlists(authenticated_client) == [
            {'id': list_id, 'name': 'Wanted', 'is_default': True, 'qty': 2}]

    def test_a_by_name_line_shows_on_every_printing(self, authenticated_client, app):
        _seed_detail(app)
        with app.app_context():
            list_id = _wishlist('Any art', 1, [(JINX, None, None, 'any', 3)])
        expected = [{'id': list_id, 'name': 'Any art', 'is_default': False, 'qty': 3}]
        assert self._in_wishlists(authenticated_client) == expected
        assert self._in_wishlists(authenticated_client,
                                  '/riftbound/api/v1/cards/SFD/257') == expected

    def test_a_line_of_another_printing_does_not_match(self, authenticated_client, app):
        _seed_detail(app)
        with app.app_context():
            list_id = _wishlist('Other art', 1, [(JINX, 'SFD', '257', 'any', 1)])
        assert self._in_wishlists(authenticated_client) == []
        assert self._in_wishlists(authenticated_client,
                                  '/riftbound/api/v1/cards/SFD/257') == [
            {'id': list_id, 'name': 'Other art', 'is_default': False, 'qty': 1}]

    def test_lines_of_one_list_sum_their_qty(self, authenticated_client, app):
        _seed_detail(app)
        with app.app_context():
            list_id = _wishlist('Both finishes', 1, [
                (JINX, 'OGN', '79', 'N', 2), (JINX, 'OGN', '79', 'S', 1),
                (JINX, None, None, 'any', 4), (JINX, 'SFD', '257', 'any', 9),
                ('Alpha Fury', 'OGN', '1', 'any', 7)])
        assert self._in_wishlists(authenticated_client) == [
            {'id': list_id, 'name': 'Both finishes', 'is_default': False, 'qty': 7}]

    def test_several_lists_follow_the_list_order(self, authenticated_client, app):
        _seed_detail(app)
        with app.app_context():
            third = _wishlist('Zeta', 3, [(JINX, 'OGN', '79', 'any', 1)])
            first = _wishlist('Omega', 1, [(JINX, None, None, 'any', 2)], is_default=True)
            _wishlist('Empty for Jinx', 2, [('Alpha Fury', 'OGN', '1', 'any', 1)])
        assert [(w['id'], w['name'], w['qty']) for w in
                self._in_wishlists(authenticated_client)] == [
            (first, 'Omega', 2), (third, 'Zeta', 1)]

    def test_another_users_lists_never_show(self, authenticated_client, app):
        _seed_detail(app)
        with app.app_context():
            _wishlist('Theirs', 1, [(JINX, 'OGN', '79', 'any', 5)], user='otheruser')
            mine = _wishlist('Mine', 1, [(JINX, None, None, 'any', 1)])
        assert self._in_wishlists(authenticated_client) == [
            {'id': mine, 'name': 'Mine', 'is_default': False, 'qty': 1}]
        from tests.conftest import login_as
        other = login_as(app.test_client(), 'otheruser')
        assert [w['name'] for w in self._in_wishlists(other)] == ['Theirs']

    def test_no_lines_is_an_empty_list(self, authenticated_client, app):
        _seed_detail(app)
        assert self._in_wishlists(authenticated_client) == []


class TestStatementBound:
    def _count_statements(self, app, client, url):
        counts = []

        def listener(conn, cursor, statement, parameters, context, executemany):
            counts.append(statement)

        with app.app_context():
            event.listen(db.engine, 'before_cursor_execute', listener)
            try:
                resp = client.get(url)
                assert resp.status_code == 200
            finally:
                event.remove(db.engine, 'before_cursor_execute', listener)
        return len(counts)

    def test_detail_statement_budget(self, authenticated_client, app):
        # 10 before the F3-j follow-ups, plus one for `in_wishlists`.
        _seed_detail(app)
        assert self._count_statements(app, authenticated_client, URL) <= 11

    def test_in_wishlists_costs_one_statement_whatever_the_lists(self, authenticated_client,
                                                                app):
        _seed_detail(app)
        before = self._count_statements(app, authenticated_client, URL)
        with app.app_context():
            for n in range(5):
                _wishlist(f'List {n}', n + 1, [(JINX, 'OGN', '79', 'N', 1),
                                               (JINX, None, None, 'any', 1)])
        assert self._count_statements(app, authenticated_client, URL) == before
        assert len(authenticated_client.get(URL).get_json()['data']['in_wishlists']) == 5

    def test_in_decks_costs_the_same_with_more_decks(self, authenticated_client, app):
        _seed_detail(app)
        before = self._count_statements(app, authenticated_client, URL)
        with app.app_context():
            for n in range(5):
                make_deck(f'More {n}', content(main=[line('OGN', '79', 1)]))
        assert self._count_statements(app, authenticated_client, URL) == before
        decks = authenticated_client.get(URL).get_json()['data']['in_decks']
        assert len(decks) == 7


class TestAuthzAndShape:
    def test_anonymous_gets_a_json_401(self, client, app):
        _seed_detail(app, decks=False)
        resp = client.get(URL)
        assert resp.status_code == 401
        body = resp.get_json()
        assert (body['success'], body['error'], body['code']) == (False, 'Unauthorized',
                                                                   'unauthenticated')

    def test_endpoint_name(self, app):
        rules = [r for r in app.url_map.iter_rules()
                 if r.rule == '/riftbound/api/v1/cards/<set_id>/<card_id>']
        assert [(r.endpoint, sorted(r.methods - {'HEAD', 'OPTIONS'})) for r in rules] == [
            ('api_v1.get_card', ['GET'])]
