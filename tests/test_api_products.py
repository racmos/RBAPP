"""F14-b S2, S3 (AC2) and F14-c S5 (AC3): GET /riftbound/api/v1/products."""
from app import db
from app.models import RbProducts, RbSet, RbcmPrice
from tests.product_helpers import (add_owned, add_price, add_product, add_sets,
                                   count_statements)

URL = '/riftbound/api/v1/products'

VISIBLE = ['Arcane Starter', 'Origins Booster', 'Origins Booster Box', 'Origins Sleeves',
           'Spiritforged Booster']


def _seed(app):
    """Five visible products plus one unlisted, one hidden and one single."""
    add_sets()
    add_product(1, 'Origins Booster', kind='booster', set_id='OGN',
                category='Riftbound Boosters')
    add_product(2, 'Origins Booster Box', kind='box', set_id='OGN',
                category='Riftbound Booster Boxes')
    add_product(3, 'Spiritforged Booster', kind='booster', set_id='SFD')
    add_product(4, 'Origins Sleeves', kind='sleeves', set_id=None, category='Sleeves')
    add_product(5, 'Old Bundle', kind='bundle', set_id='OGN', listed=False)
    add_product(6, 'Secret Case', kind='case', set_id='OGN', hidden=True)
    add_product(7, 'A single card', kind='other', set_id='OGN', type_='single')
    add_product(8, 'Arcane Starter', kind='starter', set_id='ARC')
    # 1: +25 % in 7 days (trend); 2: -20 % (avg7); 3: +100 % in 30 days (low); 4, 8: no price.
    add_price(1, '20261014', trend=4)
    add_price(1, '20261021', avg7=0, trend=5, low=4.5)
    add_price(2, '20261014', avg7=125)
    add_price(2, '20261021', avg7=100, trend=98, low=90)
    add_price(3, '20260921', low=2)
    add_price(3, '20261021', low=4)
    add_price(5, '20261021', trend=30)
    add_price(6, '20261021', trend=300)
    db.session.commit()


def _names(resp):
    assert resp.status_code == 200, resp.get_json()
    return [item['name'] for item in resp.get_json()['data']['items']]


class TestShape:
    def test_defaults(self, authenticated_client, app):
        _seed(app)
        body = authenticated_client.get(URL).get_json()
        assert body['success'] is True
        assert [item['name'] for item in body['data']['items']] == VISIBLE
        assert list(body['meta']) == ['page', 'per_page', 'total', 'pages', 'facets',
                                      'price_as_of']
        assert body['meta']['page'] == 1
        assert body['meta']['per_page'] == 48
        assert body['meta']['total'] == 5
        assert body['meta']['pages'] == 1
        assert body['meta']['price_as_of'] == '2026-10-21'

    def test_product_summary(self, authenticated_client, app):
        _seed(app)
        items = authenticated_client.get(URL).get_json()['data']['items']
        booster = next(item for item in items if item['id'] == 1)
        assert list(booster) == ['id', 'name', 'kind', 'category', 'set_id', 'image_src',
                                 'listed', 'price', 'owned_qty']
        assert booster == {
            'id': 1, 'name': 'Origins Booster', 'kind': 'booster',
            'category': 'Riftbound Boosters', 'set_id': 'OGN', 'image_src': None,
            'listed': True,
            'price': {'value': 5.0, 'source': 'trend', 'change_7d_pct': 25.0,
                      'change_30d_pct': None, 'as_of': '2026-10-21'},
            'owned_qty': 0,
        }
        assert list(booster['price']) == ['value', 'source', 'change_7d_pct',
                                          'change_30d_pct', 'as_of']

    def test_each_price_source(self, authenticated_client, app):
        _seed(app)
        items = authenticated_client.get(URL).get_json()['data']['items']
        by_id = {item['id']: item for item in items}
        assert (by_id[2]['price']['value'], by_id[2]['price']['source']) == (100.0, 'avg7')
        assert (by_id[3]['price']['value'], by_id[3]['price']['source']) == (4.0, 'low')
        assert by_id[3]['price']['change_30d_pct'] == 100.0
        assert by_id[4]['price'] is None
        assert by_id[4]['set_id'] is None

    def test_no_prices_at_all(self, authenticated_client, app):
        add_product(1, 'Origins Booster')
        db.session.commit()
        body = authenticated_client.get(URL).get_json()
        assert body['meta']['price_as_of'] is None
        assert body['data']['items'][0]['price'] is None

    def test_empty_catalog(self, authenticated_client):
        body = authenticated_client.get(URL).get_json()
        assert body['data']['items'] == []
        assert body['meta']['total'] == 0
        assert body['meta']['pages'] == 0
        assert body['meta']['facets'] == {'kind': {}, 'set': {}}


class TestFilters:
    def test_singles_hidden_and_unlisted_are_excluded_by_default(self, authenticated_client,
                                                                 app):
        _seed(app)
        names = _names(authenticated_client.get(URL))
        assert 'A single card' not in names
        assert 'Secret Case' not in names
        assert 'Old Bundle' not in names

    def test_listed_any_adds_unlisted_but_never_hidden_or_singles(self, authenticated_client,
                                                                  app):
        _seed(app)
        resp = authenticated_client.get(URL, query_string={'listed': 'any'})
        assert _names(resp) == ['Arcane Starter', 'Old Bundle'] + VISIBLE[1:]
        old = next(i for i in resp.get_json()['data']['items'] if i['name'] == 'Old Bundle')
        assert old['listed'] is False

    def test_listed_true_is_the_default(self, authenticated_client, app):
        _seed(app)
        assert _names(authenticated_client.get(URL, query_string={'listed': 'true'})) == VISIBLE

    def test_q_is_a_case_insensitive_name_substring(self, authenticated_client, app):
        _seed(app)
        assert _names(authenticated_client.get(URL, query_string={'q': 'BOOSTER b'})) == [
            'Origins Booster Box']
        assert _names(authenticated_client.get(URL, query_string={'q': 'booster'})) == [
            'Origins Booster', 'Origins Booster Box', 'Spiritforged Booster']

    def test_kind_repeated(self, authenticated_client, app):
        _seed(app)
        assert _names(authenticated_client.get(URL, query_string={'kind': 'booster'})) == [
            'Origins Booster', 'Spiritforged Booster']
        assert _names(authenticated_client.get(
            URL, query_string=[('kind', 'booster'), ('kind', 'box')])) == [
            'Origins Booster', 'Origins Booster Box', 'Spiritforged Booster']

    def test_set_repeated_and_case_insensitive(self, authenticated_client, app):
        _seed(app)
        assert _names(authenticated_client.get(URL, query_string={'set': 'sfd'})) == [
            'Spiritforged Booster']
        assert _names(authenticated_client.get(
            URL, query_string=[('set', 'SFD'), ('set', 'ARC')])) == [
            'Arcane Starter', 'Spiritforged Booster']

    def test_owned_values_without_owned_products(self, authenticated_client, app):
        _seed(app)
        assert _names(authenticated_client.get(URL, query_string={'owned': 'any'})) == VISIBLE
        assert _names(authenticated_client.get(URL, query_string={'owned': 'owned'})) == []
        assert _names(authenticated_client.get(URL, query_string={'owned': 'missing'})) == \
            VISIBLE

    def test_filters_combine(self, authenticated_client, app):
        _seed(app)
        resp = authenticated_client.get(URL, query_string={'kind': 'booster', 'set': 'OGN',
                                                           'q': 'origins'})
        assert _names(resp) == ['Origins Booster']


class TestFacets:
    def test_default_facets_in_stable_order(self, authenticated_client, app):
        _seed(app)
        facets = authenticated_client.get(URL).get_json()['meta']['facets']
        assert list(facets) == ['kind', 'set']
        # Kinds in PRODUCT_KINDS order; sets by release date; products without a set are
        # not counted in the set facet.
        assert list(facets['kind'].items()) == [('booster', 2), ('box', 1), ('starter', 1),
                                                ('sleeves', 1)]
        assert list(facets['set'].items()) == [('OGN', 2), ('SFD', 1), ('ARC', 1)]

    def test_kind_facet_ignores_its_own_filter(self, authenticated_client, app):
        _seed(app)
        facets = authenticated_client.get(URL, query_string={'kind': 'booster'}).get_json()[
            'meta']['facets']
        assert facets['kind'] == {'booster': 2, 'box': 1, 'starter': 1, 'sleeves': 1}
        assert list(facets['set'].items()) == [('OGN', 1), ('SFD', 1)]

    def test_set_facet_ignores_its_own_filter(self, authenticated_client, app):
        _seed(app)
        facets = authenticated_client.get(URL, query_string={'set': 'SFD'}).get_json()[
            'meta']['facets']
        assert list(facets['set'].items()) == [('OGN', 2), ('SFD', 1), ('ARC', 1)]
        assert facets['kind'] == {'booster': 1}

    def test_facets_follow_listed_and_q(self, authenticated_client, app):
        _seed(app)
        facets = authenticated_client.get(URL, query_string={'listed': 'any',
                                                             'q': 'o'}).get_json()[
            'meta']['facets']
        assert facets['kind'] == {'booster': 2, 'box': 1, 'bundle': 1, 'sleeves': 1}

    def test_unknown_set_sorts_after_known_ones(self, authenticated_client, app):
        _seed(app)
        add_product(9, 'Promo Pack', kind='booster', set_id='ZZZ')
        add_product(10, 'Other Promo', kind='booster', set_id='PRM')
        db.session.commit()
        facets = authenticated_client.get(URL).get_json()['meta']['facets']
        assert list(facets['set']) == ['OGN', 'SFD', 'ARC', 'PRM', 'ZZZ']


class TestSorts:
    def test_name_desc(self, authenticated_client, app):
        _seed(app)
        assert _names(authenticated_client.get(URL, query_string={'dir': 'desc'})) == \
            list(reversed(VISIBLE))

    def test_price_asc_nulls_last(self, authenticated_client, app):
        _seed(app)
        assert _names(authenticated_client.get(URL, query_string={'sort': 'price'})) == [
            'Spiritforged Booster', 'Origins Booster', 'Origins Booster Box',
            'Arcane Starter', 'Origins Sleeves']

    def test_price_desc_nulls_still_last(self, authenticated_client, app):
        _seed(app)
        assert _names(authenticated_client.get(
            URL, query_string={'sort': 'price', 'dir': 'desc'})) == [
            'Origins Booster Box', 'Origins Booster', 'Spiritforged Booster',
            'Arcane Starter', 'Origins Sleeves']

    def test_change_7d_both_directions(self, authenticated_client, app):
        _seed(app)
        # Spiritforged's 7-day reference is its 09-21 row (newest on or before 10-14).
        nulls = ['Arcane Starter', 'Origins Sleeves']
        assert _names(authenticated_client.get(URL, query_string={'sort': 'change_7d'})) == [
            'Origins Booster Box', 'Origins Booster', 'Spiritforged Booster'] + nulls
        assert _names(authenticated_client.get(
            URL, query_string={'sort': 'change_7d', 'dir': 'desc'})) == [
            'Spiritforged Booster', 'Origins Booster', 'Origins Booster Box'] + nulls

    def test_change_30d(self, authenticated_client, app):
        _seed(app)
        assert _names(authenticated_client.get(
            URL, query_string={'sort': 'change_30d', 'dir': 'desc'})) == [
            'Spiritforged Booster', 'Arcane Starter', 'Origins Booster',
            'Origins Booster Box', 'Origins Sleeves']

    def test_equal_values_tiebreak_by_name(self, authenticated_client, app):
        add_product(1, 'Zeta Pack')
        add_product(2, 'Alpha Pack')
        add_price(1, '20261021', trend=5)
        add_price(2, '20261021', trend=5)
        db.session.commit()
        for direction in ('asc', 'desc'):
            assert _names(authenticated_client.get(
                URL, query_string={'sort': 'price', 'dir': direction})) == [
                'Alpha Pack', 'Zeta Pack'], direction


class TestPagination:
    def _many(self, n):
        for product_id in range(1, n + 1):
            add_product(product_id, f'Pack {product_id:03d}')
        db.session.commit()

    def test_pages(self, authenticated_client, app):
        self._many(30)
        body = authenticated_client.get(URL, query_string={'per_page': 24,
                                                           'page': 2}).get_json()
        assert [item['name'] for item in body['data']['items']] == [
            f'Pack {i:03d}' for i in range(25, 31)]
        assert (body['meta']['total'], body['meta']['pages'], body['meta']['page'],
                body['meta']['per_page']) == (30, 2, 2, 24)

    def test_page_past_the_end_is_empty(self, authenticated_client, app):
        self._many(3)
        body = authenticated_client.get(URL, query_string={'page': 5}).get_json()
        assert body['data']['items'] == []
        assert (body['meta']['total'], body['meta']['pages']) == (3, 1)

    def test_per_page_bounds(self, authenticated_client):
        low = authenticated_client.get(URL, query_string={'per_page': 23})
        assert low.status_code == 400
        assert low.get_json()['details'] == [{
            'field': 'per_page', 'message': 'Input should be greater than or equal to 24',
            'type': 'greater_than_equal', 'code': 'out_of_range', 'params': {'min': 24}}]
        high = authenticated_client.get(URL, query_string={'per_page': 97})
        assert high.status_code == 400
        assert high.get_json()['details'][0]['params'] == {'max': 96}
        assert authenticated_client.get(URL, query_string={'per_page': 96}).status_code == 200


class TestValidation:
    def test_invalid_values_are_validation_errors(self, authenticated_client):
        for name, value in (('sort', 'value'), ('dir', 'up'), ('listed', 'false'),
                            ('owned', 'all'), ('page', 0)):
            resp = authenticated_client.get(URL, query_string={name: value})
            body = resp.get_json()
            assert resp.status_code == 400, name
            assert body['code'] == 'validation_error'
            assert body['message'] == 'Invalid query parameters'
            assert body['details'][0]['field'] == name


class TestOwned:
    """F14-c S5: `owned_qty`, the `owned` filter and hidden products for their owners."""

    def _owned(self, app, other_user=False):
        _seed(app)
        add_owned(1, 2)
        add_owned(1, 3, purchase=4)
        add_owned(3, 1)
        if other_user:
            add_owned(2, 7, user='otheruser')

    def test_owned_qty_adds_up_the_callers_lines(self, authenticated_client,
                                                 other_user_client, app):
        self._owned(app, other_user=True)
        items = authenticated_client.get(URL).get_json()['data']['items']
        assert {i['id']: i['owned_qty'] for i in items} == {8: 0, 1: 5, 2: 0, 4: 0, 3: 1}
        theirs = other_user_client.get(URL).get_json()['data']['items']
        assert {i['id']: i['owned_qty'] for i in theirs} == {8: 0, 1: 0, 2: 7, 4: 0, 3: 0}

    def test_owned_filter(self, authenticated_client, other_user_client, app):
        self._owned(app, other_user=True)
        assert _names(authenticated_client.get(URL, query_string={'owned': 'owned'})) == [
            'Origins Booster', 'Spiritforged Booster']
        assert _names(authenticated_client.get(URL, query_string={'owned': 'missing'})) == [
            'Arcane Starter', 'Origins Booster Box', 'Origins Sleeves']
        assert _names(authenticated_client.get(URL, query_string={'owned': 'any'})) == VISIBLE

    def test_owned_filter_counts_in_the_facets_and_the_total(self, authenticated_client, app):
        self._owned(app)
        body = authenticated_client.get(URL, query_string={'owned': 'owned'}).get_json()
        assert body['meta']['total'] == 2
        assert body['meta']['facets'] == {'kind': {'booster': 2},
                                          'set': {'OGN': 1, 'SFD': 1}}

    def test_hidden_products_are_listed_for_their_owners_only(self, authenticated_client,
                                                              other_user_client, app):
        self._owned(app)
        add_owned(6, 1)
        mine = authenticated_client.get(URL).get_json()
        assert _names(authenticated_client.get(URL)) == VISIBLE[:4] + ['Secret Case',
                                                                       VISIBLE[4]]
        secret = next(i for i in mine['data']['items'] if i['id'] == 6)
        assert (secret['owned_qty'], secret['price']['value']) == (1, 300.0)
        assert mine['meta']['facets']['kind']['case'] == 1
        assert _names(authenticated_client.get(URL, query_string={'owned': 'owned'})) == [
            'Origins Booster', 'Secret Case', 'Spiritforged Booster']
        assert 'Secret Case' not in _names(other_user_client.get(URL))

    def test_owned_singles_stay_out(self, authenticated_client, app):
        _seed(app)
        add_owned(7, 1)            # not possible through the API; the list still drops it
        assert 'A single card' not in _names(authenticated_client.get(
            URL, query_string={'listed': 'any'}))

    def test_statement_count_with_owned_products(self, authenticated_client, app):
        self._owned(app)
        for owned in ('any', 'owned'):
            resp, statements = count_statements(
                app, lambda: authenticated_client.get(URL, query_string={'owned': owned}))
            assert resp.status_code == 200
            assert statements <= 10, (owned, statements)


class TestUsersAndStatements:
    def test_anonymous_gets_a_json_401(self, client, app):
        _seed(app)
        resp = client.get(URL)
        assert resp.status_code == 401
        body = resp.get_json()
        assert (body['success'], body['error'], body['code']) == (False, 'Unauthorized',
                                                                   'unauthenticated')

    def test_every_user_sees_the_same_catalog(self, authenticated_client, other_user_client,
                                              app):
        _seed(app)
        mine = authenticated_client.get(URL).get_json()
        theirs = other_user_client.get(URL).get_json()
        assert mine == theirs
        assert {item['owned_qty'] for item in mine['data']['items']} == {0}

    def test_statement_count_does_not_grow(self, authenticated_client, app):
        def seed(count):
            for product_id in range(1, count + 1):
                add_product(product_id, f'Pack {product_id:03d}', kind='booster')
                add_price(product_id, '20261014', trend=1)
                add_price(product_id, '20261021', trend=2)
            db.session.commit()

        def statements(sort):
            def run():
                resp = authenticated_client.get(URL, query_string={'sort': sort})
                assert resp.status_code == 200
                return resp.get_json()['meta']['total']
            return count_statements(app, run)

        db.session.add(RbSet(rbset_id='OGN', rbset_name='Origins'))
        seed(3)
        few = {sort: statements(sort) for sort in ('name', 'price')}
        db.session.query(RbProducts).delete()
        db.session.query(RbcmPrice).delete()
        db.session.commit()
        seed(60)
        many = {sort: statements(sort) for sort in ('name', 'price')}
        for sort in ('name', 'price'):
            assert few[sort][0] == 3 and many[sort][0] == 60
            assert few[sort][1] <= 10 and many[sort][1] <= 10, (sort, few, many)
            assert few[sort][1] == many[sort][1], (sort, few, many)

    def test_endpoint_name(self, app):
        rules = [r for r in app.url_map.iter_rules() if r.rule == URL]
        assert [(r.endpoint, sorted(r.methods - {'HEAD', 'OPTIONS'})) for r in rules] == [
            ('api_v1.list_products', ['GET'])]
