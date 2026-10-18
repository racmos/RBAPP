"""
Characterization tests for the Cardmarket price fallback chain (PRC-1).

They pin the behavior introduced by commit 1ae1f6e BEFORE unit c moves the
chain into `app/services/pricing.py` (task 3.17 re-points the table below to
`resolve_price`). They must pass on the unchanged code.

  - TestResolvePriceChain ... table-driven, against `collection._resolve_price`
  - TestCollectionRoutes .... route level: the SQL join (canonical product,
    latest price row, fallback mapping) plus the chain, through the collection
    list and the CSV export.

Rule R5: a falsy value (NULL or 0) counts as missing, exactly as the `or`
chain does today.
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
from app.routes.domains.collection import _resolve_price


# ---------------------------------------------------------------------------
# PRC-1 pure chain
# ---------------------------------------------------------------------------

def _row(avg7=None, avg7_foil=None, low=None, low_foil=None):
    return SimpleNamespace(
        rbprc_avg7=avg7, rbprc_avg7_foil=avg7_foil,
        rbprc_low=low, rbprc_low_foil=low_foil,
    )


def _resolve(row, rarity, foil):
    card = SimpleNamespace(rbcar_rarity=rarity)
    col = SimpleNamespace(rbcol_foil=foil)
    return _resolve_price(col, row, card)


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

    # No card at all: the common chain is used (rarity is '').
    def test_no_card_uses_common_chain_for_non_foil(self):
        col = SimpleNamespace(rbcol_foil='N')
        assert _resolve_price(col, _row(avg7=0.1, avg7_foil=0.9), None) == 0.1

    def test_no_card_with_foil_uses_foil_first(self):
        col = SimpleNamespace(rbcol_foil='S')
        assert _resolve_price(col, _row(avg7=0.1, avg7_foil=0.9), None) == 0.9

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
