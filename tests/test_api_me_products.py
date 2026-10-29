"""F14-c S3, S4 (AC2): GET/POST /me/products, PATCH/DELETE /me/products/<id>."""
from datetime import datetime

import pytest

from tests.product_helpers import (add_owned, add_price, add_product, add_sets, count_statements,
                                   owned_rows)
from app import db

BASE = '/riftbound/api/v1/me/products'
NOT_FOUND = {'success': False, 'error': 'Not Found',
             'message': 'The requested resource was not found'}
EMPTY_TOTAL = {'value': 0.0, 'lines': 0, 'qty': 0, 'unpriced': 0}


def _seed():
    add_sets()
    add_product(1, 'Origins Booster', kind='booster', category='Riftbound Boosters')
    add_product(2, 'Origins Booster Box', kind='box', category='Riftbound Booster Boxes')
    add_product(4, 'Origins Sleeves', kind='sleeves', set_id=None, category='Sleeves')
    add_product(6, 'Secret Case', kind='case', hidden=True)
    add_product(7, 'A single card', kind='other', type_='single')
    add_price(1, '20261014', trend=4)
    add_price(1, '20261021', avg7=0, trend=5, low=4.5)     # 5.00 (trend)
    add_price(2, '20261021', avg7=100, trend=98, low=90)   # 100.00 (avg7)
    add_price(6, '20261021', trend=300)
    db.session.commit()


@pytest.fixture
def api(app, authenticated_client):
    with app.app_context():
        _seed()
    return authenticated_client


def _data(resp, status=200):
    assert resp.status_code == status, resp.get_json()
    body = resp.get_json()
    assert body['success'] is True
    return body['data']


class TestList:
    def test_empty(self, api):
        assert _data(api.get(BASE)) == {'items': [], 'total': EMPTY_TOTAL}

    def test_line_shape_and_values(self, api):
        add_owned(2, 2, purchase=80, note='Sealed', at=datetime(2026, 10, 2, 8, 0, 5))
        data = _data(api.get(BASE))
        assert list(data) == ['items', 'total']
        [line] = data['items']
        assert list(line) == ['id', 'product', 'quantity', 'purchase_price', 'note', 'value',
                              'pl_abs', 'pl_pct', 'updated_at']
        assert list(line['product']) == ['id', 'name', 'kind', 'category', 'set_id',
                                         'image_src', 'listed', 'price', 'owned_qty']
        assert line == {
            'id': owned_rows()[0].rbupr_id,
            'product': {
                'id': 2, 'name': 'Origins Booster Box', 'kind': 'box',
                'category': 'Riftbound Booster Boxes', 'set_id': 'OGN', 'image_src': None,
                'listed': True,
                'price': {'value': 100.0, 'source': 'avg7', 'change_7d_pct': None,
                          'change_30d_pct': None, 'as_of': '2026-10-21'},
                'owned_qty': 2,
            },
            'quantity': 2, 'purchase_price': 80.0, 'note': 'Sealed', 'value': 200.0,
            'pl_abs': 40.0, 'pl_pct': 25.0, 'updated_at': '2026-10-02T08:00:05Z',
        }
        assert data['total'] == {'value': 200.0, 'lines': 1, 'qty': 2, 'unpriced': 0}

    def test_order_totals_unpriced_and_owned_qty(self, api):
        add_owned(4, 1)                       # no price
        add_owned(1, 3, purchase=3)           # booster 5.00 x3
        add_owned(2, 1)                       # box 100.00, no purchase price
        add_owned(1, 2)                       # booster again, other line
        add_owned(6, 1, purchase=0)           # hidden, but the caller owns it
        data = _data(api.get(BASE))
        assert [(i['product']['name'], i['quantity']) for i in data['items']] == [
            ('Origins Booster', 3), ('Origins Booster', 2), ('Origins Booster Box', 1),
            ('Origins Sleeves', 1), ('Secret Case', 1)]
        by_qty = {(i['product']['id'], i['quantity']): i for i in data['items']}
        assert by_qty[(1, 3)]['product']['owned_qty'] == 5
        assert (by_qty[(1, 3)]['value'], by_qty[(1, 3)]['pl_abs'], by_qty[(1, 3)]['pl_pct']) == (
            15.0, 6.0, 66.7)
        assert (by_qty[(2, 1)]['value'], by_qty[(2, 1)]['pl_abs'], by_qty[(2, 1)]['pl_pct']) == (
            100.0, None, None)
        assert (by_qty[(4, 1)]['value'], by_qty[(4, 1)]['product']['price']) == (None, None)
        # A purchase price of 0 gives no P/L (F3-b S3).
        assert (by_qty[(6, 1)]['value'], by_qty[(6, 1)]['pl_abs']) == (300.0, None)
        assert data['total'] == {'value': 425.0, 'lines': 5, 'qty': 8, 'unpriced': 1}

    def test_another_users_lines_are_never_shown(self, api, other_user_client):
        add_owned(1, 4, user='otheruser')
        assert _data(api.get(BASE)) == {'items': [], 'total': EMPTY_TOTAL}
        theirs = _data(other_user_client.get(BASE))
        assert [i['quantity'] for i in theirs['items']] == [4]

    def test_statement_count_does_not_grow(self, api, app):
        add_owned(1, 1)
        _, few = count_statements(app, lambda: api.get(BASE))
        for product_id in (2, 4, 6):
            for _ in range(3):
                add_owned(product_id, 1)
        resp, many = count_statements(app, lambda: api.get(BASE))
        assert len(resp.get_json()['data']['items']) == 10
        assert few == many and many <= 6, (few, many)


class TestAdd:
    def test_creates_a_line(self, api, frozen_clock):
        resp = api.post(BASE, json={'product_id': 2, 'quantity': 3, 'purchase_price': 90.5,
                                    'note': '  From the store  '})
        data = _data(resp, 201)
        assert data['merged'] is False
        line = data['line']
        assert (line['quantity'], line['purchase_price'], line['note'], line['value'],
                line['pl_abs'], line['pl_pct']) == (3, 90.5, 'From the store', 300.0, 28.5, 10.5)
        assert line['product']['owned_qty'] == 3
        assert line['updated_at'] == '2030-01-01T12:00:00Z'
        [row] = owned_rows()
        assert (row.rbupr_id, row.rbupr_quantity, float(row.rbupr_purchase_price)) == (
            line['id'], 3, 90.5)
        assert row.rbupr_created_at == row.rbupr_updated_at == datetime(2030, 1, 1, 12, 0)

    def test_optional_fields_default_to_null(self, api):
        line = _data(api.post(BASE, json={'product_id': 4, 'quantity': 1}), 201)['line']
        assert (line['purchase_price'], line['note'], line['value']) == (None, None, None)

    def test_an_empty_note_is_no_note(self, api):
        line = _data(api.post(BASE, json={'product_id': 4, 'quantity': 1, 'note': '   '}),
                     201)['line']
        assert line['note'] is None

    def test_money_is_rounded_half_up(self, api):
        line = _data(api.post(BASE, json={'product_id': 1, 'quantity': 1,
                                          'purchase_price': 1.005}), 201)['line']
        assert line['purchase_price'] == 1.01
        assert str(owned_rows()[0].rbupr_purchase_price) == '1.01'

    def test_same_product_and_price_merges(self, api, frozen_clock):
        first = _data(api.post(BASE, json={'product_id': 1, 'quantity': 2,
                                           'purchase_price': 4}), 201)['line']
        frozen_clock.advance(minutes=5)
        data = _data(api.post(BASE, json={'product_id': 1, 'quantity': 3,
                                          'purchase_price': 4.0}), 201)
        assert data['merged'] is True
        assert (data['line']['id'], data['line']['quantity']) == (first['id'], 5)
        assert data['line']['updated_at'] == '2030-01-01T12:05:00Z'
        assert [row.rbupr_quantity for row in owned_rows()] == [5]

    def test_merge_is_null_safe(self, api):
        api.post(BASE, json={'product_id': 1, 'quantity': 1})
        data = _data(api.post(BASE, json={'product_id': 1, 'quantity': 1,
                                          'purchase_price': None}), 201)
        assert data['merged'] is True
        assert [(r.rbupr_quantity, r.rbupr_purchase_price) for r in owned_rows()] == [(2, None)]

    def test_merge_keeps_the_note_and_fills_a_missing_one(self, api):
        api.post(BASE, json={'product_id': 1, 'quantity': 1})
        api.post(BASE, json={'product_id': 1, 'quantity': 1, 'note': 'gift'})
        api.post(BASE, json={'product_id': 1, 'quantity': 1, 'note': 'other'})
        assert [(r.rbupr_quantity, r.rbupr_note) for r in owned_rows()] == [(3, 'gift')]

    def test_another_price_or_product_is_a_new_line(self, api):
        api.post(BASE, json={'product_id': 1, 'quantity': 1})
        api.post(BASE, json={'product_id': 1, 'quantity': 1, 'purchase_price': 4})
        api.post(BASE, json={'product_id': 2, 'quantity': 1, 'purchase_price': 4})
        assert [(r.rbupr_id_product, r.rbupr_quantity) for r in owned_rows()] == [
            (1, 1), (1, 1), (2, 1)]

    def test_never_merges_into_another_users_line(self, api, other_user_client):
        add_owned(1, 2, user='otheruser')
        assert _data(api.post(BASE, json={'product_id': 1, 'quantity': 1}), 201)[
            'merged'] is False
        assert [r.rbupr_quantity for r in owned_rows('otheruser')] == [2]

    def test_a_merge_past_9999_is_refused(self, api):
        add_owned(1, 9990)
        resp = api.post(BASE, json={'product_id': 1, 'quantity': 10})
        body = resp.get_json()
        assert resp.status_code == 400 and body['code'] == 'validation_error'
        assert body['details'] == [{'field': 'quantity', 'message': 'at most 9999 in one line',
                                    'type': 'value_error', 'code': 'out_of_range',
                                    'params': {'max': 9999}}]
        assert [r.rbupr_quantity for r in owned_rows()] == [9990]
        assert _data(api.post(BASE, json={'product_id': 1, 'quantity': 9}), 201)['line'][
            'quantity'] == 9999

    def test_a_hidden_product_can_be_added(self, api):
        line = _data(api.post(BASE, json={'product_id': 6, 'quantity': 1}), 201)['line']
        assert line['product']['name'] == 'Secret Case'

    @pytest.mark.parametrize('product_id', [999, 7])
    def test_unknown_or_single_product(self, api, product_id):
        resp = api.post(BASE, json={'product_id': product_id, 'quantity': 1})
        body = resp.get_json()
        assert resp.status_code == 400 and body['code'] == 'validation_error'
        assert body['details'] == [{'field': 'product_id', 'message': 'unknown product',
                                    'type': 'value_error', 'code': 'invalid_value'}]
        assert owned_rows() == []

    @pytest.mark.parametrize('body', [
        {'quantity': 0}, {'quantity': 10000}, {'quantity': 1.5}, {'quantity': '3'},
        {'quantity': True}, {'quantity': None}, {'purchase_price': -0.01},
        {'purchase_price': 100000}, {'purchase_price': 'x'}, {'note': 'x' * 201},
        {'product_id': '1'}, {'product_id': None},
    ])
    def test_invalid_bodies_are_a_400_and_store_nothing(self, api, body):
        resp = api.post(BASE, json={'product_id': 1, 'quantity': 1, **body})
        assert resp.status_code == 400, body
        assert resp.get_json()['code'] == 'validation_error'
        assert owned_rows() == []

    def test_limits_are_inclusive(self, api):
        _data(api.post(BASE, json={'product_id': 1, 'quantity': 9999,
                                   'purchase_price': 99999.99, 'note': 'x' * 200}), 201)

    def test_missing_fields_are_required(self, api):
        resp = api.post(BASE, json={})
        details = {d['field']: d['code'] for d in resp.get_json()['details']}
        assert details == {'product_id': 'required', 'quantity': 'required'}


class TestPatch:
    def test_changes_only_the_sent_fields(self, api, frozen_clock):
        row = add_owned(2, 2, purchase=80, note='Sealed')
        line = _data(api.patch(f'{BASE}/{row.rbupr_id}', json={'quantity': 4}))
        assert (line['id'], line['quantity'], line['purchase_price'], line['note'],
                line['value']) == (row.rbupr_id, 4, 80.0, 'Sealed', 400.0)
        assert line['updated_at'] == '2030-01-01T12:00:00Z'
        line = _data(api.patch(f'{BASE}/{row.rbupr_id}', json={'purchase_price': 120.004,
                                                               'note': 'Opened'}))
        assert (line['quantity'], line['purchase_price'], line['note'], line['pl_abs'],
                line['pl_pct']) == (4, 120.0, 'Opened', -80.0, -16.7)
        [stored] = owned_rows()
        assert (stored.rbupr_quantity, float(stored.rbupr_purchase_price), stored.rbupr_note) == (
            4, 120.0, 'Opened')
        assert stored.rbupr_created_at == datetime(2026, 10, 1, 9, 30)

    def test_null_clears_the_price_and_the_note(self, api):
        row = add_owned(2, 2, purchase=80, note='Sealed')
        line = _data(api.patch(f'{BASE}/{row.rbupr_id}', json={'purchase_price': None,
                                                               'note': None}))
        assert (line['purchase_price'], line['note'], line['pl_abs']) == (None, None, None)

    @pytest.mark.parametrize('body', [
        {'quantity': None}, {'quantity': 0}, {'quantity': 10000}, {'quantity': '2'},
        {'purchase_price': -1}, {'note': 'x' * 201},
    ])
    def test_invalid_bodies_change_nothing(self, api, body):
        row = add_owned(2, 2, purchase=80)
        resp = api.patch(f'{BASE}/{row.rbupr_id}', json=body)
        assert resp.status_code == 400, body
        assert resp.get_json()['code'] == 'validation_error'
        [stored] = owned_rows()
        assert (stored.rbupr_quantity, float(stored.rbupr_purchase_price)) == (2, 80.0)

    def test_foreign_and_missing_ids_are_404(self, api, other_user_client):
        theirs = add_owned(1, 2, user='otheruser')
        for line_id in (theirs.rbupr_id, 999):
            resp = api.patch(f'{BASE}/{line_id}', json={'quantity': 5})
            assert resp.status_code == 404, line_id
            assert resp.get_json() == NOT_FOUND
        assert [r.rbupr_quantity for r in owned_rows('otheruser')] == [2]


class TestDelete:
    def test_deletes_and_returns_the_line(self, api):
        row = add_owned(2, 2, purchase=80, note='Sealed')
        line_id = row.rbupr_id
        data = _data(api.delete(f'{BASE}/{line_id}'))
        assert list(data) == ['deleted']
        assert (data['deleted']['id'], data['deleted']['quantity'], data['deleted']['note'],
                data['deleted']['product']['id']) == (line_id, 2, 'Sealed', 2)
        assert owned_rows() == []

    def test_the_deleted_line_can_be_posted_back(self, api):
        row = add_owned(2, 2, purchase=80, note='Sealed')
        deleted = _data(api.delete(f'{BASE}/{row.rbupr_id}'))['deleted']
        body = {'product_id': deleted['product']['id'], **deleted}
        line = _data(api.post(BASE, json=body), 201)['line']
        assert (line['quantity'], line['purchase_price'], line['note']) == (2, 80.0, 'Sealed')

    def test_foreign_and_missing_ids_are_404(self, api, other_user_client):
        theirs = add_owned(1, 2, user='otheruser')
        for line_id in (theirs.rbupr_id, 999):
            resp = api.delete(f'{BASE}/{line_id}')
            assert resp.status_code == 404, line_id
            assert resp.get_json() == NOT_FOUND
        assert len(owned_rows('otheruser')) == 1


class TestAuthz:
    def test_anonymous_gets_a_json_401(self, client, app):
        for method, url in (('get', BASE), ('post', BASE), ('patch', f'{BASE}/1'),
                            ('delete', f'{BASE}/1')):
            resp = getattr(client, method)(url, json={} if method in ('post', 'patch') else None)
            assert resp.status_code == 401, (method, url)
            assert resp.get_json()['code'] == 'unauthenticated'

    def test_endpoint_names(self, app):
        found = sorted((r.rule, r.endpoint, tuple(sorted(r.methods - {'HEAD', 'OPTIONS'})))
                       for r in app.url_map.iter_rules() if r.rule.startswith(BASE))
        assert found == [
            (BASE, 'api_v1.create_my_product', ('POST',)),
            (BASE, 'api_v1.list_my_products', ('GET',)),
            (f'{BASE}/<int:line_id>', 'api_v1.delete_my_product', ('DELETE',)),
            (f'{BASE}/<int:line_id>', 'api_v1.update_my_product', ('PATCH',)),
        ]
