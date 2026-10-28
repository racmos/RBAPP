"""F3-b S1, S2, S5, S6, S9: GET /riftbound/api/v1/collection groups, filters, sorts, totals."""
import pytest
from sqlalchemy import event

from app import db
from tests.collection_read_helpers import URL, line, seed_all

ALL = ['OGN-1:N', 'OGN-1:S', 'OGN-2:N', 'OGN-79:N', 'SFD-10:N', 'SFD-257:N']


@pytest.fixture
def api(app, authenticated_client, make_user):
    make_user('otheruser')
    seed_all(app)
    return authenticated_client


def get(api, **params):
    response = api.get(URL, query_string=params)
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()


def keys(body):
    return [item['key'] for item in body['data']['items']]


class TestGroups:
    def test_one_group_per_printing_and_foil_in_catalog_order(self, api):
        assert keys(get(api)) == ALL

    def test_a_group_has_the_contract_keys(self, api):
        group = get(api)['data']['items'][0]
        assert list(group) == ['key', 'card', 'foil', 'qty', 'sell_qty', 'value', 'lines',
                               'keep_playset', 'playset_short', 'kept']
        assert group['card']['name'] == 'Alpha Fury'
        assert group['card']['key'] == 'OGN-1'
        assert (group['foil'], group['qty'], group['sell_qty']) == (False, 6, 1)

    def test_a_line_has_the_contract_keys_and_lines_follow_the_id(self, api):
        lines = get(api)['data']['items'][0]['lines']
        assert [l['qty'] for l in lines] == [4, 2]
        assert list(lines[0]) == ['id', 'foil', 'qty', 'condition', 'language', 'purchase_price',
                                  'selling', 'sell_qty', 'sell_price', 'updated_at', 'market',
                                  'value', 'pl_abs', 'pl_pct']
        assert lines[0]['id'] < lines[1]['id']
        assert lines[0]['selling'] is True and lines[1]['selling'] is False
        assert lines[0]['updated_at'] == '2026-10-03T09:00:00Z'

    def test_foil_is_a_boolean_and_has_its_own_group(self, api):
        groups = {g['key']: g for g in get(api)['data']['items']}
        assert groups['OGN-1:S']['foil'] is True
        assert groups['OGN-1:S']['lines'][0]['foil'] is True

    def test_only_my_lines(self, api):
        body = get(api)
        assert sum(g['qty'] for g in body['data']['items']) == 14   # not 14 + 9
        assert body['meta']['totals']['qty'] == 14

    def test_anonymous_is_refused(self, app):
        assert app.test_client().get(URL).status_code == 401

    def test_empty_collection(self, app, authenticated_client):
        body = get(authenticated_client)
        assert body['data']['items'] == []
        assert body['meta']['total_groups'] == 0 and body['meta']['pages'] == 0
        assert body['meta']['totals'] == {'lines': 0, 'qty': 0, 'unique': 0, 'value': 0.0,
                                          'cost': None, 'pl': None, 'selling_value': 0.0,
                                          'foil_pct': 0.0}


class TestFilters:
    @pytest.mark.parametrize('params, expected', [
        ({'q': 'alpha'}, ['OGN-1:N', 'OGN-1:S']),
        ({'q': 'JINX'}, ['OGN-79:N', 'SFD-257:N']),
        ({'q': 'ionia'}, ['OGN-2:N']),                       # tag
        ({'q': '79'}, ['OGN-79:N']),                         # card id
        ({'q': 'sfd-10'}, ['SFD-10:N']),                     # key
        ({'set': 'SFD'}, ['SFD-10:N', 'SFD-257:N']),
        ({'set': ['OGN', 'SFD'], 'rarity': 'Rare'}, ['OGN-79:N', 'SFD-257:N']),
        ({'domain': 'Chaos'}, ['OGN-79:N', 'SFD-257:N']),
        ({'type': 'Gear'}, ['SFD-10:N']),
        ({'foil': 'foil'}, ['OGN-1:S']),
        ({'foil': 'nonfoil'}, ['OGN-1:N', 'OGN-2:N', 'OGN-79:N', 'SFD-10:N', 'SFD-257:N']),
        ({'foil': 'any'}, ALL),
        ({'selling': 'yes'}, ['OGN-1:N', 'OGN-2:N']),
        ({'selling': 'no'}, ['OGN-1:N', 'OGN-1:S', 'OGN-79:N', 'SFD-10:N', 'SFD-257:N']),
        ({'condition': 'EX'}, ['OGN-2:N']),
        ({'condition': ['LP', 'MT']}, ['OGN-1:N', 'OGN-79:N']),
        ({'language': 'German'}, ['SFD-10:N']),
        ({'has_purchase': 'yes'}, ['OGN-1:N', 'OGN-1:S', 'OGN-2:N', 'OGN-79:N']),
        ({'has_purchase': 'no'}, ['OGN-1:N', 'SFD-10:N', 'SFD-257:N']),
    ])
    def test_filter(self, api, params, expected):
        assert keys(get(api, **params)) == expected

    def test_a_line_filter_keeps_only_the_matching_lines_of_a_group(self, api):
        group = get(api, condition='LP')['data']['items'][0]
        assert group['key'] == 'OGN-1:N'
        assert [l['condition'] for l in group['lines']] == ['LP']
        assert (group['qty'], group['sell_qty']) == (2, 0)

    def test_unknown_values_are_a_400(self, api):
        for params in ({'foil': 'maybe'}, {'selling': 'x'}, {'has_purchase': 'x'},
                       {'sort': 'popularity'}, {'per_page': 10}, {'per_page': 201},
                       {'dir': 'up'}):
            response = api.get(URL, query_string=params)
            assert response.status_code == 400, params
            assert response.get_json()['code'] == 'validation_error'


class TestSorts:
    @pytest.mark.parametrize('sort, direction, expected', [
        ('number', 'asc', ALL),
        ('number', 'desc', ['SFD-257:N', 'SFD-10:N', 'OGN-79:N', 'OGN-2:N', 'OGN-1:S', 'OGN-1:N']),
        ('name', 'asc', ['OGN-1:N', 'OGN-1:S', 'OGN-2:N', 'SFD-10:N', 'OGN-79:N', 'SFD-257:N']),
        ('qty', 'desc', ['OGN-1:N', 'OGN-2:N', 'SFD-10:N', 'OGN-1:S', 'OGN-79:N', 'SFD-257:N']),
        ('qty', 'asc', ['OGN-1:S', 'OGN-79:N', 'SFD-257:N', 'SFD-10:N', 'OGN-2:N', 'OGN-1:N']),
        # nulls (unpriced SFD groups) last in both directions
        ('price', 'asc', ['OGN-2:N', 'OGN-1:N', 'OGN-79:N', 'OGN-1:S', 'SFD-10:N', 'SFD-257:N']),
        ('price', 'desc', ['OGN-1:S', 'OGN-79:N', 'OGN-1:N', 'OGN-2:N', 'SFD-10:N', 'SFD-257:N']),
        ('value', 'desc', ['OGN-1:N', 'OGN-1:S', 'OGN-79:N', 'OGN-2:N', 'SFD-10:N', 'SFD-257:N']),
        ('value', 'asc', ['OGN-2:N', 'OGN-79:N', 'OGN-1:S', 'OGN-1:N', 'SFD-10:N', 'SFD-257:N']),
        # pl: OGN-1:N +8, OGN-1:S +10, OGN-79:N -5; the rest has none
        ('pl', 'desc', ['OGN-1:S', 'OGN-1:N', 'OGN-79:N', 'OGN-2:N', 'SFD-10:N', 'SFD-257:N']),
        ('pl', 'asc', ['OGN-79:N', 'OGN-1:N', 'OGN-1:S', 'OGN-2:N', 'SFD-10:N', 'SFD-257:N']),
        ('trend_7d', 'desc', ['OGN-1:N', 'OGN-1:S', 'OGN-2:N', 'OGN-79:N', 'SFD-10:N',
                              'SFD-257:N']),
        ('updated', 'desc', ['SFD-257:N', 'SFD-10:N', 'OGN-79:N', 'OGN-1:S', 'OGN-1:N',
                             'OGN-2:N']),
        ('updated', 'asc', ['OGN-2:N', 'OGN-1:N', 'OGN-1:S', 'OGN-79:N', 'SFD-10:N',
                            'SFD-257:N']),
        ('rarity', 'desc', ['SFD-10:N', 'OGN-79:N', 'SFD-257:N', 'OGN-2:N', 'OGN-1:N',
                            'OGN-1:S']),
    ])
    def test_sort(self, api, sort, direction, expected):
        assert keys(get(api, sort=sort, dir=direction)) == expected


class TestPagination:
    def test_pages_of_25_at_least_and_total_groups(self, api, app):
        with app.app_context():
            for number in range(100, 130):
                from app.models import RbCard
                db.session.add(RbCard(rbcar_rbset_id='OGN', rbcar_id=str(number),
                                      rbcar_name=f'Filler {number}', rbcar_type='Unit',
                                      rbcar_rarity='Common'))
                db.session.add(line(str(number), 1))
            db.session.commit()
        first = get(api, per_page=25)
        assert len(first['data']['items']) == 25
        assert first['meta']['total_groups'] == 36
        assert (first['meta']['page'], first['meta']['per_page'], first['meta']['pages']) == (1, 25, 2)
        second = get(api, per_page=25, page=2)
        assert len(second['data']['items']) == 11
        assert set(keys(first)).isdisjoint(keys(second))
        assert get(api)['meta']['per_page'] == 50
        assert get(api, per_page=200)['meta']['per_page'] == 200
        assert get(api, page=9)['data']['items'] == []

    def test_totals_cover_every_matching_line_not_just_the_page(self, api):
        meta = get(api, per_page=25, set='SFD', sort='qty', dir='desc')['meta']
        assert meta['totals']['lines'] == 2 and meta['totals']['qty'] == 3


class TestTotals:
    def test_totals_of_the_whole_collection(self, api):
        meta = get(api)['meta']
        assert meta['totals'] == {'lines': 7, 'qty': 14, 'unique': 5, 'value': 125.0,
                                  'cost': 77.0, 'pl': 13.0, 'selling_value': 27.5,
                                  'foil_pct': 7.1}
        assert (meta['total_groups'], meta['playset_size']) == (6, 3)
        assert meta['price_as_of'] == '2026-10-20'

    def test_totals_follow_the_filters(self, api):
        meta = get(api, set='OGN', rarity='Common', foil='nonfoil')['meta']
        assert meta['totals'] == {'lines': 2, 'qty': 6, 'unique': 1, 'value': 60.0,
                                  'cost': 32.0, 'pl': 8.0, 'selling_value': 12.5,
                                  'foil_pct': 0.0}

    def test_cost_and_pl_are_null_without_purchase_prices(self, api):
        totals = get(api, set='SFD')['meta']['totals']
        assert totals['cost'] is None and totals['pl'] is None and totals['value'] == 0.0


class TestFacets:
    def test_facets_count_groups_in_a_stable_order(self, api):
        facets = get(api)['meta']['facets']
        assert list(facets) == ['set', 'rarity', 'condition', 'language', 'foil']
        assert facets['set'] == {'OGN': 4, 'SFD': 2}
        assert facets['rarity'] == {'Common': 2, 'Uncommon': 1, 'Rare': 2, 'Epic': 1}
        assert list(facets['condition'].items()) == [('MT', 1), ('NM', 4), ('EX', 1), ('LP', 1)]
        assert list(facets['language'].items()) == [
            ('English', 4), ('French', 1), ('German', 1), ('Spanish', 1)]
        assert facets['foil'] == {'foil': 1, 'nonfoil': 5}

    def test_a_facet_ignores_its_own_filter_only(self, api):
        facets = get(api, set='SFD', rarity='Rare')['meta']['facets']
        assert facets['set'] == {'OGN': 1, 'SFD': 1}         # set filter lifted
        assert facets['rarity'] == {'Epic': 1, 'Rare': 1}    # rarity filter lifted, set kept
        assert facets['foil'] == {'foil': 0, 'nonfoil': 1}   # both filters applied


class TestStatementBound:
    def count(self, app, api):
        statements = []

        def listener(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        event.listen(db.engine, 'before_cursor_execute', listener)
        try:
            assert api.get(URL, query_string={'sort': 'value', 'dir': 'desc'}).status_code == 200
        finally:
            event.remove(db.engine, 'before_cursor_execute', listener)
        return len(statements)

    def test_at_most_ten_statements_whatever_the_size(self, app, api):
        self.count(app, api)   # warm-up: the first request also loads per-process state
        small = self.count(app, api)
        with app.app_context():
            from app.models import RbCard
            for number in range(100, 160):
                db.session.add(RbCard(rbcar_rbset_id='OGN', rbcar_id=str(number),
                                      rbcar_name=f'Filler {number}', rbcar_type='Unit',
                                      rbcar_rarity='Common'))
                db.session.add(line(str(number), 2))
            db.session.commit()
        large = self.count(app, api)
        assert small <= 10 and large <= 10
        assert small == large
