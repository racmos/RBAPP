"""F14-c S6 (AC4): the products total is never part of the collection value; the daily snapshot
keeps it apart in `rbvsn_products_value`."""
from datetime import date
from decimal import Decimal

import pytest
import sqlalchemy as sa

from app import db
from app.models import RbValueSnapshot
from app.services.snapshots import take_snapshots
from tests.collection_read_helpers import URL as COLLECTION, seed_catalog, seed_lines
from tests.product_helpers import add_owned, add_price, add_product, user_id

DAY = date(2030, 1, 1)
PRODUCTS = '/riftbound/api/v1/me/products'


def _seed_products():
    # Ids far from the card products of `seed_catalog` (1, 2, 11, 79).
    add_product(501, 'Origins Booster Box', kind='box')
    add_product(502, 'Origins Booster', kind='booster')
    add_product(503, 'Origins Sleeves', kind='sleeves', set_id=None)
    add_price(501, '20261020', avg7=100.005)
    add_price(502, '20261020', trend=4.335)
    db.session.commit()


@pytest.fixture
def api(app, authenticated_client, make_user):
    make_user('otheruser')
    make_user('boxer')            # products, no cards
    make_user('lonely')           # neither
    with app.app_context():
        seed_catalog()
        seed_lines()
        _seed_products()
    return authenticated_client


def _stored():
    db.session.expire_all()
    return {row.rbvsn_user_id: row for row in db.session.execute(
        sa.select(RbValueSnapshot)).scalars()}


def test_adding_products_leaves_the_collection_untouched(api):
    before = api.get(COLLECTION).get_json()
    for body in ({'product_id': 501, 'quantity': 2, 'purchase_price': 50},
                 {'product_id': 502, 'quantity': 3}):
        assert api.post(PRODUCTS, json=body).status_code == 201
    after = api.get(COLLECTION).get_json()
    assert after == before
    assert after['meta']['totals']['value'] == 125.0


def test_snapshot_values_stay_apart(api):
    take_snapshots(DAY)
    cards_only = {uid: (row.rbvsn_value, row.rbvsn_cost, row.rbvsn_qty, row.rbvsn_unique,
                        row.rbvsn_unpriced) for uid, row in _stored().items()}
    add_owned(501, 2, purchase=50)       # 100.005 x2 = 200.01
    add_owned(502, 3)                    # 4.335 x3 = 13.005 -> 13.01 (half up, per line)
    add_owned(503, 1)                    # unpriced
    result = take_snapshots(DAY)
    rows = _stored()
    mine = rows[user_id('testuser')]
    assert mine.rbvsn_products_value == Decimal('213.02')
    assert (mine.rbvsn_value, mine.rbvsn_cost, mine.rbvsn_qty, mine.rbvsn_unique,
            mine.rbvsn_unpriced) == cards_only[mine.rbvsn_user_id]
    # A user with cards and no products keeps NULL.
    assert rows[user_id('otheruser')].rbvsn_products_value is None
    assert result == {'date': '2030-01-01', 'users': 2, 'rows': 2, 'total_value': 215.0,
                      'products_value': 213.02}


def test_the_products_value_matches_the_products_total(api):
    for body in ({'product_id': 501, 'quantity': 2, 'purchase_price': 50},
                 {'product_id': 502, 'quantity': 3}, {'product_id': 503, 'quantity': 1}):
        api.post(PRODUCTS, json=body)
    take_snapshots(DAY)
    total = api.get(PRODUCTS).get_json()['data']['total']
    assert float(_stored()[user_id('testuser')].rbvsn_products_value) == total['value']


def test_a_products_only_user_gets_a_row(api):
    add_owned(501, 1, user='boxer')
    add_owned(503, 4, user='boxer')
    result = take_snapshots(DAY)
    rows = _stored()
    boxer = rows[user_id('boxer')]
    assert (boxer.rbvsn_value, boxer.rbvsn_cost, boxer.rbvsn_qty, boxer.rbvsn_unique,
            boxer.rbvsn_unpriced, boxer.rbvsn_products_value) == (
        Decimal('0'), None, 0, 0, 0, Decimal('100.01'))
    assert user_id('lonely') not in rows
    assert (result['users'], result['rows'], result['total_value'],
            result['products_value']) == (3, 3, 215.0, 100.01)


def test_a_products_only_user_with_unpriced_products(api):
    add_owned(503, 1, user='boxer')
    take_snapshots(DAY)
    assert _stored()[user_id('boxer')].rbvsn_products_value == Decimal('0')


def test_a_second_run_replaces_the_products_value(api):
    add_owned(502, 1, user='boxer')
    take_snapshots(DAY)
    add_owned(502, 1, user='boxer')
    take_snapshots(DAY)
    rows = _stored()
    assert rows[user_id('boxer')].rbvsn_products_value == Decimal('8.68')
    assert len(rows) == 3
