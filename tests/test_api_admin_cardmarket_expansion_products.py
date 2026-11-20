"""CM-f: the products of one Cardmarket expansion on the latest load (A, read-only).

`GET /riftbound/api/v1/admin/cardmarket/expansions/<id>/products` lists every product of the
expansion on the latest load with everything we hold about it (type, category, first seen,
that day's prices, its card link and its catalog product), so an expansion Cardmarket gives
no name can be told apart before it is mapped or a set is created for it.

Data from `tests/cardmarket_matching_data.py`: expansion 10 (Origins -> OGN) has 7 singles and
1 sealed product on the latest load D2; 12 (Accessories, unmapped) one sealed product.

Specs (S) and their tests:
  S1  admin only (401 / 403), classified A ............... TestAuthorization
  S2  unknown expansion 404, same envelope ................ TestNotFound
  S3  every product of the latest load, all the fields .... TestItems
  S4  prices of the latest load only, price chain ......... TestPrices
  S5  card link and catalog product ....................... TestItems, TestLinks
  S6  q: name, case-insensitive ........................... TestFilters
  S7  type all | single | sealed .......................... TestFilters
  S8  sort price (default) | name | added ................. TestSort
  S9  page / per_page 50, 100, 200; meta total, pages ..... TestPaging
  S10 meta: whole-expansion counts, price range, first seen TestMeta
  S11 a bad query is a 400 validation_error ............... TestValidation
  S12 bounded statements .................................. TestStatements
  S13 nothing written ..................................... every request via `get`

CM-g (2026-11-20), the products by kind (expansion 30, `kinds_data`):
  S14 every item has `kind`: `card` for a single, else the catalog kind (admin locks win),
      else the kind of its category ...................... TestKind
  S15 meta.kinds: counts of the whole expansion, card first then the PRODUCT_KINDS
      order, zero kinds left out, whatever the filters .. TestKindCounts
  S16 `kind` all | card | a product kind filters the list, total and pages; it combines
      with `type` and `q` (AND) ......................... TestKindFilter
  S17 a bad kind is a 400 validation_error ............... TestValidation
  S18 statements stay 5 with the kind filter ............. TestStatements
"""
import pytest
import sqlalchemy as sa
from sqlalchemy import event

from app import db
from app.models.audit import RbAdminAudit
from app.models.cardmarket import (RbcmExpansion, RbcmProduct, RbcmProductCardMap,
                                   RbProducts)
from tests import cardmarket_matching_data as cm
from tests.test_authz_matrix import classify

BASE = '/riftbound/api/v1/admin/cardmarket/expansions'


def url(expansion_id, query=''):
    return f'{BASE}/{expansion_id}/products' + (f'?{query}' if query else '')


@pytest.fixture
def data(app):
    cm.build()
    # 13: unmapped, nothing on the latest load
    db.session.add(RbcmExpansion(rbexp_id=13, rbexp_name=None))
    db.session.commit()
    return app


def state():
    """What a read must never change: the expansions, links, catalog and audit rows."""
    db.session.expire_all()
    return (
        sorted((e.rbexp_id, e.rbexp_name, e.rbexp_rbset_id)
               for e in db.session.execute(sa.select(RbcmExpansion)).scalars()),
        db.session.execute(sa.select(sa.func.count()).select_from(RbcmProductCardMap)).scalar(),
        db.session.execute(sa.select(sa.func.count()).select_from(RbProducts)).scalar(),
        db.session.execute(sa.select(sa.func.count()).select_from(RbAdminAudit)).scalar(),
    )


def get(client, target):
    """GET `target`; the read must leave every table as it was (S13)."""
    before = state()
    resp = client.get(target)
    assert state() == before
    return resp


def ok(resp):
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert body['success'] is True
    return body['data']


def err(resp, status, code=None):
    assert resp.status_code == status, resp.get_json()
    body = resp.get_json()
    assert body['success'] is False
    if code:
        assert body.get('code') == code, body
    return body


def ids(got):
    return [item['id_product'] for item in got['items']]


NO_PRICES = None


def prices(low=None, trend=None, avg7=None, avg30=None, avg=None, low_foil=None,
           trend_foil=None):
    return {'low': low, 'trend': trend, 'avg7': avg7, 'avg30': avg30, 'avg': avg,
            'low_foil': low_foil, 'trend_foil': trend_foil}


ITEM_KEYS = {'id_product', 'name', 'type', 'kind', 'category', 'category_id', 'date_added',
             'price', 'price_source', 'prices', 'linked', 'catalog'}


# ---------------------------------------------------------------------------
# S1, S2
# ---------------------------------------------------------------------------

class TestAuthorization:
    def test_anonymous_401_user_403(self, app, authenticated_client, data):
        assert get(app.test_client(), url(10)).status_code == 401
        assert get(authenticated_client, url(10)).status_code == 403

    def test_the_rule_is_admin_and_get_only(self, app):
        rules = [rule for rule in app.url_map.iter_rules()
                 if rule.rule == f'{BASE}/<int:expansion_id>/products']
        assert len(rules) == 1
        assert classify(rules[0]) == 'A'
        assert rules[0].methods - {'HEAD', 'OPTIONS'} == {'GET'}


class TestNotFound:
    def test_unknown_expansion_is_404_like_the_other_expansion_routes(
            self, admin_client, data):
        body = err(get(admin_client, url(999)), 404)
        assert body == {'success': False, 'error': 'Not Found',
                        'message': 'Cardmarket expansion 999 not found.'}
        assert err(admin_client.put(f'{BASE}/999', json={'set_id': 'OGN'}), 404)['message'] \
            == body['message']

    def test_an_expansion_without_products_on_the_latest_load(self, admin_client, data):
        got = ok(get(admin_client, url(13)))
        assert got['expansion'] == {'id': 13, 'name': None, 'mapped_set_id': None,
                                    'mapped_set_name': None}
        assert got['items'] == []
        assert got['meta'] == {'page': 1, 'per_page': 50, 'total': 0, 'pages': 1,
                               'singles': 0, 'sealed': 0, 'kinds': [], 'price_range': None,
                               'first_seen': None, 'date': '2030-10-02'}


# ---------------------------------------------------------------------------
# S3, S5: the items
# ---------------------------------------------------------------------------

class TestItems:
    def test_every_product_of_the_latest_load_dearest_first(self, admin_client, data):
        got = ok(get(admin_client, url(10)))
        assert got['expansion'] == {'id': 10, 'name': 'Origins', 'mapped_set_id': 'OGN',
                                    'mapped_set_name': 'Origins'}
        # product 900 is only on the older snapshot D1, 201 belongs to expansion 11
        assert ids(got) == [300, 250, 200, 101, 400, 100, 500, 501]
        assert {key for item in got['items'] for key in item} == ITEM_KEYS

    def test_all_the_fields_of_a_product(self, admin_client, data):
        cm.product(600, 'Teemo, Scout', expansion=12, date_added='2025-07-14 16:11:32')
        db.session.execute(sa.update(RbcmProduct)
                           .where(RbcmProduct.rbprd_id_product == 600)
                           .values(rbprd_id_category=1))
        cm.price(600, 0.2, rbprc_trend=0.3, rbprc_avg7=0.25, rbprc_avg30=0.28, rbprc_avg=0.27,
                 rbprc_low_foil=1.5, rbprc_trend_foil=2.0, rbprc_avg1=9.0)
        cm.link(600, 'OGN', '001', foil='N')
        db.session.commit()
        items = {item['id_product']: item for item in ok(get(admin_client, url(12)))['items']}
        assert items[600] == {
            'id_product': 600, 'name': 'Teemo, Scout', 'type': 'single', 'kind': 'card',
            'category': 'Riftbound Single', 'category_id': 1, 'date_added': '2025-07-14',
            'price': 0.2, 'price_source': 'low',
            'prices': prices(low=0.2, trend=0.3, avg7=0.25, avg30=0.28, avg=0.27,
                             low_foil=1.5, trend_foil=2.0),
            'linked': {'set_id': 'OGN', 'card_id': '001', 'foil': 'N'},
            'catalog': None}
        # a sealed product without a price, a link or a catalog row
        assert items[301] == {
            'id_product': 301, 'name': 'Origins Playmat', 'type': 'sealed',
            'kind': 'accessory', 'category': 'Riftbound Playmats', 'category_id': None, 'date_added': None,
            'price': None, 'price_source': None, 'prices': NO_PRICES, 'linked': None,
            'catalog': None}

    def test_a_catalog_product(self, admin_client, data):
        box = next(item for item in ok(get(admin_client, url(10)))['items']
                   if item['id_product'] == 300)
        assert box['type'] == 'sealed'
        assert box['catalog'] == {'kind': 'box', 'set_id': 'OGN'}
        assert box['linked'] is None


class TestLinks:
    def test_linked_cards_after_a_reset_none(self, admin_client, data):
        assert all(item['linked'] is None for item in ok(get(admin_client, url(10)))['items'])

    def test_a_link_without_a_foil_slot(self, admin_client, data):
        cm.link(250, 'OGN', '003')
        db.session.commit()
        items = {item['id_product']: item for item in ok(get(admin_client, url(10)))['items']}
        assert items[250]['linked'] == {'set_id': 'OGN', 'card_id': '003', 'foil': None}
        assert items[200]['linked'] is None


# ---------------------------------------------------------------------------
# S4: prices
# ---------------------------------------------------------------------------

class TestPrices:
    def test_only_the_prices_of_the_latest_load(self, admin_client, data):
        # 500 has a price on D1 only (product 500 is not on D1, but its price row is)
        cm.price(500, 77.0, date=cm.D1)
        db.session.commit()
        items = {item['id_product']: item for item in ok(get(admin_client, url(10)))['items']}
        assert items[500]['prices'] is None and items[500]['price'] is None
        # 100 had 0.01 on D1 and 0.10 on D2
        assert items[100]['prices'] == prices(low=0.1)
        assert (items[100]['price'], items[100]['price_source']) == (0.1, 'low')

    def test_a_single_is_worth_its_low_a_sealed_product_avg7_then_trend_then_low(
            self, admin_client, data):
        db.session.add(RbcmExpansion(rbexp_id=20, rbexp_name=None))
        cm.product(2000, 'Single', expansion=20)
        cm.price(2000, 1.0, rbprc_avg7=50.0, rbprc_trend=40.0)
        cm.product(2001, 'Box avg7', expansion=20, type_='nonsingle')
        cm.price(2001, 3.0, rbprc_avg7=5.0, rbprc_trend=4.0)
        cm.product(2002, 'Box trend', expansion=20, type_='nonsingle')
        cm.price(2002, 3.0, rbprc_avg7=0, rbprc_trend=4.0)
        cm.product(2003, 'Box low', expansion=20, type_='nonsingle')
        cm.price(2003, 2.0)
        cm.product(2004, 'Box zero', expansion=20, type_='nonsingle')
        cm.price(2004, 0)
        cm.product(2005, 'Single zero', expansion=20)
        cm.price(2005, 0)
        db.session.commit()
        items = {item['id_product']: (item['price'], item['price_source'])
                 for item in ok(get(admin_client, url(20)))['items']}
        assert items == {2000: (1.0, 'low'), 2001: (5.0, 'avg7'), 2002: (4.0, 'trend'),
                         2003: (2.0, 'low'), 2004: (None, None), 2005: (0.0, 'low')}


# ---------------------------------------------------------------------------
# S6, S7: filters
# ---------------------------------------------------------------------------

class TestFilters:
    def test_q_matches_the_name_ignoring_case(self, admin_client, data):
        got = ok(get(admin_client, url(10, 'q=JINX')))
        assert ids(got) == [101, 100]
        assert got['meta']['total'] == 2
        assert ids(ok(get(admin_client, url(10, 'q=%20booster%20')))) == [300]
        assert ids(ok(get(admin_client, url(10, 'q=nothing')))) == []

    @pytest.mark.parametrize('kind,expected', [
        ('single', [250, 200, 101, 400, 100, 500, 501]),
        ('sealed', [300]),
        ('all', [300, 250, 200, 101, 400, 100, 500, 501]),
    ])
    def test_type(self, admin_client, data, kind, expected):
        got = ok(get(admin_client, url(10, f'type={kind}')))
        assert ids(got) == expected
        assert {item['type'] for item in got['items']} <= {'single', 'sealed'}
        assert got['meta']['total'] == len(expected)

    def test_q_and_type_together(self, admin_client, data):
        assert ids(ok(get(admin_client, url(10, 'q=i&type=sealed')))) == [300]


# ---------------------------------------------------------------------------
# S8: sort
# ---------------------------------------------------------------------------

class TestSort:
    def test_price_is_dearest_first_unpriced_last_then_by_name(self, admin_client, data):
        assert ids(ok(get(admin_client, url(10, 'sort=price')))) == \
            ids(ok(get(admin_client, url(10))))
        # 500 Ignored Thing and 501 Renamed Thing are unpriced: by name
        assert ids(ok(get(admin_client, url(10))))[-2:] == [500, 501]

    def test_name_ignoring_case_then_id(self, admin_client, data):
        cm.product(601, 'ahri, Nine-Tailed Fox', metacard=3)
        db.session.commit()
        assert ids(ok(get(admin_client, url(10, 'sort=name')))) == [
            250, 601, 500, 100, 101, 400, 300, 501, 200]

    def test_added_newest_first_undated_last(self, admin_client, data):
        db.session.add(RbcmExpansion(rbexp_id=20, rbexp_name=None))
        cm.product(2000, 'Old', expansion=20, date_added='2025-06-01 10:00:00')
        cm.product(2001, 'New', expansion=20, date_added='2025-07-14 16:11:32')
        cm.product(2002, 'Undated', expansion=20)
        cm.product(2003, 'Also new', expansion=20, date_added='2025-07-14 16:11:32')
        db.session.commit()
        assert ids(ok(get(admin_client, url(20, 'sort=added')))) == [2003, 2001, 2000, 2002]


# ---------------------------------------------------------------------------
# S9, S10: paging and meta
# ---------------------------------------------------------------------------

def many(n, expansion=20):
    db.session.add(RbcmExpansion(rbexp_id=expansion, rbexp_name=None))
    for k in range(n):
        pid = 10000 + k
        cm.product(pid, f'Card {k:04d}', expansion=expansion)
        cm.price(pid, k + 1)
    db.session.commit()


class TestPaging:
    @pytest.mark.parametrize('per_page', [50, 100, 200])
    def test_pages(self, admin_client, data, per_page):
        many(230)
        first = ok(get(admin_client, url(20, f'per_page={per_page}')))
        assert len(first['items']) == min(per_page, 230)
        assert first['items'][0]['id_product'] == 10229          # the dearest
        assert {key: first['meta'][key] for key in ('page', 'per_page', 'total', 'pages')} \
            == {'page': 1, 'per_page': per_page, 'total': 230,
                'pages': (230 + per_page - 1) // per_page}
        last_page = first['meta']['pages']
        last = ok(get(admin_client, url(20, f'per_page={per_page}&page={last_page}')))
        assert len(last['items']) == 230 - per_page * (last_page - 1)
        assert last['items'][-1]['id_product'] == 10000

    def test_every_product_once_across_the_pages(self, admin_client, data):
        many(120)
        seen = []
        for page in (1, 2, 3):
            seen += ids(ok(get(admin_client, url(20, f'page={page}'))))
        assert sorted(seen) == list(range(10000, 10120))

    def test_a_page_past_the_end_is_empty(self, admin_client, data):
        got = ok(get(admin_client, url(10, 'page=9')))
        assert got['items'] == []
        assert (got['meta']['page'], got['meta']['total'], got['meta']['pages']) == (9, 8, 1)


class TestMeta:
    def test_the_whole_expansion_whatever_the_filters(self, admin_client, data):
        cm.product(600, 'Late', date_added='2025-06-01 10:00:00')
        cm.product(601, 'Later', date_added='2025-07-14 16:11:32')
        db.session.commit()
        expected = {'singles': 9, 'sealed': 1, 'price_range': {'min': 0.1, 'max': 9.0},
                    'first_seen': '2025-06-01', 'date': '2030-10-02'}
        for query in ('', 'type=sealed', 'q=nothing', 'page=3&per_page=200', 'sort=name'):
            meta = ok(get(admin_client, url(10, query)))['meta']
            assert {key: meta[key] for key in expected} == expected, query

    def test_the_figures_are_the_list_row(self, admin_client, data):
        rows = {item['id']: item for item in ok(get(admin_client, BASE))['items']}
        for one in (10, 12):
            meta = ok(get(admin_client, url(one)))['meta']
            assert (meta['singles'], meta['sealed'], meta['price_range'],
                    meta['first_seen']) == (rows[one]['singles_count'],
                                            rows[one]['sealed_count'],
                                            rows[one]['price_range'],
                                            rows[one]['first_seen'])


# ---------------------------------------------------------------------------
# S11: validation
# ---------------------------------------------------------------------------

class TestValidation:
    @pytest.mark.parametrize('query', [
        'type=nonsingle', 'type=single,sealed', 'sort=low', 'kind=single', 'kind=sealed',
        'kind=cards', 'kind=Card', 'kind=card,box', 'kind=nonsingle', 'per_page=25', 'per_page=500', 'page=0',
        'page=x', 'dir=asc', 'q=' + 'x' * 101])
    def test_a_bad_query_is_400(self, admin_client, data, query):
        body = err(get(admin_client, url(10, query)), 400, 'validation_error')
        assert body['message'] == 'Invalid query parameters'

    def test_a_blank_type_is_the_default(self, admin_client, data):
        # `validate_query` drops empty values: `type=` is absent, so all
        assert ids(ok(get(admin_client, url(10, 'type=')))) == \
            ids(ok(get(admin_client, url(10))))


# ---------------------------------------------------------------------------
# S12: statements
# ---------------------------------------------------------------------------

def statements(client, target):
    counted = []

    def before(conn, cursor, statement, params, context, executemany):
        counted.append(statement)

    event.listen(db.engine, 'before_cursor_execute', before)
    try:
        resp = client.get(target)
        assert resp.status_code == 200, resp.get_json()
    finally:
        event.remove(db.engine, 'before_cursor_execute', before)
    return counted


class TestStatements:
    def test_bounded_whatever_the_size_and_the_page(self, admin_client, data):
        small = len(statements(admin_client, url(10)))
        many(400)
        for pid in range(10000, 10400, 3):
            cm.link(pid, 'OGN', str(pid))
        db.session.add_all(RbProducts(rbpdt_id_product=pid, rbpdt_name=f'P {pid}',
                                      rbpdt_type='nonsingle', rbpdt_kind='box')
                           for pid in range(10001, 10400, 5))
        db.session.commit()
        for query in ('per_page=200', 'per_page=200&page=2', 'q=card&sort=name',
                      'type=sealed&sort=added', 'kind=card', 'kind=box&per_page=100',
                      'kind=other&type=sealed&q=p'):
            assert len(statements(admin_client, url(20, query))) == small, query
        # the signed-in user, the expansion with its figures, the latest date, the kind counts
        # with the total and the page
        assert small == 5, small


# ---------------------------------------------------------------------------
# S14 - S16: kinds (CM-g)
# ---------------------------------------------------------------------------

# Expansion 30 on the latest load: (id, category, catalog kind or None for no catalog row,
# or '' for a catalog row without a kind), and the kind the API gives it.
KINDS = [
    (3001, 'Riftbound Single', None, 'card'),
    (3002, 'Riftbound Single', None, 'card'),
    (3003, 'Riftbound Single', 'box', 'card'),           # a single is a card, whatever
    (3010, 'Riftbound Booster', None, 'booster'),
    (3011, 'Riftbound Booster', 'booster', 'booster'),
    (3012, 'Riftbound Booster', 'case', 'case'),         # the admin's lock wins
    (3020, 'Riftbound Display', None, 'box'),
    (3030, 'Riftbound Champion Decks', None, 'starter'),
    # in box sets the name decides (NAMES): a deck is a starter, anything else a bundle
    (3040, 'Riftbound Riftbound Box Sets', None, 'starter'),
    (3043, 'Riftbound Riftbound Box Sets', None, 'bundle'),
    (3041, 'Riftbound Riftbound Box Sets', '', 'bundle'),  # catalog row without a kind
    (3042, 'Riftbound Riftbound Box Sets', 'other', 'other'),  # an old unlocked `other` row
    (3044, 'RB Set', None, 'other'),                      # RB Set has no rule
    (3050, 'Riftbound Playmats', None, 'accessory'),
    (3060, 'Riftbound Mystery', None, 'other'),
]
# The real names of the box sets and rb set products (CM-g); the rest are 'Product <id>'
NAMES = {3040: 'Jinx Trial Deck', 3041: 'Legacy Vault', 3042: 'Unleashed Vault',
         3043: 'Bulk Runes Box', 3044: 'Origins: Full Set'}
EXPECTED_KINDS = [{'kind': 'card', 'count': 3}, {'kind': 'booster', 'count': 2},
                  {'kind': 'box', 'count': 1}, {'kind': 'case', 'count': 1},
                  {'kind': 'bundle', 'count': 2}, {'kind': 'starter', 'count': 2},
                  {'kind': 'accessory', 'count': 1}, {'kind': 'other', 'count': 3}]


@pytest.fixture
def kinds_data(data):
    db.session.add(RbcmExpansion(rbexp_id=30, rbexp_name=None))
    for pid, category, catalog, _ in KINDS:
        cm.product(pid, NAMES.get(pid, f'Product {pid}'), expansion=30, category=category,
                   type_='single' if category == 'Riftbound Single' else 'nonsingle')
        cm.price(pid, pid / 100)
        if catalog is not None:
            db.session.add(RbProducts(rbpdt_id_product=pid, rbpdt_name=f'Product {pid}',
                                      rbpdt_type='nonsingle', rbpdt_kind=catalog or None,
                                      rbpdt_kind_locked=catalog == 'case'))
    # an older snapshot of another kind never counts
    cm.product(3070, 'Old Display', expansion=30, type_='nonsingle', date=cm.D1,
               category='Riftbound Display')
    db.session.commit()
    return data


def kinds_of(got):
    return {item['id_product']: item['kind'] for item in got['items']}


class TestKind:
    def test_every_item_has_its_kind(self, admin_client, kinds_data):
        got = ok(get(admin_client, url(30, 'per_page=100')))
        assert kinds_of(got) == {pid: kind for pid, _, _, kind in KINDS}

    def test_the_catalog_kind_is_still_in_catalog(self, admin_client, kinds_data):
        items = {item['id_product']: item for item in ok(get(admin_client, url(30)))['items']}
        assert items[3012]['catalog'] == {'kind': 'case', 'set_id': None}
        assert items[3041]['catalog'] == {'kind': None, 'set_id': None}
        assert items[3010]['catalog'] is None

    def test_the_cm_f_data(self, admin_client, data):
        got = ok(get(admin_client, url(10)))
        assert set(kinds_of(got).values()) == {'card', 'box'}
        assert kinds_of(got)[300] == 'box'


class TestKindCounts:
    def test_counts_of_the_whole_expansion_in_a_stable_order(self, admin_client, kinds_data):
        for query in ('', 'kind=card', 'kind=box', 'type=sealed', 'q=nothing',
                      'kind=sleeves', 'page=5', 'sort=name&kind=bundle&type=single'):
            assert ok(get(admin_client, url(30, query)))['meta']['kinds'] == EXPECTED_KINDS, \
                query

    def test_the_counts_add_up_to_the_products(self, admin_client, kinds_data):
        meta = ok(get(admin_client, url(30)))['meta']
        assert sum(one['count'] for one in meta['kinds']) == meta['singles'] + meta['sealed'] \
            == meta['total'] == len(KINDS)
        assert meta['kinds'][0] == {'kind': 'card', 'count': meta['singles']}

    def test_the_cm_f_data(self, admin_client, data):
        assert ok(get(admin_client, url(10)))['meta']['kinds'] == [
            {'kind': 'card', 'count': 7}, {'kind': 'box', 'count': 1}]
        assert ok(get(admin_client, url(12)))['meta']['kinds'] == [
            {'kind': 'accessory', 'count': 1}]


class TestKindFilter:
    @pytest.mark.parametrize('kind', ['card', 'booster', 'box', 'case', 'bundle', 'starter',
                                      'sleeves', 'accessory', 'other'])
    def test_one_kind(self, admin_client, kinds_data, kind):
        got = ok(get(admin_client, url(30, f'kind={kind}')))
        expected = sorted(pid for pid, _, _, one in KINDS if one == kind)
        assert sorted(ids(got)) == expected
        assert set(kinds_of(got).values()) <= {kind}
        assert (got['meta']['total'], got['meta']['pages']) == (len(expected), 1)

    def test_all_is_every_kind(self, admin_client, kinds_data):
        assert ids(ok(get(admin_client, url(30, 'kind=all')))) == ids(ok(get(admin_client,
                                                                              url(30))))
        assert ok(get(admin_client, url(30, 'kind=all')))['meta']['total'] == len(KINDS)

    def test_dearest_first_within_a_kind(self, admin_client, kinds_data):
        # 3012 is a booster category the admin made a case
        assert ids(ok(get(admin_client, url(30, 'kind=booster')))) == [3011, 3010]
        assert ids(ok(get(admin_client, url(30, 'kind=bundle')))) == [3043, 3041]
        assert ids(ok(get(admin_client, url(30, 'kind=starter')))) == [3040, 3030]

    @pytest.mark.parametrize('query,expected', [
        ('kind=card&type=single', [3003, 3002, 3001]),
        ('kind=card&type=sealed', []),
        ('kind=booster&type=single', []),
        ('kind=booster&type=sealed', [3011, 3010]),
        ('kind=card&q=3002', [3002]),
        ('kind=other&q=3060', [3060]),
        ('kind=other&q=3002', []),
    ])
    def test_kind_combines_with_type_and_q(self, admin_client, kinds_data, query, expected):
        got = ok(get(admin_client, url(30, query)))
        assert ids(got) == expected
        assert got['meta']['total'] == len(expected)

    def test_pages_of_one_kind(self, admin_client, data):
        many(120)
        cm.product(20999, 'A booster', expansion=20, type_='nonsingle',
                   category='Riftbound Booster')
        db.session.commit()
        got = ok(get(admin_client, url(20, 'kind=card&page=3')))
        assert (got['meta']['total'], got['meta']['pages'], len(got['items'])) == (120, 3, 20)
        got = ok(get(admin_client, url(20, 'kind=booster')))
        assert (ids(got), got['meta']['total'], got['meta']['pages']) == ([20999], 1, 1)

    def test_a_blank_kind_is_all(self, admin_client, kinds_data):
        assert ids(ok(get(admin_client, url(30, 'kind=')))) == ids(ok(get(admin_client,
                                                                           url(30))))
