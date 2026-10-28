"""F3-c S6 (AC4): POST /collection/bulk."""
import pytest

from app import db
from tests.collection_write_helpers import BASE, all_rows, fetch, line, seed_catalog

URL = f'{BASE}/bulk'


@pytest.fixture
def api(app, authenticated_client, make_user):
    make_user('otheruser')
    with app.app_context():
        seed_catalog()
        rows = [line('1', 5, purchase=8, selling='Y', sell_qty=2, sell_price=12.5),
                line('2', 3, condition='EX', language='French'),
                line('79', 4, condition='MT')]
        foreign = line('1', 4, user='otheruser')
        db.session.add_all([*rows, foreign])
        db.session.commit()
        authenticated_client.ids = [row.rbcol_id for row in rows]
        authenticated_client.foreign = foreign.rbcol_id
    return authenticated_client


def bulk(api, ids=None, **body):
    return api.post(URL, json={'ids': api.ids if ids is None else ids, **body})


class TestSet:
    @pytest.mark.parametrize('values, column, expected', [
        ({'condition': 'GD'}, 'rbcol_condition', 'GD'),
        ({'condition': None}, 'rbcol_condition', None),
        ({'language': 'German'}, 'rbcol_language', 'German'),
        ({'sell_price': 9.995}, 'rbcol_sell_price', 10.0),
        ({'purchase_price': 2.5}, 'rbcol_purchase_price', 2.5),
    ])
    def test_each_field_reaches_every_line(self, api, values, column, expected):
        response = bulk(api, **{'set': values})
        assert response.status_code == 200 and response.get_json()['data'] == {'updated': 3}
        for row in all_rows():
            value = getattr(row, column)
            assert (float(value) if value is not None and column.endswith('price') else value) \
                == expected

    def test_selling_true_marks_the_lines_and_asks_market_plus_five_percent(self, api):
        bulk(api, **{'set': {'selling': True}})
        first, second, third = all_rows()
        assert [r.rbcol_selling for r in (first, second, third)] == ['Y', 'Y', 'Y']
        assert float(first.rbcol_sell_price) == 12.5            # it had one
        assert float(second.rbcol_sell_price) == 5.25           # market 5 x 1.05
        assert float(third.rbcol_sell_price) == 21.0            # market 20 x 1.05

    def test_selling_false_keeps_quantities(self, api):
        bulk(api, **{'set': {'selling': False}})
        first = all_rows()[0]
        assert (first.rbcol_selling, first.rbcol_sell_qty) == ('N', 2)

    def test_rule_all_sells_every_copy(self, api):
        bulk(api, **{'set': {'sell_qty_rule': 'all'}})
        assert [r.rbcol_sell_qty for r in all_rows()] == [5, 3, 4]

    def test_rule_none_sells_nothing(self, api):
        bulk(api, **{'set': {'sell_qty_rule': 'none'}})
        assert [r.rbcol_sell_qty for r in all_rows()] == [0, 0, 0]

    def test_rule_keep_n_keeps_n_copies(self, api):
        bulk(api, **{'set': {'sell_qty_rule': 'keep_n', 'keep': 3}})
        assert [r.rbcol_sell_qty for r in all_rows()] == [2, 0, 1]

    def test_keep_n_needs_keep(self, api):
        for values in ({'sell_qty_rule': 'keep_n'}, {'sell_qty_rule': 'keep_n', 'keep': 0},
                       {'sell_qty_rule': 'keep_n', 'keep': 10}, {'sell_qty_rule': 'some'}):
            response = bulk(api, **{'set': values})
            assert response.status_code == 400, values
            assert response.get_json()['code'] == 'validation_error'
        assert [r.rbcol_sell_qty for r in all_rows()] == [2, 0, 0]

    def test_several_fields_at_once(self, api):
        bulk(api, **{'set': {'condition': 'NM', 'language': 'English', 'selling': True,
                             'sell_qty_rule': 'all'}})
        for row in all_rows():
            assert (row.rbcol_condition, row.rbcol_language, row.rbcol_selling,
                    row.rbcol_sell_qty) == ('NM', 'English', 'Y', row.rbcol_quantity)

    def test_stamps_the_change_time(self, api, frozen_clock):
        frozen_clock.advance(days=1)
        bulk(api, **{'set': {'condition': 'GD'}})
        assert {r.rbcol_chadat for r in all_rows()} == {frozen_clock()}


class TestDelete:
    def test_deletes_and_returns_the_lines(self, api):
        response = bulk(api, delete=True)
        data = response.get_json()['data']
        assert response.status_code == 200
        assert [d['id'] for d in data['deleted']] == api.ids
        assert {'set_id', 'card_id', 'qty'} <= set(data['deleted'][0])
        assert all_rows() == []
        assert fetch(api.foreign) is not None


class TestAllOrNothing:
    def test_a_foreign_id_is_a_404_and_nothing_changes(self, api):
        response = bulk(api, ids=[*api.ids, api.foreign], **{'set': {'condition': 'PO'}})
        assert response.status_code == 404
        assert {r.rbcol_condition for r in all_rows()} == {'NM', 'EX', 'MT'}
        assert fetch(api.foreign).rbcol_condition == 'NM'

    def test_a_missing_id_deletes_nothing(self, api):
        assert bulk(api, ids=[*api.ids, 99999], delete=True).status_code == 404
        assert len(all_rows()) == 3

    def test_repeated_ids_count_once(self, api):
        response = bulk(api, ids=[api.ids[0], api.ids[0]], **{'set': {'condition': 'PO'}})
        assert response.get_json()['data'] == {'updated': 1}


class TestValidation:
    @pytest.mark.parametrize('body', [
        {}, {'ids': []}, {'ids': [0]}, {'ids': ['a']}, {'ids': [1, 2, 3]},
        {'ids': [1], 'set': {}}, {'ids': [1], 'set': {'condition': 'XX'}},
        {'ids': [1], 'delete': False}, {'ids': [1], 'delete': 'yes'},
        {'ids': [1], 'set': {'condition': 'GD'}, 'delete': True}])
    def test_bad_bodies_are_a_400(self, api, body):
        response = api.post(URL, json=body)
        assert response.status_code == 400 and response.get_json()['code'] == 'validation_error'

    def test_the_limit_is_1000_ids(self, api):
        assert api.post(URL, json={'ids': list(range(1, 1002)),
                                   'set': {'condition': 'GD'}}).status_code == 400
        too_many_but_valid = api.post(URL, json={'ids': list(range(1, 1001)),
                                                 'set': {'condition': 'GD'}})
        assert too_many_but_valid.status_code == 404      # 1000 ids are fine, they are not mine

    def test_requires_a_session(self, app):
        assert app.test_client().post(URL, json={'ids': [1], 'delete': True}).status_code == 401
