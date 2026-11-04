"""F16-x: POST /collection/bulk `set.location_id` (bulk location of several lines)."""
import pytest

from app import db
from app.models import RbCollectionLocation, RbLocation, User
from app.services import locations
from tests.collection_write_helpers import BASE, all_rows, line, seed_catalog

URL = f'{BASE}/bulk'
NOT_FOUND = {'success': False, 'error': 'Not Found',
             'message': 'The requested resource was not found'}


@pytest.fixture
def api(authenticated_client, make_user):
    """Three lines of testuser: L1 (4 copies: 2 in A, 1 in B, 1 unassigned), L2 (3 copies in C),
    L3 (2 copies, none placed); and one line of otheruser."""
    make_user('otheruser')
    seed_catalog()
    rows = [line('1', 4), line('2', 3, condition='EX', language='French'),
            line('79', 2, condition='MT')]
    foreign = line('1', 5, user='otheruser')
    db.session.add_all([*rows, foreign])
    db.session.commit()
    me = User.query.filter_by(username='testuser').one()
    them = User.query.filter_by(username='otheruser').one()
    a, b, c, d = (locations.create_location(me, code) for code in ('A', 'B', 'C', 'D'))
    locations.assign_copies(me, rows[0].rbcol_id, a.rbloc_id, 2)
    locations.assign_copies(me, rows[0].rbcol_id, b.rbloc_id, 1)
    locations.assign_copies(me, rows[1].rbcol_id, c.rbloc_id, 3)
    theirs = locations.create_location(them, 'THEIRS')
    locations.assign_copies(them, foreign.rbcol_id, theirs.rbloc_id, 2)
    authenticated_client.me = me
    authenticated_client.ids = [row.rbcol_id for row in rows]
    authenticated_client.foreign = foreign.rbcol_id
    authenticated_client.loc = {code: loc.rbloc_id for code, loc in
                                (('A', a), ('B', b), ('C', c), ('D', d),
                                 ('THEIRS', theirs))}
    return authenticated_client


def bulk(api, ids=None, **values):
    return api.post(URL, json={'ids': api.ids if ids is None else ids, 'set': values})


def held():
    """{line id: {location code: qty}} of every line that has copies in a location."""
    db.session.expire_all()
    found = {}
    for line_id, code, qty in db.session.query(
            RbCollectionLocation.rbcll_line_id, RbLocation.rbloc_code,
            RbCollectionLocation.rbcll_qty).join(
            RbLocation, RbLocation.rbloc_id == RbCollectionLocation.rbcll_location_id).all():
        found.setdefault(line_id, {})[code] = qty
    return found


def snapshot():
    """Every field of every line plus where the copies are."""
    rows = [(r.rbcol_id, r.rbcol_quantity, r.rbcol_condition, r.rbcol_language,
             r.rbcol_selling, r.rbcol_sell_qty, r.rbcol_sell_price, r.rbcol_purchase_price,
             r.rbcol_chadat) for r in all_rows() + all_rows('otheruser')]
    return rows, held()


def _start(api):
    l1, l2, _ = api.ids
    return {l1: {'A': 2, 'B': 1}, l2: {'C': 3}, api.foreign: {'THEIRS': 2}}


class TestKeep:
    def test_without_location_id_every_line_keeps_its_locations(self, api):
        """The owner's case: changing the language of lines in different places moves nothing."""
        response = bulk(api, language='German')
        assert response.status_code == 200, response.get_json()
        assert response.get_json()['data'] == {'updated': 3}
        assert [r.rbcol_language for r in all_rows()] == ['German'] * 3
        assert held() == _start(api)

    def test_other_fields_alone_keep_locations(self, api):
        assert bulk(api, condition='GD', selling=True, sell_qty_rule='all',
                    purchase_price=1).status_code == 200
        assert held() == _start(api)


class TestPlace:
    def test_a_location_takes_every_copy_of_every_line(self, api):
        l1, l2, l3 = api.ids
        response = bulk(api, location_id=api.loc['D'])
        assert response.status_code == 200, response.get_json()
        assert response.get_json()['data'] == {'updated': 3}
        assert held() == {l1: {'D': 4}, l2: {'D': 3}, l3: {'D': 2},
                          api.foreign: {'THEIRS': 2}}
        assert [r.rbcol_quantity for r in all_rows()] == [4, 3, 2]

    def test_a_location_one_of_the_lines_already_uses(self, api):
        l1, l2, l3 = api.ids
        assert bulk(api, location_id=api.loc['A']).status_code == 200
        assert held() == {l1: {'A': 4}, l2: {'A': 3}, l3: {'A': 2},
                          api.foreign: {'THEIRS': 2}}

    def test_only_the_selected_lines_move(self, api):
        l1, l2, l3 = api.ids
        assert bulk(api, ids=[l1, l3], location_id=api.loc['C']).status_code == 200
        assert held() == {l1: {'C': 4}, l2: {'C': 3}, l3: {'C': 2},
                          api.foreign: {'THEIRS': 2}}
        assert bulk(api, ids=[l3], location_id=api.loc['B']).status_code == 200
        assert held()[l2] == {'C': 3} and held()[l1] == {'C': 4} and held()[l3] == {'B': 2}

    def test_null_makes_every_copy_unassigned(self, api):
        l1, l2, l3 = api.ids
        response = bulk(api, location_id=None)
        assert response.status_code == 200, response.get_json()
        assert response.get_json()['data'] == {'updated': 3}
        assert held() == {api.foreign: {'THEIRS': 2}}
        assert [r.rbcol_quantity for r in all_rows()] == [4, 3, 2]

    def test_combined_with_the_language_in_one_request(self, api):
        l1, l2, l3 = api.ids
        assert bulk(api, ids=[l1, l2], language='Italian',
                    location_id=api.loc['B']).status_code == 200
        assert [r.rbcol_language for r in all_rows()] == ['Italian', 'Italian', 'English']
        assert held() == {l1: {'B': 4}, l2: {'B': 3}, api.foreign: {'THEIRS': 2}}

    @pytest.mark.parametrize('value', [0, -1, 'A', 1.5, True])
    def test_a_bad_location_id_is_a_400_and_nothing_changes(self, api, value):
        before = snapshot()
        response = bulk(api, location_id=value)
        assert response.status_code == 400
        assert response.get_json()['code'] == 'validation_error'
        assert snapshot() == before


class TestRefused:
    def test_a_foreign_or_unknown_location_is_a_404_and_nothing_changes(self, api):
        before = snapshot()
        for location_id in (api.loc['THEIRS'], 9999):
            response = bulk(api, language='German', location_id=location_id)
            assert response.status_code == 404 and response.get_json() == NOT_FOUND
        assert snapshot() == before

    def test_a_locked_target_is_a_409_and_nothing_changes(self, api):
        locations.set_locked(api.me, api.loc['D'], True)
        before = snapshot()
        response = bulk(api, language='German', location_id=api.loc['D'])
        assert response.status_code == 409
        body = response.get_json()
        assert body['code'] == 'location_locked'
        assert body['params'] == {'codes': 'D'}
        assert snapshot() == before

    def test_copies_in_a_locked_location_cannot_move_and_nothing_changes(self, api):
        locations.set_locked(api.me, api.loc['B'], True)
        locations.set_locked(api.me, api.loc['C'], True)
        before = snapshot()
        for value in (api.loc['D'], None):
            response = bulk(api, condition='GD', location_id=value)
            assert response.status_code == 409
            body = response.get_json()
            assert body['code'] == 'location_locked'
            assert body['params'] == {'codes': 'B, C'}     # the user's order
            assert snapshot() == before

    def test_locked_copies_do_not_block_a_change_without_location_id(self, api):
        locations.set_locked(api.me, api.loc['A'], True)
        assert bulk(api, language='German').status_code == 200
        assert held() == _start(api)

    def test_a_line_of_another_user_is_a_404_and_nothing_changes(self, api):
        before = snapshot()
        response = bulk(api, ids=[*api.ids, api.foreign], location_id=api.loc['D'])
        assert response.status_code == 404 and response.get_json() == NOT_FOUND
        assert snapshot() == before


class TestPreserved:
    def test_location_id_alone_is_a_non_empty_set(self, api):
        """`null` is an explicit value: it counts as a change for "exactly one of set or
        delete"."""
        assert bulk(api, location_id=None).status_code == 200
        response = api.post(URL, json={'ids': api.ids, 'set': {'location_id': None},
                                       'delete': True})
        assert response.status_code == 400

    def test_an_empty_set_is_still_a_400(self, api):
        before = snapshot()
        response = api.post(URL, json={'ids': api.ids, 'set': {}})
        assert response.status_code == 400
        assert response.get_json()['code'] == 'validation_error'
        assert snapshot() == before
