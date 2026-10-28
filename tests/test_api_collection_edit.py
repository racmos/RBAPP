"""F3-c S1, S3 (AC2): PATCH /collection/<id>."""
import pytest

from app import db
from tests.collection_write_helpers import BASE, all_rows, fetch, line, seed_catalog


@pytest.fixture
def api(app, authenticated_client, make_user):
    make_user('otheruser')
    with app.app_context():
        seed_catalog()
        mine = line('1', 5, purchase=8, selling='Y', sell_qty=2, sell_price=12.5)
        foreign = line('1', 4, user='otheruser')
        db.session.add_all([mine, foreign])
        db.session.commit()
        authenticated_client.mine = mine.rbcol_id
        authenticated_client.foreign = foreign.rbcol_id
    return authenticated_client


def patch(api, line_id=None, **body):
    return api.patch(f'{BASE}/{line_id or api.mine}', json=body)


def updated(api):
    return api.get(BASE).get_json()['data']['items'][0]['lines'][0]['updated_at']


class TestFields:
    @pytest.mark.parametrize('field, value, check', [
        ('condition', 'EX', lambda l: l['condition'] == 'EX'),
        ('condition', None, lambda l: l['condition'] is None),
        ('language', 'French', lambda l: l['language'] == 'French'),
        ('language', None, lambda l: l['language'] is None),
        ('purchase_price', 9.5, lambda l: l['purchase_price'] == 9.5),
        ('purchase_price', None, lambda l: l['purchase_price'] is None and l['pl_abs'] is None),
        ('sell_price', 14, lambda l: l['sell_price'] == 14.0),
        ('sell_price', None, lambda l: l['sell_price'] is None),
        ('qty', 7, lambda l: l['qty'] == 7 and l['value'] == 70.0),
        ('sell_qty', 4, lambda l: l['sell_qty'] == 4),
    ])
    def test_each_field(self, api, field, value, check):
        response = patch(api, **{field: value})
        assert response.status_code == 200, response.get_data(as_text=True)
        assert check(response.get_json()['data'])

    def test_the_answer_is_the_line_with_set_and_card(self, api):
        data = patch(api, condition='GD').get_json()['data']
        assert (data['id'], data['set_id'], data['card_id']) == (api.mine, 'OGN', '1')

    def test_only_the_sent_fields_change(self, api):
        patch(api, condition='LP')
        row = fetch(api.mine)
        assert (row.rbcol_condition, row.rbcol_quantity, row.rbcol_sell_qty) == ('LP', 5, 2)
        assert float(row.rbcol_purchase_price) == 8.0

    def test_every_write_stamps_the_change_time(self, api, frozen_clock):
        frozen_clock.advance(hours=1)
        patch(api, condition='LP')
        assert fetch(api.mine).rbcol_chadat == frozen_clock()

    @pytest.mark.parametrize('body', [{'qty': 0}, {'qty': 10000}, {'condition': 'XX'},
                                      {'purchase_price': -1}, {'selling': 'x'}, {'sell_qty': -1},
                                      {'if_updated_at': 'yesterday'}, {'language': 'x' * 41}])
    def test_invalid_values_are_a_400_and_change_nothing(self, api, body):
        response = patch(api, **body)
        assert response.status_code == 400 and response.get_json()['code'] == 'validation_error'
        assert fetch(api.mine).rbcol_quantity == 5

    def test_money_is_rounded_half_up(self, api):
        assert patch(api, sell_price=2.675).get_json()['data']['sell_price'] == 2.68


class TestQuantities:
    def test_lowering_qty_below_sell_qty_lowers_sell_qty(self, api):
        data = patch(api, qty=1).get_json()['data']
        assert (data['qty'], data['sell_qty']) == (1, 1)

    def test_lowering_qty_above_sell_qty_keeps_it(self, api):
        data = patch(api, qty=3).get_json()['data']
        assert (data['qty'], data['sell_qty']) == (3, 2)

    def test_sell_qty_above_qty_is_refused(self, api):
        response = patch(api, sell_qty=6)
        body = response.get_json()
        assert response.status_code == 409
        assert (body['code'], body['params']) == ('insufficient_quantity', {'available': 5})
        assert fetch(api.mine).rbcol_sell_qty == 2

    def test_qty_and_sell_qty_together_are_checked_against_the_new_qty(self, api):
        assert patch(api, qty=8, sell_qty=7).status_code == 200
        response = patch(api, qty=3, sell_qty=4)
        assert response.status_code == 409
        assert response.get_json()['params'] == {'available': 3}
        assert (fetch(api.mine).rbcol_quantity, fetch(api.mine).rbcol_sell_qty) == (8, 7)


class TestSelling:
    def test_selling_true_without_a_price_asks_market_plus_five_percent(self, api):
        patch(api, selling=False, sell_price=None)
        data = patch(api, selling=True).get_json()['data']
        assert (data['selling'], data['sell_price']) == (True, 10.5)

    def test_selling_true_keeps_a_price_the_line_has(self, api):
        patch(api, selling=False)
        assert patch(api, selling=True).get_json()['data']['sell_price'] == 12.5

    def test_selling_true_on_a_line_with_nothing_for_sale_sells_everything(self, api):
        patch(api, selling=False, sell_qty=0)
        assert patch(api, selling=True).get_json()['data']['sell_qty'] == 5

    def test_selling_false_keeps_quantity_and_price(self, api):
        data = patch(api, selling=False).get_json()['data']
        assert (data['selling'], data['sell_qty'], data['sell_price']) == (False, 2, 12.5)


class TestOwnership:
    def test_another_users_line_is_a_404_and_untouched(self, api):
        response = patch(api, api.foreign, condition='PO')
        assert response.status_code == 404
        assert fetch(api.foreign).rbcol_condition == 'NM'

    def test_a_missing_line_is_a_404(self, api):
        assert patch(api, 99999, condition='PO').status_code == 404

    def test_requires_a_session(self, app, api):
        assert app.test_client().patch(f'{BASE}/{api.mine}', json={}).status_code == 401


class TestStaleGuard:
    def test_matching_if_updated_at_is_accepted(self, api):
        stamp = updated(api)
        assert patch(api, condition='EX', if_updated_at=stamp).status_code == 200

    def test_a_different_if_updated_at_is_a_409_and_changes_nothing(self, api):
        response = patch(api, condition='EX', if_updated_at='2020-01-01T00:00:00Z')
        body = response.get_json()
        assert response.status_code == 409 and body['code'] == 'stale_line'
        assert fetch(api.mine).rbcol_condition == 'NM'

    def test_a_second_edit_with_the_old_stamp_is_stale(self, api, frozen_clock):
        stamp = updated(api)
        frozen_clock.advance(minutes=5)
        assert patch(api, condition='EX', if_updated_at=stamp).status_code == 200
        assert patch(api, condition='GD', if_updated_at=stamp).status_code == 409
        assert fetch(api.mine).rbcol_condition == 'EX'

    def test_the_stamp_may_be_naive_or_end_with_z(self, api):
        stamp = updated(api)
        assert patch(api, language='Korean', if_updated_at=stamp.rstrip('Z')).status_code == 200
