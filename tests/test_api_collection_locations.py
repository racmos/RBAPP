"""F16-b S10-S12: GET /collection lines carry their locations (additive), the `location`
filter, and the statement bound with locations."""
import pytest
from sqlalchemy import event

from app import db
from app.models import RbCard, RbCollection, User
from app.services import locations
from tests.collection_read_helpers import URL, line, seed_all

LINE_KEYS = ['id', 'foil', 'qty', 'condition', 'language', 'purchase_price', 'selling',
             'sell_qty', 'sell_price', 'updated_at', 'market', 'value', 'pl_abs', 'pl_pct']


@pytest.fixture
def api(app, authenticated_client, make_user):
    make_user('otheruser')
    seed_all(app)
    return authenticated_client


@pytest.fixture
def me(api):
    return User.query.filter_by(username='testuser').one()


def _ids(card, set_id='OGN', foil='N'):
    return [row.rbcol_id for row in RbCollection.query.filter_by(
        rbcol_user='testuser', rbcol_rbset_id=set_id, rbcol_rbcar_id=card, rbcol_foil=foil)
        .order_by(RbCollection.rbcol_id)]


def get(api, **params):
    response = api.get(URL, query_string=params)
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()


def groups(body):
    return {item['key']: item for item in body['data']['items']}


class TestLineLocations:
    def test_lines_append_locations_locations_more_and_unassigned(self, api):
        lines = groups(get(api))['OGN-1:N']['lines']
        assert list(lines[0]) == LINE_KEYS + ['locations', 'locations_more', 'unassigned']
        assert [(l['locations'], l['locations_more'], l['unassigned']) for l in lines] == [
            ([], 0, 4), ([], 0, 2)]

    def test_a_group_keeps_its_contract_keys(self, api, me):
        locations.assign_copies(me, _ids('1')[0], locations.create_location(me, 'A').rbloc_id, 1)
        assert list(groups(get(api))['OGN-1:N']) == [
            'key', 'card', 'foil', 'qty', 'sell_qty', 'value', 'lines', 'keep_playset',
            'playset_short', 'kept']

    def test_the_first_five_in_the_users_order_and_the_count_of_the_rest(self, api, me):
        line_id = _ids('79')[0]
        db.session.get(RbCollection, line_id).rbcol_quantity = 9
        db.session.commit()
        made = [locations.create_location(me, f'L{n}', f'place {n}') for n in range(1, 8)]
        for loc in made:
            locations.assign_copies(me, line_id, loc.rbloc_id, 1)
        locations.reorder_locations(me, [loc.rbloc_id for loc in reversed(made)])
        locations.set_locked(me, made[6].rbloc_id, True)
        [only] = groups(get(api))['OGN-79:N']['lines']
        assert only['locations'] == [
            {'location_id': loc.rbloc_id, 'code': loc.rbloc_code,
             'description': loc.rbloc_description, 'qty': 1}
            for loc in reversed(made[2:])]
        assert (only['locations_more'], only['unassigned'], only['qty']) == (2, 2, 9)

    def test_quantities_per_location(self, api, me):
        first, second = _ids('1')
        a, b = locations.create_location(me, 'A', 'Binder'), locations.create_location(me, 'B')
        locations.assign_copies(me, first, b.rbloc_id, 3)
        locations.assign_copies(me, first, a.rbloc_id, 1)
        locations.assign_copies(me, second, b.rbloc_id, 2)
        lines = groups(get(api))['OGN-1:N']['lines']
        assert lines[0]['locations'] == [
            {'location_id': a.rbloc_id, 'code': 'A', 'description': 'Binder', 'qty': 1},
            {'location_id': b.rbloc_id, 'code': 'B', 'description': None, 'qty': 3}]
        assert (lines[0]['unassigned'], lines[1]['unassigned']) == (0, 0)

    def test_other_users_locations_never_appear(self, api):
        theirs = User.query.filter_by(username='otheruser').one()
        their_line = RbCollection.query.filter_by(rbcol_user='otheruser').one().rbcol_id
        locations.assign_copies(theirs, their_line,
                                locations.create_location(theirs, 'T').rbloc_id, 5)
        body = get(api)
        assert all(l['locations'] == [] for g in body['data']['items'] for l in g['lines'])

    def test_write_responses_keep_the_collection_line_shape(self, api, me):
        response = api.post(URL, json={'set_id': 'OGN', 'card_id': '2', 'foil': False, 'qty': 1})
        assert response.status_code == 201
        assert set(response.get_json()['data']['line']) == {*LINE_KEYS, 'set_id', 'card_id'}


class TestLocationFilter:
    @pytest.fixture
    def placed(self, me):
        a, b = locations.create_location(me, 'Box-A'), locations.create_location(me, 'B')
        locations.assign_copies(me, _ids('1')[1], a.rbloc_id, 1)     # L2 (2 copies, LP)
        locations.assign_copies(me, _ids('10', 'SFD')[0], b.rbloc_id, 2)
        return a, b

    def test_keeps_the_lines_with_copies_in_the_location_ignoring_case(self, api, placed):
        body = get(api, location='box-a')
        assert list(groups(body)) == ['OGN-1:N']
        [only] = body['data']['items'][0]['lines']
        assert (only['condition'], only['qty']) == ('LP', 2)
        assert body['meta']['totals']['qty'] == 2
        assert body['meta']['total_groups'] == 1

    def test_repeated_codes_are_any_of_them(self, api, placed):
        assert list(groups(get(api, location=['BOX-A', 'b']))) == ['OGN-1:N', 'SFD-10:N']

    def test_combines_with_the_other_filters(self, api, placed):
        assert list(groups(get(api, location=['BOX-A', 'B'], set='SFD'))) == ['SFD-10:N']
        facets = get(api, location='B')['meta']['facets']
        assert facets['set'] == {'SFD': 1}

    def test_an_unknown_code_matches_nothing(self, api, placed):
        body = get(api, location='NOPE')
        assert body['data']['items'] == [] and body['meta']['totals']['qty'] == 0

    def test_more_than_fifty_codes_is_a_400(self, api):
        response = api.get(URL, query_string={'location': [f'C{n}' for n in range(51)]})
        assert response.status_code == 400
        assert response.get_json()['code'] == 'validation_error'

    def test_the_export_takes_the_filter_too(self, api, placed):
        response = api.get(f'{URL}/export', query_string={'location': 'b'})
        assert response.status_code == 200
        assert response.headers['X-Rows-Exported'] == '1'


class TestStatementBound:
    def count(self, api, **params):
        statements = []

        def listener(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        event.listen(db.engine, 'before_cursor_execute', listener)
        try:
            response = api.get(URL, query_string={'sort': 'value', 'dir': 'desc', **params})
            assert response.status_code == 200
        finally:
            event.remove(db.engine, 'before_cursor_execute', listener)
        return len(statements)

    def test_at_most_ten_statements_with_locations_whatever_the_size(self, app, api, me):
        self.count(api)   # warm-up
        small = self.count(api)
        made = [locations.create_location(me, f'L{n}') for n in range(6)]
        for number in range(100, 140):
            db.session.add(RbCard(rbcar_rbset_id='OGN', rbcar_id=str(number),
                                  rbcar_name=f'Filler {number}', rbcar_type='Unit',
                                  rbcar_rarity='Common'))
            db.session.add(line(str(number), 8))
        db.session.commit()
        for row in RbCollection.query.filter_by(rbcol_user='testuser').filter(
                RbCollection.rbcol_quantity == 8):
            for loc in made:
                locations.assign_copies(me, row.rbcol_id, loc.rbloc_id, 1)
        self.count(api)   # the seeding commits expired the signed-in user: load it again
        large = self.count(api)
        filtered = self.count(api, location=['L1', 'L2'])
        assert small <= 10 and large <= 10 and filtered <= 10
        assert small == large == filtered
