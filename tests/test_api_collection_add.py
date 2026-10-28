"""F3-c S2 (AC1): POST /collection."""
import pytest

from app import db
from tests.collection_write_helpers import BASE, all_rows, card, line, seed_catalog


@pytest.fixture
def api(app, authenticated_client, make_user):
    make_user('otheruser')
    with app.app_context():
        seed_catalog()
    return authenticated_client


def post(api, **body):
    return api.post(BASE, json=card(**body))


class TestCreate:
    def test_creates_a_line_and_answers_201_with_the_line(self, api):
        response = post(api, qty=2, condition='NM', language='English', purchase_price=8)
        assert response.status_code == 201
        data = response.get_json()['data']
        assert data['merged'] is False
        created = data['line']
        assert (created['set_id'], created['card_id']) == ('OGN', '1')
        assert (created['foil'], created['qty'], created['condition'], created['language']) == (
            False, 2, 'NM', 'English')
        assert (created['purchase_price'], created['selling'], created['sell_qty']) == (
            8.0, False, 0)
        assert (created['market'], created['value'], created['pl_abs'], created['pl_pct']) == (
            10.0, 20.0, 4.0, 25.0)
        assert [row.rbcol_quantity for row in all_rows()] == [2]

    def test_requires_a_session(self, app):
        assert app.test_client().post(BASE, json=card()).status_code == 401

    @pytest.mark.parametrize('body', [
        {'qty': 0}, {'qty': 10000}, {'qty': 1.5}, {'qty': '3'}, {'qty': True},
        {'condition': 'XX'}, {'language': 'x' * 41}, {'purchase_price': -1},
        {'purchase_price': 100000}, {'sell_price': -0.01}, {'selling': 'yes'},
        {'foil': 'no'}, {'sell_qty': -1},
    ])
    def test_invalid_bodies_are_a_400_and_store_nothing(self, api, body):
        response = post(api, **body)
        assert response.status_code == 400, body
        assert response.get_json()['code'] == 'validation_error'
        assert all_rows() == []

    def test_missing_fields_are_required(self, api):
        response = api.post(BASE, json={'set_id': 'OGN'})
        details = {d['field']: d['code'] for d in response.get_json()['details']}
        assert details == {'card_id': 'required', 'qty': 'required'}

    def test_unknown_card(self, api):
        response = post(api, card_id='999')
        body = response.get_json()
        assert response.status_code == 400 and body['code'] == 'validation_error'
        assert body['details'] == [{'field': 'card_id', 'message': 'unknown card',
                                    'type': 'value_error', 'code': 'invalid_value'}]

    def test_an_empty_language_is_no_language(self, api):
        assert post(api, language='').get_json()['data']['line']['language'] is None

    def test_condition_and_language_may_be_null(self, api):
        created = post(api, condition=None, language=None).get_json()['data']['line']
        assert (created['condition'], created['language']) == (None, None)


class TestFoil:
    def test_foil_of_a_foilable_card_is_priced_as_foil(self, api):
        created = post(api, foil=True).get_json()['data']['line']
        assert (created['foil'], created['market']) == (True, 30.0)

    def test_foil_of_a_card_without_foil_is_refused(self, api):
        response = post(api, card_id='79', foil=True)
        body = response.get_json()
        assert response.status_code == 400
        assert body['code'] == 'foil_not_allowed'
        assert all_rows() == []

    def test_the_same_card_may_be_added_without_foil(self, api):
        assert post(api, card_id='79').status_code == 201


class TestSellingDefaults:
    def test_selling_without_sell_qty_sells_everything(self, api):
        created = post(api, qty=3, selling=True).get_json()['data']['line']
        assert (created['selling'], created['sell_qty']) == (True, 3)

    @pytest.mark.parametrize('card_id, set_id, foil, expected', [
        ('1', 'OGN', False, 10.5), ('2', 'OGN', False, 5.25), ('1', 'OGN', True, 31.5),
        ('10', 'SFD', False, None)])
    def test_selling_without_a_price_asks_market_plus_five_percent(
            self, api, card_id, set_id, foil, expected):
        created = post(api, card_id=card_id, set_id=set_id, foil=foil,
                       selling=True).get_json()['data']['line']
        assert created['sell_price'] == expected

    def test_a_given_price_and_quantity_are_kept(self, api):
        created = post(api, qty=5, selling=True, sell_qty=2,
                       sell_price=12).get_json()['data']['line']
        assert (created['sell_qty'], created['sell_price']) == (2, 12.0)

    def test_not_selling_keeps_a_given_sell_qty_and_adds_no_price(self, api):
        created = post(api, qty=5, sell_qty=2).get_json()['data']['line']
        assert (created['selling'], created['sell_qty'], created['sell_price']) == (False, 2, None)

    def test_more_copies_for_sale_than_owned_is_refused(self, api):
        response = post(api, qty=2, selling=True, sell_qty=3)
        body = response.get_json()
        assert response.status_code == 409
        assert (body['code'], body['params']) == ('insufficient_quantity', {'available': 2})
        assert all_rows() == []

    def test_money_is_rounded_half_up(self, api):
        created = post(api, purchase_price=1.005, selling=True,
                       sell_price=2.675).get_json()['data']['line']
        assert (created['purchase_price'], created['sell_price']) == (1.01, 2.68)


class TestMerge:
    def test_identical_lines_merge_and_add_up(self, api):
        first = post(api, qty=2, condition='NM', purchase_price=8, selling=True,
                     sell_qty=1, sell_price=12).get_json()['data']
        second = post(api, qty=3, condition='NM', purchase_price=8, selling=True,
                      sell_qty=2, sell_price=12)
        assert second.status_code == 201
        data = second.get_json()['data']
        assert data['merged'] is True
        assert data['line']['id'] == first['line']['id']
        assert (data['line']['qty'], data['line']['sell_qty']) == (5, 3)
        assert len(all_rows()) == 1

    @pytest.mark.parametrize('other', [
        {'foil': True}, {'condition': 'EX'}, {'language': 'Spanish'}, {'purchase_price': 9},
        {'selling': True, 'sell_price': 12}, {'card_id': '2'}])
    def test_a_difference_in_the_key_keeps_the_lines_apart(self, api, other):
        post(api, condition='NM', language='English', purchase_price=8)
        base = {'condition': 'NM', 'language': 'English', 'purchase_price': 8}
        response = post(api, **{**base, **other})
        assert response.get_json()['data']['merged'] is False
        assert len(all_rows()) == 2

    def test_no_purchase_price_does_not_merge_with_a_zero_one(self, api):
        post(api)
        assert post(api, purchase_price=0).get_json()['data']['merged'] is False
        assert post(api).get_json()['data']['merged'] is True

    def test_never_merges_with_another_users_line(self, app, api):
        with app.app_context():
            db.session.add(line('1', 4, user='otheruser'))
            db.session.commit()
        assert post(api, condition='NM', language='English').get_json()['data']['merged'] is False
