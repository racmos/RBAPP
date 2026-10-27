"""F2-c S2-S9: GET /riftbound/api/v1/cards filters, facets, pagination."""
from datetime import date
from unittest.mock import patch

import pytest
from sqlalchemy import event

from app import db
from app.models import RbCard, RbCollection, RbSet, RbcmPrice, RbcmProductCardMap
from app.services import bans

URL = '/riftbound/api/v1/cards'


def _seed_filters(app):
    """A small catalog with one printing per "base" name plus a promo."""
    with app.app_context():
        db.session.add_all([
            RbSet(rbset_id='OGN', rbset_name='Origins', rbset_outdat=date(2025, 10, 31)),
            RbSet(rbset_id='SFD', rbset_name='Spiritforged', rbset_outdat=date(2025, 11, 30)),
        ])
        db.session.add_all([
            RbCard(rbcar_rbset_id='OGN', rbcar_id='1', rbcar_name='Alpha Fury',
                   rbcar_domain='Fury', rbcar_type='Unit', rbcar_rarity='Common',
                   rbcar_energy=1, rbcar_power=1, rbcar_might=1,
                   rbcar_tags='Noxus', rbcar_ability='Charge.'),
            RbCard(rbcar_rbset_id='OGN', rbcar_id='2', rbcar_name='Beta Calm',
                   rbcar_domain='Calm', rbcar_type='Spell', rbcar_rarity='Uncommon',
                   rbcar_energy=2, rbcar_power=None, rbcar_might=None,
                   rbcar_tags='Ionia', rbcar_ability='Heal.'),
            RbCard(rbcar_rbset_id='OGN', rbcar_id='79', rbcar_name='Jinx, Loose Cannon',
                   rbcar_domain='Chaos', rbcar_type='Champion Unit', rbcar_rarity='Rare',
                   rbcar_energy=3, rbcar_power=4, rbcar_might=5,
                   rbcar_tags='Zaun', rbcar_ability='Boom.'),
            RbCard(rbcar_rbset_id='OGN', rbcar_id='79a', rbcar_name='Jinx, Loose Cannon',
                   rbcar_domain='Chaos', rbcar_type='Champion Unit', rbcar_rarity='Rare',
                   rbcar_energy=3, rbcar_power=4, rbcar_might=5,
                   rbcar_tags='Zaun', rbcar_ability='Boom.'),
            RbCard(rbcar_rbset_id='SFD', rbcar_id='10', rbcar_name='Delta Gear',
                   rbcar_domain='Fury Order', rbcar_type='Gear', rbcar_rarity='Epic',
                   rbcar_energy=None, rbcar_power=None, rbcar_might=6,
                   rbcar_tags='Noxus', rbcar_ability='Equip.'),
            RbCard(rbcar_rbset_id='SFD', rbcar_id='11', rbcar_name='Epsilon Legend',
                   rbcar_domain='Mind', rbcar_type='Legend', rbcar_rarity='Showcase',
                   rbcar_energy=0, rbcar_power=None, rbcar_might=None,
                   rbcar_tags='', rbcar_ability=''),
        ])
        db.session.add_all([
            RbcmProductCardMap(rbpcm_rbset_id='OGN', rbpcm_rbcar_id='1',
                               rbpcm_id_product=1, rbpcm_foil='N'),
            RbcmPrice(rbprc_date='20261020', rbprc_id_product=1, rbprc_avg7=10),
            RbcmProductCardMap(rbpcm_rbset_id='OGN', rbpcm_rbcar_id='2',
                               rbpcm_id_product=2, rbpcm_foil='N'),
            RbcmPrice(rbprc_date='20261020', rbprc_id_product=2, rbprc_avg7=5),
        ])
        db.session.commit()
        bans.add_ban('Jinx, Loose Cannon', ['1v1'])


def _keys(items):
    return [item['key'] for item in items]


class TestQueryValidation:
    def test_per_page_500_is_out_of_range(self, authenticated_client):
        resp = authenticated_client.get(URL, query_string={'per_page': 500})
        body = resp.get_json()
        assert resp.status_code == 400
        assert body['success'] is False
        assert body['code'] == 'validation_error'
        assert body['message'] == 'Invalid query parameters'
        assert body['details'] == [{
            'field': 'per_page',
            'message': 'Input should be less than or equal to 192',
            'type': 'less_than_equal',
            'code': 'out_of_range',
            'params': {'max': 192},
        }]

    def test_sort_popularity_is_invalid_value(self, authenticated_client):
        resp = authenticated_client.get(URL, query_string={'sort': 'popularity'})
        body = resp.get_json()
        assert resp.status_code == 400
        assert body['code'] == 'validation_error'
        assert body['message'] == 'Invalid query parameters'
        detail = body['details'][0]
        assert detail['field'] == 'sort'
        assert detail['code'] == 'invalid_value'

    def test_defaults(self, authenticated_client, app):
        _seed_filters(app)
        resp = authenticated_client.get(URL)
        body = resp.get_json()
        assert resp.status_code == 200
        assert body['success'] is True
        meta = body['meta']
        assert meta['page'] == 1
        assert meta['per_page'] == 48
        assert meta['total'] == 6
        assert meta['pages'] == 1
        assert len(body['data']['items']) == 6
        assert meta['price_as_of'] == '2026-10-20'

    def test_min_greater_than_max_returns_empty_200(self, authenticated_client, app):
        _seed_filters(app)
        resp = authenticated_client.get(URL, query_string={'energy_min': 5, 'energy_max': 4})
        body = resp.get_json()
        assert resp.status_code == 200
        assert body['data']['items'] == []
        assert body['meta']['total'] == 0
        assert body['meta']['pages'] == 0


class TestFilters:
    def test_q_digits_matches_number(self, authenticated_client, app):
        _seed_filters(app)
        resp = authenticated_client.get(URL, query_string={'q': '79'})
        assert _keys(resp.get_json()['data']['items']) == ['OGN-79', 'OGN-79a']

    def test_q_key_matches_exact_card(self, authenticated_client, app):
        _seed_filters(app)
        resp = authenticated_client.get(URL, query_string={'q': 'OGN-79'})
        assert _keys(resp.get_json()['data']['items']) == ['OGN-79']

    def test_q_tag_matches_case_insensitive(self, authenticated_client, app):
        _seed_filters(app)
        resp = authenticated_client.get(URL, query_string={'q': 'noxus'})
        assert _keys(resp.get_json()['data']['items']) == ['OGN-1', 'SFD-10']

    def test_text_filters_ability(self, authenticated_client, app):
        _seed_filters(app)
        resp = authenticated_client.get(URL, query_string={'text': 'heal'})
        assert _keys(resp.get_json()['data']['items']) == ['OGN-2']

    def test_set_filter(self, authenticated_client, app):
        _seed_filters(app)
        resp = authenticated_client.get(URL, query_string={'set': 'SFD'})
        assert _keys(resp.get_json()['data']['items']) == ['SFD-10', 'SFD-11']

    def test_rarity_filter(self, authenticated_client, app):
        _seed_filters(app)
        resp = authenticated_client.get(URL, query_string={'rarity': 'Rare'})
        assert _keys(resp.get_json()['data']['items']) == ['OGN-79', 'OGN-79a']

    def test_type_filter(self, authenticated_client, app):
        _seed_filters(app)
        resp = authenticated_client.get(URL, query_string={'type': 'Gear'})
        assert _keys(resp.get_json()['data']['items']) == ['SFD-10']

    def test_supertype_filter(self, authenticated_client, app):
        _seed_filters(app)
        resp = authenticated_client.get(URL, query_string={'supertype': 'Champion'})
        assert _keys(resp.get_json()['data']['items']) == ['OGN-79', 'OGN-79a']

    def test_exclude_supertype_keeps_null_supertype(self, authenticated_client, app):
        _seed_filters(app)
        resp = authenticated_client.get(URL, query_string={'exclude_supertype': 'Champion'})
        assert _keys(resp.get_json()['data']['items']) == [
            'OGN-1', 'OGN-2', 'SFD-10', 'SFD-11',
        ]

    def test_tag_filter(self, authenticated_client, app):
        _seed_filters(app)
        resp = authenticated_client.get(URL, query_string={'tag': 'Zaun'})
        assert _keys(resp.get_json()['data']['items']) == ['OGN-79', 'OGN-79a']

    def test_domain_match_any(self, authenticated_client, app):
        _seed_filters(app)
        resp = authenticated_client.get(URL, query_string={
            'domain': ['Fury', 'Mind'],
            'domain_match': 'any',
        })
        assert _keys(resp.get_json()['data']['items']) == ['OGN-1', 'SFD-10', 'SFD-11']

    def test_domain_match_all(self, authenticated_client, app):
        _seed_filters(app)
        resp = authenticated_client.get(URL, query_string={
            'domain': ['Fury', 'Order'],
            'domain_match': 'all',
        })
        assert _keys(resp.get_json()['data']['items']) == ['SFD-10']

    def test_domain_match_subset(self, authenticated_client, app):
        _seed_filters(app)
        resp = authenticated_client.get(URL, query_string={
            'domain': ['Fury', 'Calm'],
            'domain_match': 'subset',
        })
        assert _keys(resp.get_json()['data']['items']) == ['OGN-1', 'OGN-2']

    def test_range_excludes_null_values(self, authenticated_client, app):
        _seed_filters(app)
        resp = authenticated_client.get(URL, query_string={'energy_min': 1})
        assert _keys(resp.get_json()['data']['items']) == [
            'OGN-1', 'OGN-2', 'OGN-79', 'OGN-79a',
        ]

    def test_price_bounds_exclude_cards_without_price(self, authenticated_client, app):
        _seed_filters(app)
        resp = authenticated_client.get(URL, query_string={'price_min': 7})
        assert _keys(resp.get_json()['data']['items']) == ['OGN-1']

    def test_banned_in(self, authenticated_client, app):
        _seed_filters(app)
        resp = authenticated_client.get(URL, query_string={'banned_in': '1v1'})
        assert _keys(resp.get_json()['data']['items']) == ['OGN-79', 'OGN-79a']

    def test_base_only_excludes_promo_printings(self, authenticated_client, app):
        _seed_filters(app)
        resp = authenticated_client.get(URL, query_string={'base_only': 'true'})
        assert _keys(resp.get_json()['data']['items']) == [
            'OGN-1', 'OGN-2', 'OGN-79', 'SFD-10', 'SFD-11',
        ]

    def test_owned_missing_includes_everyone(self, authenticated_client, app):
        _seed_filters(app)
        resp = authenticated_client.get(URL, query_string={'owned': 'missing'})
        assert len(resp.get_json()['data']['items']) == 6

    def test_owned_owned_is_empty_without_collection_rows(self, authenticated_client, app):
        _seed_filters(app)
        resp = authenticated_client.get(URL, query_string={'owned': 'owned'})
        assert resp.get_json()['data']['items'] == []


class TestFacets:
    def _seed_s4(self, app):
        with app.app_context():
            db.session.add(RbSet(rbset_id='OGN', rbset_name='Origins',
                                 rbset_outdat=date(2025, 6, 1)))
            db.session.add_all([
                RbCard(rbcar_rbset_id='OGN', rbcar_id='1', rbcar_name='Fury One',
                       rbcar_domain='Fury', rbcar_type='Unit', rbcar_rarity='Common',
                       rbcar_tags='aggro'),
                RbCard(rbcar_rbset_id='OGN', rbcar_id='2', rbcar_name='Fury Two',
                       rbcar_domain='Fury', rbcar_type='Unit', rbcar_rarity='Common',
                       rbcar_tags='aggro'),
                RbCard(rbcar_rbset_id='OGN', rbcar_id='3', rbcar_name='Fury Three',
                       rbcar_domain='Fury', rbcar_type='Unit', rbcar_rarity='Uncommon',
                       rbcar_tags='combo'),
                RbCard(rbcar_rbset_id='OGN', rbcar_id='4', rbcar_name='Calm One',
                       rbcar_domain='Calm', rbcar_type='Spell', rbcar_rarity='Common',
                       rbcar_tags='aggro'),
                RbCard(rbcar_rbset_id='OGN', rbcar_id='5', rbcar_name='Calm Two',
                       rbcar_domain='Calm', rbcar_type='Spell', rbcar_rarity='Rare',
                       rbcar_tags='control'),
            ])
            db.session.commit()

    def _seed_order(self, app):
        with app.app_context():
            db.session.add_all([
                RbSet(rbset_id='OGN', rbset_name='Origins', rbset_outdat=date(2025, 6, 1)),
                RbSet(rbset_id='SFD', rbset_name='Spiritforged', rbset_outdat=date(2025, 9, 1)),
            ])
            db.session.add_all([
                RbCard(rbcar_rbset_id='OGN', rbcar_id='1', rbcar_name='Fury One',
                       rbcar_domain='Fury', rbcar_type='Unit', rbcar_rarity='Common'),
                RbCard(rbcar_rbset_id='OGN', rbcar_id='2', rbcar_name='Calm One',
                       rbcar_domain='Calm', rbcar_type='Spell', rbcar_rarity='Uncommon'),
                RbCard(rbcar_rbset_id='OGN', rbcar_id='3', rbcar_name='Body One',
                       rbcar_domain='Body', rbcar_type='Legend', rbcar_rarity='Rare'),
                RbCard(rbcar_rbset_id='SFD', rbcar_id='1', rbcar_name='Chaos One',
                       rbcar_domain='Chaos', rbcar_type='Gear', rbcar_rarity='Epic'),
            ])
            db.session.commit()

    def _seed_tags(self, app):
        with app.app_context():
            db.session.add(RbSet(rbset_id='OGN', rbset_name='Origins',
                                 rbset_outdat=date(2025, 6, 1)))
            for i in range(35):
                db.session.add(RbCard(
                    rbcar_rbset_id='OGN',
                    rbcar_id=str(100 + i),
                    rbcar_name=f'Tag Card {i}',
                    rbcar_domain='Fury',
                    rbcar_type='Unit',
                    rbcar_rarity='Common',
                    rbcar_tags=f'tag_{i:02d}',
                ))
            db.session.commit()

    def test_s4_example(self, authenticated_client, app):
        self._seed_s4(app)
        resp = authenticated_client.get(URL, query_string={'domain': 'Fury'})
        body = resp.get_json()
        assert resp.status_code == 200
        assert _keys(body['data']['items']) == ['OGN-1', 'OGN-2', 'OGN-3']
        assert body['meta']['facets']['domain'] == {'Fury': 3, 'Calm': 2}
        assert body['meta']['facets']['set'] == {'OGN': 3}

    def test_disjunctive_counts(self, authenticated_client, app):
        self._seed_s4(app)
        resp = authenticated_client.get(URL, query_string={
            'domain': 'Fury',
            'rarity': 'Common',
        })
        facets = resp.get_json()['meta']['facets']
        # rarity filter stays; domain facet ignores the domain filter.
        assert facets['domain'] == {'Fury': 2, 'Calm': 1}
        # domain filter stays; rarity facet ignores the rarity filter.
        assert facets['rarity'] == {'Common': 2, 'Uncommon': 1}

    def test_canonical_order(self, authenticated_client, app):
        self._seed_order(app)
        resp = authenticated_client.get(URL)
        facets = resp.get_json()['meta']['facets']
        assert list(facets['set'].keys()) == ['OGN', 'SFD']
        assert list(facets['domain'].keys()) == ['Fury', 'Calm', 'Body', 'Chaos']
        assert list(facets['type'].keys()) == ['Legend', 'Unit', 'Spell', 'Gear']
        assert list(facets['rarity'].keys()) == ['Common', 'Uncommon', 'Rare', 'Epic']

    def test_top_30_tags(self, authenticated_client, app):
        self._seed_tags(app)
        resp = authenticated_client.get(URL, query_string={'domain': 'Fury'})
        tags = resp.get_json()['meta']['facets']['tag']
        assert len(tags) == 30
        expected = [{'tag': f'tag_{i:02d}', 'count': 1} for i in range(30)]
        assert tags == expected


def _seed_sort(app):
    """Five-card catalog with distinct sort attributes and prices."""
    with app.app_context():
        db.session.add_all([
            RbSet(rbset_id='OGN', rbset_name='Origins', rbset_outdat=date(2025, 6, 1)),
            RbSet(rbset_id='SFD', rbset_name='Spiritforged', rbset_outdat=date(2025, 9, 1)),
        ])
        db.session.add_all([
            RbCard(rbcar_rbset_id='OGN', rbcar_id='1', rbcar_name='Alpha',
                   rbcar_domain='Fury', rbcar_type='Unit', rbcar_rarity='Common',
                   rbcar_energy=1, rbcar_power=1, rbcar_might=1),
            RbCard(rbcar_rbset_id='OGN', rbcar_id='2', rbcar_name='beta',
                   rbcar_domain='Calm', rbcar_type='Unit', rbcar_rarity='Uncommon',
                   rbcar_energy=2, rbcar_power=None, rbcar_might=2),
            RbCard(rbcar_rbset_id='OGN', rbcar_id='10', rbcar_name='Gamma',
                   rbcar_domain='Body', rbcar_type='Unit', rbcar_rarity='Rare',
                   rbcar_energy=3, rbcar_power=3, rbcar_might=None),
            RbCard(rbcar_rbset_id='SFD', rbcar_id='1', rbcar_name='delta',
                   rbcar_domain='Chaos', rbcar_type='Unit', rbcar_rarity='Epic',
                   rbcar_energy=None, rbcar_power=4, rbcar_might=4),
            RbCard(rbcar_rbset_id='SFD', rbcar_id='2', rbcar_name='Epsilon',
                   rbcar_domain='Order', rbcar_type='Unit', rbcar_rarity='Showcase',
                   rbcar_energy=0, rbcar_power=0, rbcar_might=0),
        ])
        db.session.add_all([
            # OGN-1: 7d trend +25.0, 30d None
            RbcmProductCardMap(rbpcm_rbset_id='OGN', rbpcm_rbcar_id='1',
                               rbpcm_id_product=1, rbpcm_foil='N'),
            RbcmPrice(rbprc_date='20261020', rbprc_id_product=1, rbprc_avg7=10),
            RbcmPrice(rbprc_date='20261013', rbprc_id_product=1, rbprc_avg7=8),
            # OGN-2: 7d trend -16.7, 30d None
            RbcmProductCardMap(rbpcm_rbset_id='OGN', rbpcm_rbcar_id='2',
                               rbpcm_id_product=2, rbpcm_foil='N'),
            RbcmPrice(rbprc_date='20261020', rbprc_id_product=2, rbprc_avg7=5),
            RbcmPrice(rbprc_date='20261013', rbprc_id_product=2, rbprc_avg7=6),
            # OGN-10: 7d None (no row <= 20261013), 30d trend +100.0
            RbcmProductCardMap(rbpcm_rbset_id='OGN', rbpcm_rbcar_id='10',
                               rbpcm_id_product=3, rbpcm_foil='N'),
            RbcmPrice(rbprc_date='20261020', rbprc_id_product=3, rbprc_avg7=20),
            RbcmPrice(rbprc_date='20261014', rbprc_id_product=3, rbprc_avg7=15),
            RbcmPrice(rbprc_date='20260920', rbprc_id_product=3, rbprc_avg7=10),
            # SFD-1: 7d trend 0.0, 30d None; same price as OGN-1 to test tiebreak
            RbcmProductCardMap(rbpcm_rbset_id='SFD', rbpcm_rbcar_id='1',
                               rbpcm_id_product=4, rbpcm_foil='N'),
            RbcmPrice(rbprc_date='20261020', rbprc_id_product=4, rbprc_avg7=10),
            RbcmPrice(rbprc_date='20261010', rbprc_id_product=4, rbprc_avg7=10),
            # SFD-2: no price -> nulls in price/trend sorts
        ])
        db.session.commit()


def _seed_owned(app):
    """Three cards with collection rows for two users."""
    with app.app_context():
        db.session.add(RbSet(rbset_id='OGN', rbset_name='Origins',
                             rbset_outdat=date(2025, 6, 1)))
        db.session.add_all([
            RbCard(rbcar_rbset_id='OGN', rbcar_id='1', rbcar_name='One',
                   rbcar_domain='Fury', rbcar_type='Unit', rbcar_rarity='Common'),
            RbCard(rbcar_rbset_id='OGN', rbcar_id='2', rbcar_name='Two',
                   rbcar_domain='Fury', rbcar_type='Unit', rbcar_rarity='Common'),
            RbCard(rbcar_rbset_id='OGN', rbcar_id='3', rbcar_name='Three',
                   rbcar_domain='Fury', rbcar_type='Unit', rbcar_rarity='Common'),
        ])
        db.session.commit()


def _add_collection(app, username, rows):
    """rows: list of (set_id, card_id, foil, quantity)."""
    with app.app_context():
        for set_id, card_id, foil, quantity in rows:
            db.session.add(RbCollection(
                rbcol_rbset_id=set_id,
                rbcol_rbcar_id=card_id,
                rbcol_user=username,
                rbcol_foil=foil,
                rbcol_quantity=quantity,
            ))
        db.session.commit()


def _seed_200(app):
    """200 cards across two sets, with prices for every other card."""
    with app.app_context():
        db.session.add_all([
            RbSet(rbset_id='OGN', rbset_name='Origins', rbset_outdat=date(2025, 6, 1)),
            RbSet(rbset_id='SFD', rbset_name='Spiritforged', rbset_outdat=date(2025, 9, 1)),
        ])
        products = []
        prices = []
        for i in range(200):
            set_id = 'OGN' if i < 100 else 'SFD'
            card_id = str(i + 1)
            db.session.add(RbCard(
                rbcar_rbset_id=set_id,
                rbcar_id=card_id,
                rbcar_name=f'Card {card_id}',
                rbcar_domain='Fury',
                rbcar_type='Unit',
                rbcar_rarity='Common',
            ))
            if i % 2 == 0:
                products.append(RbcmProductCardMap(
                    rbpcm_rbset_id=set_id, rbpcm_rbcar_id=card_id,
                    rbpcm_id_product=i + 1, rbpcm_foil='N'))
                prices.append(RbcmPrice(
                    rbprc_date='20261020', rbprc_id_product=i + 1, rbprc_avg7=1))
        db.session.add_all(products)
        db.session.add_all(prices)
        db.session.commit()


class TestSortAndPages:
    def test_sort_number_asc(self, authenticated_client, app):
        _seed_sort(app)
        resp = authenticated_client.get(URL, query_string={'sort': 'number', 'dir': 'asc'})
        assert _keys(resp.get_json()['data']['items']) == [
            'OGN-1', 'OGN-2', 'OGN-10', 'SFD-1', 'SFD-2']

    def test_sort_number_desc(self, authenticated_client, app):
        _seed_sort(app)
        resp = authenticated_client.get(URL, query_string={'sort': 'number', 'dir': 'desc'})
        # number sort desc reverses natural_key; no separate tiebreak applies.
        assert _keys(resp.get_json()['data']['items']) == [
            'SFD-2', 'SFD-1', 'OGN-10', 'OGN-2', 'OGN-1']

    def test_sort_name_asc(self, authenticated_client, app):
        _seed_sort(app)
        resp = authenticated_client.get(URL, query_string={'sort': 'name', 'dir': 'asc'})
        assert _keys(resp.get_json()['data']['items']) == [
            'OGN-1', 'OGN-2', 'SFD-1', 'SFD-2', 'OGN-10']

    def test_sort_name_desc(self, authenticated_client, app):
        _seed_sort(app)
        resp = authenticated_client.get(URL, query_string={'sort': 'name', 'dir': 'desc'})
        assert _keys(resp.get_json()['data']['items']) == [
            'OGN-10', 'SFD-2', 'SFD-1', 'OGN-2', 'OGN-1']

    def test_sort_rarity_asc(self, authenticated_client, app):
        _seed_sort(app)
        resp = authenticated_client.get(URL, query_string={'sort': 'rarity', 'dir': 'asc'})
        assert _keys(resp.get_json()['data']['items']) == [
            'OGN-1', 'OGN-2', 'OGN-10', 'SFD-1', 'SFD-2']

    def test_sort_rarity_desc(self, authenticated_client, app):
        _seed_sort(app)
        resp = authenticated_client.get(URL, query_string={'sort': 'rarity', 'dir': 'desc'})
        assert _keys(resp.get_json()['data']['items']) == [
            'SFD-2', 'SFD-1', 'OGN-10', 'OGN-2', 'OGN-1']

    def test_sort_price_asc_nulls_last_with_tiebreak(self, authenticated_client, app):
        _seed_sort(app)
        resp = authenticated_client.get(URL, query_string={'sort': 'price', 'dir': 'asc'})
        # OGN-2=5, OGN-1=10, SFD-1=10 (tiebreak OGN before SFD), OGN-10=20, SFD-2=None
        assert _keys(resp.get_json()['data']['items']) == [
            'OGN-2', 'OGN-1', 'SFD-1', 'OGN-10', 'SFD-2']

    def test_sort_price_desc_nulls_last(self, authenticated_client, app):
        _seed_sort(app)
        resp = authenticated_client.get(URL, query_string={'sort': 'price', 'dir': 'desc'})
        # OGN-1 and SFD-1 both price 10; natural_key tiebreak puts OGN first.
        assert _keys(resp.get_json()['data']['items']) == [
            'OGN-10', 'OGN-1', 'SFD-1', 'OGN-2', 'SFD-2']

    def test_sort_trend_7d_asc_nulls_last(self, authenticated_client, app):
        _seed_sort(app)
        resp = authenticated_client.get(URL, query_string={'sort': 'trend_7d', 'dir': 'asc'})
        items = resp.get_json()['data']['items']
        assert _keys(items) == ['OGN-2', 'SFD-1', 'OGN-1', 'OGN-10', 'SFD-2']
        assert items[0]['price']['trend_7d_pct'] == -16.7
        assert items[1]['price']['trend_7d_pct'] == 0.0
        assert items[2]['price']['trend_7d_pct'] == 25.0
        assert items[3]['price']['trend_7d_pct'] == 100.0
        assert items[4]['price'] is None

    def test_sort_trend_7d_desc_nulls_last(self, authenticated_client, app):
        _seed_sort(app)
        resp = authenticated_client.get(URL, query_string={'sort': 'trend_7d', 'dir': 'desc'})
        assert _keys(resp.get_json()['data']['items']) == [
            'OGN-10', 'OGN-1', 'SFD-1', 'OGN-2', 'SFD-2']

    def test_sort_trend_30d_asc_nulls_last(self, authenticated_client, app):
        _seed_sort(app)
        resp = authenticated_client.get(URL, query_string={'sort': 'trend_30d', 'dir': 'asc'})
        assert _keys(resp.get_json()['data']['items']) == [
            'OGN-10', 'OGN-1', 'OGN-2', 'SFD-1', 'SFD-2']

    def test_sort_trend_30d_desc_nulls_last(self, authenticated_client, app):
        _seed_sort(app)
        resp = authenticated_client.get(URL, query_string={'sort': 'trend_30d', 'dir': 'desc'})
        assert _keys(resp.get_json()['data']['items']) == [
            'OGN-10', 'OGN-1', 'OGN-2', 'SFD-1', 'SFD-2']

    def test_sort_energy_asc_nulls_last(self, authenticated_client, app):
        _seed_sort(app)
        resp = authenticated_client.get(URL, query_string={'sort': 'energy', 'dir': 'asc'})
        assert _keys(resp.get_json()['data']['items']) == [
            'SFD-2', 'OGN-1', 'OGN-2', 'OGN-10', 'SFD-1']

    def test_sort_energy_desc_nulls_last(self, authenticated_client, app):
        _seed_sort(app)
        resp = authenticated_client.get(URL, query_string={'sort': 'energy', 'dir': 'desc'})
        assert _keys(resp.get_json()['data']['items']) == [
            'OGN-10', 'OGN-2', 'OGN-1', 'SFD-2', 'SFD-1']

    def test_sort_power_asc_nulls_last(self, authenticated_client, app):
        _seed_sort(app)
        resp = authenticated_client.get(URL, query_string={'sort': 'power', 'dir': 'asc'})
        assert _keys(resp.get_json()['data']['items']) == [
            'SFD-2', 'OGN-1', 'OGN-10', 'SFD-1', 'OGN-2']

    def test_sort_power_desc_nulls_last(self, authenticated_client, app):
        _seed_sort(app)
        resp = authenticated_client.get(URL, query_string={'sort': 'power', 'dir': 'desc'})
        assert _keys(resp.get_json()['data']['items']) == [
            'SFD-1', 'OGN-10', 'OGN-1', 'SFD-2', 'OGN-2']

    def test_sort_might_asc_nulls_last(self, authenticated_client, app):
        _seed_sort(app)
        resp = authenticated_client.get(URL, query_string={'sort': 'might', 'dir': 'asc'})
        assert _keys(resp.get_json()['data']['items']) == [
            'SFD-2', 'OGN-1', 'OGN-2', 'SFD-1', 'OGN-10']

    def test_sort_might_desc_nulls_last(self, authenticated_client, app):
        _seed_sort(app)
        resp = authenticated_client.get(URL, query_string={'sort': 'might', 'dir': 'desc'})
        assert _keys(resp.get_json()['data']['items']) == [
            'SFD-1', 'OGN-2', 'OGN-1', 'SFD-2', 'OGN-10']

    def test_pagination_total_pages_and_past_the_end(self, authenticated_client, app):
        _seed_sort(app)
        resp = authenticated_client.get(URL, query_string={'per_page': 2})
        body = resp.get_json()
        assert body['meta']['total'] == 5
        assert body['meta']['pages'] == 3
        assert len(body['data']['items']) == 2

        resp = authenticated_client.get(URL, query_string={'per_page': 2, 'page': 3})
        body = resp.get_json()
        assert len(body['data']['items']) == 1

        resp = authenticated_client.get(URL, query_string={'per_page': 2, 'page': 4})
        body = resp.get_json()
        assert resp.status_code == 200
        assert body['data']['items'] == []
        assert body['meta']['total'] == 5
        assert body['meta']['pages'] == 3

    def test_price_as_of_set(self, authenticated_client, app):
        _seed_sort(app)
        resp = authenticated_client.get(URL)
        assert resp.get_json()['meta']['price_as_of'] == '2026-10-20'

    def test_price_as_of_null(self, authenticated_client, app):
        with app.app_context():
            db.session.add(RbSet(rbset_id='OGN', rbset_name='Origins',
                                 rbset_outdat=date(2025, 6, 1)))
            db.session.add(RbCard(rbcar_rbset_id='OGN', rbcar_id='1',
                                  rbcar_name='Only', rbcar_domain='Fury',
                                  rbcar_type='Unit', rbcar_rarity='Common'))
            db.session.commit()
        resp = authenticated_client.get(URL)
        assert resp.get_json()['meta']['price_as_of'] is None


class TestOwned:
    def test_owned_totals_sum_quantity(self, authenticated_client, app):
        _seed_owned(app)
        _add_collection(app, 'testuser', [
            ('OGN', '1', 'N', 2),
            ('OGN', '1', 'S', 1),
            ('OGN', '2', 'N', 3),
        ])
        resp = authenticated_client.get(URL, query_string={
            'set': 'OGN',
            'sort': 'name',
            'dir': 'asc',
        })
        items = resp.get_json()['data']['items']
        assert {item['key']: item['owned'] for item in items} == {
            'OGN-1': {'total': 3, 'foil': 1},
            'OGN-2': {'total': 3, 'foil': 0},
            'OGN-3': {'total': 0, 'foil': 0},
        }

    def test_owned_never_includes_other_user(self, authenticated_client, app, make_user):
        _seed_owned(app)
        make_user('otheruser')
        _add_collection(app, 'testuser', [('OGN', '1', 'N', 2)])
        _add_collection(app, 'otheruser', [
            ('OGN', '1', 'N', 99),
            ('OGN', '2', 'S', 50),
        ])
        resp = authenticated_client.get(URL, query_string={
            'set': 'OGN',
            'sort': 'name',
            'dir': 'asc',
        })
        items = resp.get_json()['data']['items']
        assert {item['key']: item['owned'] for item in items} == {
            'OGN-1': {'total': 2, 'foil': 0},
            'OGN-2': {'total': 0, 'foil': 0},
            'OGN-3': {'total': 0, 'foil': 0},
        }


class TestPriceScope:
    def test_default_query_prices_only_the_page(self, authenticated_client, app):
        _seed_sort(app)
        from app.services import pricing
        calls = []
        original = pricing.price_summaries

        def spy(items):
            calls.append(len(list(items)))
            return original(items)

        with patch.object(pricing, 'price_summaries', spy):
            resp = authenticated_client.get(URL, query_string={'per_page': 2})
        assert resp.status_code == 200
        assert calls == [2]

    def test_sort_price_prices_all_matches(self, authenticated_client, app):
        _seed_sort(app)
        from app.services import pricing
        calls = []
        original = pricing.price_summaries

        def spy(items):
            calls.append(len(list(items)))
            return original(items)

        with patch.object(pricing, 'price_summaries', spy):
            resp = authenticated_client.get(URL, query_string={
                'sort': 'price', 'dir': 'desc', 'per_page': 2})
        assert resp.status_code == 200
        assert calls == [5]


class TestStatementBound:
    def _count_statements(self, app, client, query_string):
        counts = []

        def listener(conn, cursor, statement, parameters, context, executemany):
            counts.append(statement)

        with app.app_context():
            event.listen(db.engine, 'before_cursor_execute', listener)
            try:
                resp = client.get(URL, query_string=query_string)
                assert resp.status_code == 200
            finally:
                event.remove(db.engine, 'before_cursor_execute', listener)
        return len(counts)

    def test_default_query_under_12_statements(self, authenticated_client, app):
        _seed_200(app)
        count = self._count_statements(app, authenticated_client, {})
        assert count <= 12

    def test_sort_price_query_under_12_statements(self, authenticated_client, app):
        _seed_200(app)
        count = self._count_statements(app, authenticated_client,
                                       {'sort': 'price', 'dir': 'desc'})
        assert count <= 12


class TestAuthzAndShape:
    def test_anonymous_gets_a_json_401(self, client):
        resp = client.get(URL)
        assert resp.status_code == 401
        assert 'Location' not in resp.headers
        body = resp.get_json()
        assert (body['success'], body['error'], body['code']) == (False, 'Unauthorized',
                                                                   'unauthenticated')

    def test_endpoint_name(self, app):
        rules = [r for r in app.url_map.iter_rules() if r.rule == URL]
        assert [(r.endpoint, sorted(r.methods - {'HEAD', 'OPTIONS'})) for r in rules] == [
            ('api_v1.list_cards', ['GET'])]
