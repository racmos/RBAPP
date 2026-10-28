"""F3-c S4, S5 (AC3): DELETE /collection/<id> and POST /collection/<id>/split."""
import pytest

from app import db
from tests.collection_write_helpers import BASE, all_rows, card, fetch, line, seed_catalog


@pytest.fixture
def api(app, authenticated_client, make_user):
    make_user('otheruser')
    with app.app_context():
        seed_catalog()
        mine = line('1', 5, purchase=8, selling='Y', sell_qty=4, sell_price=12.5)
        foreign = line('1', 4, user='otheruser')
        db.session.add_all([mine, foreign])
        db.session.commit()
        authenticated_client.mine = mine.rbcol_id
        authenticated_client.foreign = foreign.rbcol_id
    return authenticated_client


class TestDelete:
    def test_deletes_and_returns_the_line(self, api):
        response = api.delete(f'{BASE}/{api.mine}')
        assert response.status_code == 200
        deleted = response.get_json()['data']['deleted']
        assert (deleted['id'], deleted['set_id'], deleted['card_id'], deleted['qty']) == (
            api.mine, 'OGN', '1', 5)
        assert all_rows() == []

    def test_the_answer_can_be_posted_back_to_undo(self, api):
        deleted = api.delete(f'{BASE}/{api.mine}').get_json()['data']['deleted']
        back = api.post(BASE, json=deleted)
        assert back.status_code == 201
        restored = back.get_json()['data']['line']
        for key in ('set_id', 'card_id', 'foil', 'qty', 'condition', 'language', 'purchase_price',
                    'selling', 'sell_qty', 'sell_price'):
            assert restored[key] == deleted[key], key
        assert len(all_rows()) == 1

    def test_another_users_line_is_a_404(self, api):
        assert api.delete(f'{BASE}/{api.foreign}').status_code == 404
        assert fetch(api.foreign) is not None

    def test_missing_line_and_no_session(self, app, api):
        assert api.delete(f'{BASE}/99999').status_code == 404
        assert app.test_client().delete(f'{BASE}/{api.mine}').status_code == 401


def split(api, line_id=None, **body):
    return api.post(f'{BASE}/{line_id or api.mine}/split', json=body)


class TestSplit:
    def test_moves_copies_into_a_new_line_with_overrides(self, api):
        response = split(api, qty=2, condition='EX', language='Spanish')
        assert response.status_code == 200
        data = response.get_json()['data']
        assert data['merged'] is False
        assert (data['source']['qty'], data['source']['id']) == (3, api.mine)
        target = data['target']
        assert (target['qty'], target['condition'], target['language']) == (2, 'EX', 'Spanish')
        assert target['id'] != api.mine
        assert (target['set_id'], target['card_id'], target['purchase_price']) == ('OGN', '1', 8.0)
        assert len(all_rows()) == 2

    def test_source_sell_qty_is_clamped_to_its_new_quantity(self, api):
        data = split(api, qty=3, condition='EX').get_json()['data']
        assert (data['source']['qty'], data['source']['sell_qty']) == (2, 2)

    def test_target_sells_all_its_copies_when_selling(self, api):
        data = split(api, qty=2, condition='EX', selling=True).get_json()['data']
        assert (data['target']['selling'], data['target']['sell_qty']) == (True, 2)

    def test_target_sells_nothing_when_not_selling(self, api):
        data = split(api, qty=2, condition='EX', selling=False).get_json()['data']
        assert (data['target']['selling'], data['target']['sell_qty']) == (False, 0)

    def test_inherits_the_selling_flag_and_price_from_the_source(self, api):
        data = split(api, qty=1, condition='EX').get_json()['data']['target']
        assert (data['selling'], data['sell_price'], data['sell_qty']) == (True, 12.5, 1)

    def test_merges_into_an_identical_existing_line(self, app, api):
        with app.app_context():
            other = line('1', 2, condition='EX', purchase=8, selling='Y', sell_qty=1,
                         sell_price=12.5)
            db.session.add(other)
            db.session.commit()
            other_id = other.rbcol_id
        data = split(api, qty=2, condition='EX').get_json()['data']
        assert data['merged'] is True
        assert data['target']['id'] == other_id
        assert (data['target']['qty'], data['target']['sell_qty']) == (4, 3)
        assert data['source']['qty'] == 3
        assert len(all_rows()) == 2

    def test_at_least_one_copy_stays(self, api):
        response = split(api, qty=5, condition='EX')
        body = response.get_json()
        assert response.status_code == 409
        assert (body['code'], body['params']) == ('insufficient_quantity', {'available': 4})
        assert fetch(api.mine).rbcol_quantity == 5 and len(all_rows()) == 1

    def test_the_largest_split_leaves_exactly_one(self, api):
        data = split(api, qty=4, condition='EX').get_json()['data']
        assert (data['source']['qty'], data['target']['qty']) == (1, 4)

    @pytest.mark.parametrize('body', [{'qty': 0}, {}, {'qty': 2, 'condition': 'XX'},
                                      {'qty': 'a'}, {'qty': 2, 'purchase_price': -1}])
    def test_invalid_bodies_are_a_400(self, api, body):
        response = split(api, **body)
        assert response.status_code == 400 and response.get_json()['code'] == 'validation_error'
        assert fetch(api.mine).rbcol_quantity == 5

    def test_another_users_line_is_a_404(self, api):
        assert split(api, api.foreign, qty=1, condition='EX').status_code == 404
        assert fetch(api.foreign).rbcol_quantity == 4

    def test_without_a_difference_nothing_moves(self, api):
        data = split(api, qty=2).get_json()['data']
        assert data['merged'] is True
        assert data['source']['id'] == data['target']['id'] == api.mine
        assert fetch(api.mine).rbcol_quantity == 5
