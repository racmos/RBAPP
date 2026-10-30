"""Owner feedback S18 (g): compound types and domain pairs count under their base values.

`rbcar_type` stores the gallery's "<supertype> <type>" ("Champion Unit", "Token Battlefield",
a bare "Token") and `rbcar_domain` the domains separated by spaces ("Body Chaos"). Facets,
filters and `GET /meta/game` only offer the canonical values of `game_domain.py` (plus values
that are truly unknown); a card counts under each canonical value it has.
"""
import json
from datetime import date
from pathlib import Path

import pytest

from app import db
from app.models import RbCard, RbCollection, RbSet
from app.schemas.game_domain import CARD_TYPES, DOMAINS, RARITIES, SUPERTYPES
from app.services import catalog

CARDS = '/riftbound/api/v1/cards'
COLLECTION = '/riftbound/api/v1/collection'
META = '/riftbound/api/v1/meta/game'
LOCALES = Path(__file__).resolve().parent.parent / 'frontend' / 'src' / 'i18n' / 'locales'


def _seed(app):
    with app.app_context():
        db.session.add_all([
            RbSet(rbset_id='OGN', rbset_name='Origins', rbset_outdat=date(2025, 10, 31)),
            RbSet(rbset_id='SFD', rbset_name='Spiritforged', rbset_outdat=date(2025, 11, 30)),
        ])
        rows = [
            ('OGN', '1', 'Champion Unit', 'Body Chaos'),
            ('OGN', '2', 'Signature Spell', 'Calm Order'),
            ('OGN', '3', 'Basic Rune', 'Body'),
            ('OGN', '4', 'Token Unit', 'Fury'),
            ('OGN', '5', 'Token', 'Colorless'),
            ('OGN', '6', 'Unit', 'Fury Mind'),
            ('OGN', '7', 'Token Battlefield', None),
            ('SFD', '1', 'Creature', 'Weird'),
        ]
        db.session.add_all([
            RbCard(rbcar_rbset_id=set_id, rbcar_id=card_id, rbcar_name=f'Card {set_id} {card_id}',
                   rbcar_type=card_type, rbcar_domain=domain, rbcar_rarity='Common')
            for set_id, card_id, card_type, domain in rows])
        db.session.commit()


def _keys(body):
    return [item['key'] for item in body['data']['items']]


@pytest.fixture
def cards(app, authenticated_client):
    _seed(app)
    return authenticated_client


def _list(client, **params):
    response = client.get(CARDS, query_string=params)
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()


class TestTypeFacets:
    def test_compound_types_split_into_type_and_supertypes(self):
        assert catalog.type_facets('Champion Unit') == ('Unit', ['Champion'])
        assert catalog.type_facets('Signature Spell') == ('Spell', ['Signature'])
        assert catalog.type_facets('basic rune') == ('Rune', ['Basic'])
        assert catalog.type_facets('Token Battlefield') == ('Battlefield', ['Token'])
        assert catalog.type_facets('Unit') == ('Unit', [])

    def test_a_bare_supertype_has_no_type(self):
        assert catalog.type_facets('Token') == (None, ['Token'])
        assert catalog.type_facets('token') == (None, ['Token'])

    def test_unknown_values_stay_and_empty_is_nothing(self):
        assert catalog.type_facets('Creature') == ('Creature', [])
        assert catalog.type_facets('Weird Unit') == ('Unit', ['Weird'])
        assert catalog.type_facets('') == (None, [])
        assert catalog.type_facets(None) == (None, [])

    def test_card_summary_type_is_unchanged(self, app):
        """The contract keeps `type`/`supertype`/`type_raw` as before (additive only)."""
        assert catalog.parse_type('Token') == ('Token', None)
        assert catalog.parse_type('Champion Unit') == ('Unit', 'Champion')


class TestCardsFacets:
    def test_facets_hold_only_canonical_and_unknown_base_values(self, cards):
        facets = _list(cards)['meta']['facets']
        assert facets['type'] == {'Unit': 3, 'Spell': 1, 'Rune': 1, 'Battlefield': 1,
                                  'Creature': 1}
        assert list(facets['type']) == ['Unit', 'Spell', 'Rune', 'Battlefield', 'Creature']
        assert facets['supertype'] == {'Champion': 1, 'Signature': 1, 'Token': 3, 'Basic': 1}
        assert facets['domain'] == {'Fury': 2, 'Calm': 1, 'Mind': 1, 'Body': 2, 'Chaos': 1,
                                    'Order': 1, 'Colorless': 1, 'Weird': 1}

    def test_type_filter_includes_compound_types(self, cards):
        assert _keys(_list(cards, type='Unit')) == ['OGN-1', 'OGN-4', 'OGN-6']

    def test_supertype_filter_includes_a_bare_token(self, cards):
        assert _keys(_list(cards, supertype='Token')) == ['OGN-4', 'OGN-5', 'OGN-7']
        assert _keys(_list(cards, supertype='Champion')) == ['OGN-1']

    def test_exclude_supertype_drops_a_bare_token(self, cards):
        assert _keys(_list(cards, exclude_supertype='Token')) == [
            'OGN-1', 'OGN-2', 'OGN-3', 'OGN-6', 'SFD-1']

    def test_domain_filter_includes_domain_pairs(self, cards):
        assert _keys(_list(cards, domain='Body')) == ['OGN-1', 'OGN-3']

    def test_facets_stay_disjunctive(self, cards):
        facets = _list(cards, type='Unit')['meta']['facets']
        assert facets['type'] == {'Unit': 3, 'Spell': 1, 'Rune': 1, 'Battlefield': 1,
                                  'Creature': 1}
        assert facets['supertype'] == {'Champion': 1, 'Token': 1}
        facets = _list(cards, supertype='Token')['meta']['facets']
        assert facets['supertype'] == {'Champion': 1, 'Signature': 1, 'Token': 3, 'Basic': 1}
        assert facets['type'] == {'Unit': 1, 'Battlefield': 1}

    def test_card_summary_of_a_bare_token_is_unchanged(self, cards):
        item = _list(cards, q='OGN-5')['data']['items'][0]
        assert (item['type'], item['supertype'], item['type_raw']) == ('Token', None, 'Token')


class TestCollectionFilters:
    @pytest.fixture
    def owned(self, app, cards):
        with app.app_context():
            db.session.add_all([
                RbCollection(rbcol_rbset_id='OGN', rbcol_rbcar_id=card_id, rbcol_foil='N',
                             rbcol_user='testuser', rbcol_quantity=1, rbcol_condition='NM',
                             rbcol_language='English', rbcol_selling='N', rbcol_sell_qty=0)
                for card_id in ('1', '3', '5', '6')])
            db.session.commit()
        return cards

    def _get(self, client, **params):
        response = client.get(COLLECTION, query_string=params)
        assert response.status_code == 200, response.get_data(as_text=True)
        return [item['key'] for item in response.get_json()['data']['items']]

    def test_type_and_domain_filters_follow_the_base_values(self, owned):
        assert self._get(owned, type='Unit') == ['OGN-1:N', 'OGN-6:N']
        assert self._get(owned, type='Rune') == ['OGN-3:N']
        assert self._get(owned, domain='Body') == ['OGN-1:N', 'OGN-3:N']
        assert self._get(owned, domain='Chaos') == ['OGN-1:N']

    def test_export_filters_follow_the_base_values(self, owned):
        response = owned.get(f'{COLLECTION}/export', query_string={'type': 'Unit'})
        assert response.status_code == 200
        assert response.headers['X-Rows-Exported'] == '2'
        response = owned.get(f'{COLLECTION}/export', query_string={'domain': 'Body'})
        assert response.headers['X-Rows-Exported'] == '2'


class TestMetaGame:
    def test_lists_canonical_values_then_truly_unknown_ones(self, app, client):
        _seed(app)
        data = client.get(META).get_json()['data']
        assert data['types'] == [*CARD_TYPES, 'Creature']
        assert data['supertypes'] == list(SUPERTYPES)
        assert data['domains'] == [*DOMAINS, 'Weird']


@pytest.mark.parametrize('lang', ['es', 'en'])
def test_every_canonical_value_has_a_label(lang):
    """The facets translate every canonical value (`enums.json`, both languages)."""
    enums = json.loads((LOCALES / lang / 'enums.json').read_text(encoding='utf-8'))
    for kind, values in (('domain', DOMAINS), ('type', CARD_TYPES),
                         ('supertype', SUPERTYPES), ('rarity', RARITIES)):
        assert set(values) <= set(enums[kind]), (lang, kind)
