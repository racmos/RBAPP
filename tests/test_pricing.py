"""
Cardmarket price resolution (PRC-1, PRC-2).

PRC-1 pins the behavior introduced by commit 1ae1f6e. It was written against
`collection._resolve_price` (unit a) and re-pointed to the shared
`app.services.pricing.resolve_price` when the chain moved there (unit c, 3.17).

  - TestResolvePriceChain ... table-driven chain
  - TestCollectionRoutes .... route level: the SQL join (canonical product,
    latest price row, fallback mapping) plus the chain, through the collection
    list and the CSV export. Unchanged by the move.
  - TestCanonicalProductId / TestLatestPriceForCard / TestDeckPrices ... PRC-2:
    deck viewing uses the very same chain.

Rule R5: a falsy value (NULL or 0) counts as missing. A row whose four values
are all missing resolves to None, never 0.0 (orchestrator decision, unit c).
"""
import csv
import io
from contextlib import contextmanager
from decimal import Decimal
from types import SimpleNamespace

import pytest
from flask import template_rendered

from app import db
from app.models import RbCard, RbCollection, RbSet
from app.models.cardmarket import RbcmPrice, RbcmProductCardMap
from app.services.pricing import canonical_product_id, latest_price_for_card, resolve_price


# ---------------------------------------------------------------------------
# PRC-1 pure chain
# ---------------------------------------------------------------------------

def _row(avg7=None, avg7_foil=None, low=None, low_foil=None):
    return SimpleNamespace(
        rbprc_avg7=avg7, rbprc_avg7_foil=avg7_foil,
        rbprc_low=low, rbprc_low_foil=low_foil,
    )


def _resolve(row, rarity, foil):
    return resolve_price(row, rarity=rarity, foil=foil)


class TestResolvePriceChain:
    @pytest.mark.parametrize('rarity, foil, row, expected', [
        # Premium prefers the foil average
        ('Rare', 'N', _row(avg7_foil=5.0, avg7=3.0), 5.0),
        # Premium cascade: avg7_foil -> avg7 -> low_foil -> low
        ('epic', 'N', _row(low_foil=1.2, low=1.0), 1.2),
        ('epic', 'N', _row(low=1.0), 1.0),
        ('Rare', 'N', _row(avg7=3.0, low_foil=1.2, low=1.0), 3.0),
        # Showcase is premium (case-insensitive)
        ('SHOWCASE', 'N', _row(low=0.5), 0.5),
        ('showcase', 'N', _row(avg7_foil=4.0, avg7=3.0), 4.0),
        # Common non-foil prefers avg7
        ('common', 'N', _row(avg7=0.1, avg7_foil=0.9), 0.1),
        # Common non-foil cascade: avg7 -> avg7_foil -> low -> low_foil
        ('uncommon', 'N', _row(low=0.2, low_foil=0.8), 0.2),
        ('uncommon', 'N', _row(avg7_foil=0.7, low=0.2, low_foil=0.8), 0.7),
        ('uncommon', 'N', _row(low_foil=0.8), 0.8),
        # Common foil follows the premium order
        ('common', 'S', _row(avg7_foil=0.9, avg7=0.1), 0.9),
        ('common', 'S', _row(avg7=0.1, low_foil=0.8, low=0.2), 0.1),
        ('common', 'S', _row(low_foil=0.8, low=0.2), 0.8),
    ])
    def test_chain(self, rarity, foil, row, expected):
        result = _resolve(row, rarity, foil)
        assert result == expected
        assert isinstance(result, float)

    @pytest.mark.parametrize('rarity, foil', [
        ('Rare', 'N'), ('common', 'N'), ('common', 'S'),
    ])
    def test_row_with_all_values_missing_gives_none(self, rarity, foil):
        assert _resolve(_row(), rarity, foil) is None

    def test_no_price_row_gives_none(self):
        assert _resolve(None, 'Rare', 'N') is None
        assert _resolve(None, 'common', 'S') is None

    def test_numeric_decimals_come_back_as_float(self):
        result = _resolve(_row(avg7=Decimal('0.1000000000')), 'common', 'N')
        assert result == 0.1
        assert isinstance(result, float)

    # R5: 0 counts as missing, exactly as the `or` chain does today.
    @pytest.mark.parametrize('rarity, foil, row, expected', [
        ('common', 'N', _row(avg7=0, avg7_foil=0.9), 0.9),
        ('common', 'N', _row(avg7=Decimal('0'), low=0.2), 0.2),
        ('Rare', 'N', _row(avg7_foil=0, avg7=3.0), 3.0),
        ('common', 'S', _row(avg7_foil=Decimal('0'), avg7=0.1), 0.1),
    ])
    def test_zero_counts_as_missing(self, rarity, foil, row, expected):
        assert _resolve(row, rarity, foil) == expected

    # A row where every value is 0 or NULL has no price at all (decision, unit c):
    # None, not 0.0.
    @pytest.mark.parametrize('rarity, foil', [('Rare', 'N'), ('common', 'N'), ('common', 'S')])
    @pytest.mark.parametrize('row', [
        _row(avg7=0, avg7_foil=0, low=0, low_foil=0),
        _row(avg7=Decimal('0'), avg7_foil=None, low=Decimal('0.00'), low_foil=None),
    ])
    def test_row_of_zeros_gives_none(self, rarity, foil, row):
        assert _resolve(row, rarity, foil) is None

    def test_a_single_real_value_among_zeros_wins(self):
        assert _resolve(_row(avg7=0, avg7_foil=0, low=0, low_foil=0.4), 'common', 'N') == 0.4

    # No rarity at all: the common chain is used (rarity is '').
    def test_no_rarity_uses_common_chain_for_non_foil(self):
        assert resolve_price(_row(avg7=0.1, avg7_foil=0.9), rarity=None, foil='N') == 0.1

    def test_no_rarity_with_foil_uses_foil_first(self):
        assert resolve_price(_row(avg7=0.1, avg7_foil=0.9), rarity=None, foil='S') == 0.9

    def test_foil_flag_none_is_not_foil(self):
        assert resolve_price(_row(avg7=0.1, avg7_foil=0.9), rarity='common', foil=None) == 0.1

    def test_card_with_null_rarity_uses_common_chain(self):
        assert _resolve(_row(avg7=0.1, avg7_foil=0.9), None, 'N') == 0.1


# ---------------------------------------------------------------------------
# Route level: collection list (~L239) and CSV export (~L748)
# ---------------------------------------------------------------------------

SET_ID = 'TEST1'
USER = 'testuser'

# card_id, rarity, foil, mappings [(id_product, rbpcm_foil)],
# prices {id_product: [(date, {columns})]}, expected unit price (None = no price)
CASES = [
    # --- common / uncommon -------------------------------------------------
    ('c01', 'Common', 'N', [(101, 'N')],
     {101: [('20261001', dict(avg7=0.10, avg7_foil=0.90))]}, 0.10),
    # low / low_foil fallback when the avg7 columns are NULL (35c2b71)
    ('c02', 'Uncommon', 'N', [(102, 'N')],
     {102: [('20261001', dict(low=0.20, low_foil=0.80))]}, 0.20),
    ('c03', 'Common', 'S', [(103, 'S')],
     {103: [('20261001', dict(avg7=0.10, avg7_foil=0.90))]}, 0.90),
    # unmapped card: no price
    ('c04', 'Common', 'N', [], {}, None),
    # latest-dated price row wins
    ('c05', 'Common', 'N', [(105, 'N')],
     {105: [('20261001', dict(avg7=1.0)), ('20261002', dict(avg7=2.0))]}, 2.0),
    # no exact foil mapping: any mapping of the card is used as approximation
    ('c06', 'Common', 'N', [(106, 'S')],
     {106: [('20261001', dict(avg7=0.30))]}, 0.30),
    # several mappings: the canonical product is MIN(id_product)
    ('c07', 'Common', 'N', [(108, 'N'), (107, 'N')],
     {107: [('20261001', dict(avg7=0.70))], 108: [('20261001', dict(avg7=0.80))]}, 0.70),
    # price row exists but every column is NULL
    ('c08', 'Common', 'N', [(109, 'N')], {109: [('20261001', dict())]}, None),
    # R5 at SQL level: 0 counts as missing
    ('c09', 'Common', 'N', [(110, 'N')],
     {110: [('20261001', dict(avg7=0, avg7_foil=0.50))]}, 0.50),
    # --- premium -----------------------------------------------------------
    ('r01', 'Rare', 'N', [(201, None)],
     {201: [('20261001', dict(avg7_foil=5.0, avg7=3.0))]}, 5.0),
    ('r02', 'Rare', 'N', [(202, None)],
     {202: [('20261001', dict(low=1.0, low_foil=1.2))]}, 1.2),
    ('r03', 'Rare', 'N', [(203, None)], {203: [('20261001', dict(low=0.5))]}, 0.5),
    ('s01', 'Showcase', 'N', [(301, None)], {301: [('20261001', dict(low=0.5))]}, 0.5),
    ('e01', 'Epic', 'N', [(401, None)],
     {401: [('20261001', dict(avg7=3.0, low_foil=1.2))]}, 3.0),
]


def _seed(app):
    with app.app_context():
        db.session.add(RbSet(rbset_id=SET_ID, rbset_name='Test Set', rbset_ncard=100))
        for card_id, rarity, foil, mappings, prices, _expected in CASES:
            db.session.add(RbCard(
                rbcar_rbset_id=SET_ID, rbcar_id=card_id,
                rbcar_name=f'Card {card_id}', rbcar_rarity=rarity,
            ))
            db.session.add(RbCollection(
                rbcol_rbset_id=SET_ID, rbcol_rbcar_id=card_id, rbcol_foil=foil,
                rbcol_user=USER, rbcol_quantity=2, rbcol_selling='Y',
            ))
            for id_product, map_foil in mappings:
                db.session.add(RbcmProductCardMap(
                    rbpcm_id_product=id_product, rbpcm_rbset_id=SET_ID,
                    rbpcm_rbcar_id=card_id, rbpcm_foil=map_foil,
                ))
            for id_product, rows in prices.items():
                for date, columns in rows:
                    db.session.add(RbcmPrice(
                        rbprc_date=date, rbprc_id_product=id_product,
                        **{f'rbprc_{name}': value for name, value in columns.items()},
                    ))
        db.session.commit()


@contextmanager
def _captured_templates(app):
    recorded = []

    def record(sender, template, context, **extra):
        recorded.append((template, context))

    template_rendered.connect(record, app)
    try:
        yield recorded
    finally:
        template_rendered.disconnect(record, app)


class TestCollectionRoutes:
    def test_list_prices_follow_the_chain(self, app, authenticated_client):
        _seed(app)
        with _captured_templates(app) as rendered:
            resp = authenticated_client.get('/riftbound/collection?per_page=100')
        assert resp.status_code == 200
        (_, context), = [r for r in rendered if r[0].name == 'collection.html']
        data = context['collections_data']

        # One row per collection row: several mappings must not multiply rows.
        assert len(data) == len(CASES)
        got = {d['card'].rbcar_id: d['price'] for d in data}
        assert got == {card_id: expected for card_id, *_rest, expected in CASES}

    def test_list_shows_formatted_price_or_dash(self, app, authenticated_client):
        _seed(app)
        html = authenticated_client.get('/riftbound/collection?per_page=100').get_data(as_text=True)
        assert '5.00 €' in html     # r01
        assert '2.00 €' in html     # c05 latest row
        assert '1.20 €' in html     # r02 low_foil
        assert '<td>-</td>' in html  # c04 / c08 have no price

    @pytest.mark.parametrize('rarity', ['Common', 'Uncommon', 'Rare', 'Epic', 'Showcase'])
    def test_export_prices_follow_the_chain(self, app, authenticated_client, rarity):
        _seed(app)
        resp = authenticated_client.post(
            '/riftbound/collection/export_csv',
            json={'rbset_id': SET_ID, 'rarity': rarity},
        )
        assert resp.status_code == 200
        rows = list(csv.reader(io.StringIO(resp.get_data(as_text=True).lstrip('﻿'))))
        assert rows[0] == ['name', 'language', 'quantity', 'price']

        expected = {
            f'Card {card_id}': f'{(price if price is not None else 0.0):.2f}'
            for card_id, card_rarity, _f, _m, _p, price in CASES
            if card_rarity == rarity
        }
        assert expected, 'every parametrized rarity must have at least one case'
        got = {name: price for name, _lang, qty, price in rows[1:] if qty == '2'}
        assert got == expected
        assert int(resp.headers['X-Rows-Exported']) == len(expected)

    def test_export_uses_manual_sell_price_before_market_price(self, app, authenticated_client):
        _seed(app)
        with app.app_context():
            row = RbCollection.query.filter_by(rbcol_rbcar_id='r01').one()
            row.rbcol_sell_price = 9.5
            db.session.commit()
        resp = authenticated_client.post(
            '/riftbound/collection/export_csv',
            json={'rbset_id': SET_ID, 'rarity': 'Rare'},
        )
        rows = {r[0]: r[3] for r in csv.reader(io.StringIO(resp.get_data(as_text=True).lstrip('﻿')))}
        assert rows['Card r01'] == '9.50'
        assert rows['Card r02'] == '1.20'


# ---------------------------------------------------------------------------
# PRC-2: one shared implementation (canonical product, latest row, deck view)
# ---------------------------------------------------------------------------

def _add_card(set_id, card_id, rarity, mappings=(), prices=None):
    """Seed one catalog card with Cardmarket mappings [(id_product, foil)] and
    prices {id_product: [(date, {column: value})]}."""
    if not RbSet.query.get(set_id):
        db.session.add(RbSet(rbset_id=set_id, rbset_name=f'Set {set_id}'))
    db.session.add(RbCard(rbcar_rbset_id=set_id, rbcar_id=card_id,
                          rbcar_name=f'Card {card_id}', rbcar_rarity=rarity))
    for id_product, foil in mappings:
        db.session.add(RbcmProductCardMap(
            rbpcm_id_product=id_product, rbpcm_rbset_id=set_id,
            rbpcm_rbcar_id=card_id, rbpcm_foil=foil))
    for id_product, rows in (prices or {}).items():
        for date, columns in rows:
            db.session.add(RbcmPrice(
                rbprc_date=date, rbprc_id_product=id_product,
                **{f'rbprc_{name}': value for name, value in columns.items()}))
    db.session.commit()


class TestCanonicalProductId:
    """Same rule as the collection query: MIN(id_product), preferring the
    mapping of the right foil, then an unclassified one, then any."""

    def test_unmapped_card_has_no_product(self, app):
        _add_card('DK', 'x1', 'Common')
        assert canonical_product_id('DK', 'x1') is None

    def test_lowest_id_among_several_mappings(self, app):
        _add_card('DK', 'x1', 'Common', mappings=[(108, 'N'), (107, 'N')])
        assert canonical_product_id('DK', 'x1') == 107

    def test_exact_foil_mapping_beats_a_lower_id_of_the_other_foil(self, app):
        _add_card('DK', 'x1', 'Common', mappings=[(11, 'N'), (12, 'S')])
        assert canonical_product_id('DK', 'x1', 'N') == 11
        assert canonical_product_id('DK', 'x1', 'S') == 12

    def test_default_foil_is_normal(self, app):
        _add_card('DK', 'x1', 'Common', mappings=[(5, 'S'), (9, 'N')])
        assert canonical_product_id('DK', 'x1') == 9

    def test_unclassified_mapping_serves_either_foil(self, app):
        _add_card('DK', 'x1', 'Rare', mappings=[(201, None)])
        assert canonical_product_id('DK', 'x1', 'N') == 201
        assert canonical_product_id('DK', 'x1', 'S') == 201

    def test_without_an_exact_foil_any_mapping_is_the_approximation(self, app):
        _add_card('DK', 'x1', 'Common', mappings=[(106, 'S')])
        assert canonical_product_id('DK', 'x1', 'N') == 106

    def test_mappings_of_other_cards_do_not_leak(self, app):
        _add_card('DK', 'x1', 'Common', mappings=[(1, 'N')])
        _add_card('DK', 'x2', 'Common', mappings=[(2, 'N')])
        assert canonical_product_id('DK', 'x2') == 2


class TestLatestPriceForCard:
    def test_common_card_uses_avg7(self, app):
        _add_card('DK', 'x1', 'Common', [(11, 'N')],
                  {11: [('20261001', dict(avg7=0.10, avg7_foil=0.90))]})
        assert latest_price_for_card('DK', 'x1', rarity='Common') == 0.10

    def test_rare_card_uses_avg7_foil(self, app):
        _add_card('DK', 'x1', 'Rare', [(12, None)],
                  {12: [('20261001', dict(avg7=3.0, avg7_foil=5.0))]})
        assert latest_price_for_card('DK', 'x1', rarity='Rare') == 5.0

    def test_latest_dated_row_wins(self, app):
        _add_card('DK', 'x1', 'Common', [(13, 'N')],
                  {13: [('20261001', dict(avg7=1.0)), ('20261002', dict(avg7=2.0))]})
        assert latest_price_for_card('DK', 'x1', rarity='Common') == 2.0

    def test_unmapped_card_has_no_price(self, app):
        _add_card('DK', 'x1', 'Common')
        assert latest_price_for_card('DK', 'x1', rarity='Common') is None

    def test_mapped_but_never_priced_has_no_price(self, app):
        _add_card('DK', 'x1', 'Common', [(14, 'N')])
        assert latest_price_for_card('DK', 'x1', rarity='Common') is None

    def test_foil_argument_changes_the_chain(self, app):
        _add_card('DK', 'x1', 'Common', [(15, 'N'), (16, 'S')],
                  {15: [('20261001', dict(avg7=0.1, avg7_foil=0.9))],
                   16: [('20261001', dict(avg7=0.2, avg7_foil=0.8))]})
        assert latest_price_for_card('DK', 'x1', rarity='Common', foil='N') == 0.1
        assert latest_price_for_card('DK', 'x1', rarity='Common', foil='S') == 0.8


class TestDeckPrices:
    """PRC-2: the deck page shows the same prices the collection does."""

    @staticmethod
    def deck_cards(app, client, card_ids):
        from app.models import RbDeck
        db.session.add(RbDeck(
            rbdck_user='testuser', rbdck_name='Priced', rbdck_seq=1,
            rbdck_cards={'main': [{'set': SET_ID, 'id': c, 'qty': 1} for c in card_ids]}))
        db.session.commit()
        deck_id = RbDeck.query.filter_by(rbdck_name='Priced').one().id
        with _captured_templates(app) as rendered:
            resp = client.get(f'/riftbound/deck/view/{deck_id}')
        assert resp.status_code == 200
        (_, context), = [r for r in rendered if r[0].name == 'deck_view.html']
        return {c['card_id']: c['price'] for c in context['deck'].cards}

    def test_rare_card_with_only_low_is_priced_like_the_collection(
            self, app, authenticated_client):
        _add_card(SET_ID, 'r3', 'Rare', [(203, None)], {203: [('20261001', dict(low=0.5))]})
        db.session.add(RbCollection(rbcol_rbset_id=SET_ID, rbcol_rbcar_id='r3', rbcol_foil='N',
                                    rbcol_user=USER, rbcol_quantity=1, rbcol_selling='Y'))
        db.session.commit()
        with _captured_templates(app) as rendered:
            authenticated_client.get('/riftbound/collection?per_page=100')
        (_, context), = [r for r in rendered if r[0].name == 'collection.html']
        in_collection = {d['card'].rbcar_id: d['price'] for d in context['collections_data']}

        in_deck = self.deck_cards(app, authenticated_client, ['r3'])
        assert in_collection == {'r3': 0.5}
        assert in_deck == {'r3': 0.5}

    def test_showcase_with_only_low_foil_is_priced(self, app, authenticated_client):
        _add_card(SET_ID, 's1', 'Showcase', [(301, None)],
                  {301: [('20261001', dict(low_foil=2.0))]})
        assert self.deck_cards(app, authenticated_client, ['s1']) == {'s1': 2.0}

    def test_common_card_falls_back_from_avg7_to_low(self, app, authenticated_client):
        _add_card(SET_ID, 'c2', 'Uncommon', [(102, 'N')],
                  {102: [('20261001', dict(low=0.2, low_foil=0.8))]})
        assert self.deck_cards(app, authenticated_client, ['c2']) == {'c2': 0.2}

    def test_latest_row_wins_and_unmapped_has_no_price(self, app, authenticated_client):
        _add_card(SET_ID, 'c5', 'Common', [(105, 'N')],
                  {105: [('20261001', dict(avg7=1.0)), ('20261002', dict(avg7=2.0))]})
        _add_card(SET_ID, 'c4', 'Common')
        assert self.deck_cards(app, authenticated_client, ['c5', 'c4']) == {'c5': 2.0, 'c4': None}


class TestNoOtherPriceRule:
    """PRC-2: no route picks a price column by its own rule."""

    ROUTES = __import__('pathlib').Path(__file__).resolve().parent.parent / 'app' / 'routes' / 'domains'

    def test_deck_routes_name_no_price_column(self):
        import re
        assert not re.search(r'rbprc_(avg7|low)', (self.ROUTES / 'deck.py').read_text(encoding='utf-8'))

    def test_collection_routes_only_sort_by_a_price_column(self):
        import re
        hits = [line.strip() for line in
                (self.ROUTES / 'collection.py').read_text(encoding='utf-8').splitlines()
                if re.search(r'rbprc_(avg7|low)', line)]
        # the only mention left is the ORDER BY key of the list's "price" column
        assert hits == ["'price': [RbcmPrice.rbprc_avg7, RbCollection.rbcol_rbset_id, "
                        "card_id_num, RbCollection.rbcol_id],"]

    def test_both_routes_call_the_shared_service(self):
        for name in ('deck.py', 'collection.py'):
            assert 'app.services.pricing' in (self.ROUTES / name).read_text(encoding='utf-8'), name
