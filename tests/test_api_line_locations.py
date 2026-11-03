"""F16-b S7-S9: GET/PUT /collection/<line_id>/locations and POST .../locations/move."""
import pytest

from app import db
from app.models import RbCollection, RbCollectionLocation, RbLocation, User
from app.services import locations
from tests.collection_read_helpers import line, seed_catalog

BASE = '/riftbound/api/v1/collection'
NOT_FOUND = {'success': False, 'error': 'Not Found',
             'message': 'The requested resource was not found'}


@pytest.fixture
def api(app, authenticated_client, make_user):
    make_user('otheruser')
    seed_catalog()
    return authenticated_client


@pytest.fixture
def me(api):
    return User.query.filter_by(username='testuser').one()


@pytest.fixture
def them(api):
    return User.query.filter_by(username='otheruser').one()


def _line(card='1', qty=6, user='testuser'):
    row = line(card, qty, user=user)
    db.session.add(row)
    db.session.commit()
    return row.rbcol_id


def _held(line_id):
    """{location code: qty} of a line."""
    db.session.expire_all()
    return dict(db.session.query(RbLocation.rbloc_code, RbCollectionLocation.rbcll_qty).join(
        RbLocation, RbLocation.rbloc_id == RbCollectionLocation.rbcll_location_id).filter(
        RbCollectionLocation.rbcll_line_id == line_id).all())


def _data(resp, status=200):
    assert resp.status_code == status, resp.get_json()
    body = resp.get_json()
    assert body['success'] is True
    return body['data']


def _error(resp, status, code):
    assert resp.status_code == status, resp.get_json()
    body = resp.get_json()
    assert body['success'] is False and body['code'] == code
    return body


def _url(line_id, tail=''):
    return f'{BASE}/{line_id}/locations{tail}'


class TestGet:
    def test_the_lines_locations_in_the_users_order_with_unassigned_and_total(self, api, me):
        line_id = _line(qty=6)
        a = locations.create_location(me, 'A', 'first')
        b = locations.create_location(me, 'B')
        locations.assign_copies(me, line_id, a.rbloc_id, 1)
        locations.assign_copies(me, line_id, b.rbloc_id, 2)
        locations.reorder_locations(me, [b.rbloc_id, a.rbloc_id])
        locations.set_locked(me, a.rbloc_id, True)
        data = _data(api.get(_url(line_id)))
        assert list(data) == ['locations', 'unassigned', 'total']
        assert data == {
            'locations': [
                {'location_id': b.rbloc_id, 'code': 'B', 'description': None, 'locked': False,
                 'qty': 2},
                {'location_id': a.rbloc_id, 'code': 'A', 'description': 'first',
                 'locked': True, 'qty': 1}],
            'unassigned': 3, 'total': 6}

    def test_a_line_in_no_location(self, api):
        assert _data(api.get(_url(_line(qty=2)))) == {'locations': [], 'unassigned': 2,
                                                      'total': 2}

    def test_a_foreign_or_unknown_line_is_a_404(self, api):
        for line_id in (_line(user='otheruser'), 9999):
            resp = api.get(_url(line_id))
            assert resp.status_code == 404 and resp.get_json() == NOT_FOUND


class TestPut:
    def test_replaces_the_assignment(self, api, me):
        line_id = _line(qty=6)
        a, b, c = (locations.create_location(me, code) for code in 'ABC')
        locations.assign_copies(me, line_id, a.rbloc_id, 2)
        locations.assign_copies(me, line_id, b.rbloc_id, 1)
        data = _data(api.put(_url(line_id), json={'assignments': [
            {'location_id': b.rbloc_id, 'qty': 3}, {'location_id': c.rbloc_id, 'qty': 2}]}))
        assert _held(line_id) == {'B': 3, 'C': 2}
        assert [(row['code'], row['qty']) for row in data['locations']] == [('B', 3), ('C', 2)]
        assert (data['unassigned'], data['total']) == (1, 6)
        assert db.session.get(RbCollection, line_id).rbcol_quantity == 6

    def test_an_empty_list_frees_every_copy(self, api, me):
        line_id = _line(qty=4)
        a = locations.create_location(me, 'A')
        locations.assign_copies(me, line_id, a.rbloc_id, 4)
        data = _data(api.put(_url(line_id), json={'assignments': []}))
        assert data == {'locations': [], 'unassigned': 4, 'total': 4}
        assert _held(line_id) == {}

    def test_the_whole_quantity_can_be_placed(self, api, me):
        line_id = _line(qty=4)
        a = locations.create_location(me, 'A')
        _data(api.put(_url(line_id), json={'assignments': [{'location_id': a.rbloc_id,
                                                            'qty': 4}]}))
        assert _held(line_id) == {'A': 4}

    def test_over_the_line_quantity_is_a_409_and_nothing_changes(self, api, me):
        line_id = _line(qty=4)
        a, b = locations.create_location(me, 'A'), locations.create_location(me, 'B')
        locations.assign_copies(me, line_id, a.rbloc_id, 1)
        body = _error(api.put(_url(line_id), json={'assignments': [
            {'location_id': a.rbloc_id, 'qty': 3}, {'location_id': b.rbloc_id, 'qty': 2}]}),
            409, 'location_over_quantity')
        assert body['params'] == {'max': 4, 'requested': 5}
        assert body['error'] == 'Conflict'
        assert _held(line_id) == {'A': 1}

    def test_a_locked_location_cannot_change_but_can_be_sent_unchanged(self, api, me):
        line_id = _line(qty=6)
        a, b = locations.create_location(me, 'A'), locations.create_location(me, 'B')
        locations.assign_copies(me, line_id, a.rbloc_id, 2)
        locations.set_locked(me, a.rbloc_id, True)
        for assignments in (
                [{'location_id': a.rbloc_id, 'qty': 3}],                   # raise
                [{'location_id': b.rbloc_id, 'qty': 1}],                   # drop
                [{'location_id': a.rbloc_id, 'qty': 3},
                 {'location_id': b.rbloc_id, 'qty': 9}]):                  # before over-qty
            _error(api.put(_url(line_id), json={'assignments': assignments}), 409,
                   'location_locked')
            assert _held(line_id) == {'A': 2}
        _data(api.put(_url(line_id), json={'assignments': [
            {'location_id': a.rbloc_id, 'qty': 2}, {'location_id': b.rbloc_id, 'qty': 3}]}))
        assert _held(line_id) == {'A': 2, 'B': 3}

    def test_adding_a_locked_location_is_a_409(self, api, me):
        line_id = _line(qty=6)
        a = locations.create_location(me, 'A')
        locations.set_locked(me, a.rbloc_id, True)
        _error(api.put(_url(line_id), json={'assignments': [
            {'location_id': a.rbloc_id, 'qty': 1}]}), 409, 'location_locked')
        assert _held(line_id) == {}

    def test_foreign_lines_and_locations_are_a_404(self, api, me, them):
        mine = _line(qty=6)
        a = locations.create_location(me, 'A')
        theirs = locations.create_location(them, 'T')
        cases = [(_line(user='otheruser'), a.rbloc_id), (9999, a.rbloc_id),
                 (mine, theirs.rbloc_id), (mine, 9999)]
        for line_id, location_id in cases:
            resp = api.put(_url(line_id), json={'assignments': [
                {'location_id': location_id, 'qty': 1}]})
            assert resp.status_code == 404 and resp.get_json() == NOT_FOUND
        assert _held(mine) == {}

    @pytest.mark.parametrize('body', [
        {}, {'assignments': 'x'}, {'assignments': [{'location_id': 1}]},
        {'assignments': [{'location_id': 1, 'qty': 0}]},
        {'assignments': [{'location_id': 1, 'qty': '2'}]},
        {'assignments': [{'location_id': 1, 'qty': 1}, {'location_id': 1, 'qty': 2}]},
    ])
    def test_a_malformed_body_is_a_400(self, api, me, body):
        line_id = _line(qty=6)
        locations.create_location(me, 'A')
        _error(api.put(_url(line_id), json=body), 400, 'validation_error')
        assert _held(line_id) == {}


class TestMove:
    @pytest.fixture
    def placed(self, me):
        line_id = _line(qty=6)
        a, b = locations.create_location(me, 'A'), locations.create_location(me, 'B')
        locations.assign_copies(me, line_id, a.rbloc_id, 3)
        return line_id, a.rbloc_id, b.rbloc_id

    def _move(self, api, line_id, source, target, qty):
        return api.post(_url(line_id, '/move'), json={
            'from_location_id': source, 'to_location_id': target, 'qty': qty})

    def test_between_locations_returns_the_line_locations(self, api, placed):
        line_id, a, b = placed
        data = _data(self._move(api, line_id, a, b, 2))
        assert _held(line_id) == {'A': 1, 'B': 2}
        assert [(row['code'], row['qty']) for row in data['locations']] == [('A', 1), ('B', 2)]
        assert (data['unassigned'], data['total']) == (3, 6)

    def test_from_and_to_unassigned(self, api, placed):
        line_id, a, b = placed
        _data(self._move(api, line_id, None, b, 3))
        assert _held(line_id) == {'A': 3, 'B': 3}
        _data(self._move(api, line_id, a, None, 3))
        assert _held(line_id) == {'B': 3}

    def test_more_than_the_unassigned_copies_is_location_over_quantity(self, api, placed):
        line_id, _, b = placed
        body = _error(self._move(api, line_id, None, b, 4), 409, 'location_over_quantity')
        assert body['params'] == {'max': 3, 'requested': 4}
        assert _held(line_id) == {'A': 3}

    def test_more_than_the_source_holds_is_insufficient_quantity(self, api, placed):
        line_id, a, b = placed
        body = _error(self._move(api, line_id, a, b, 4), 409, 'insufficient_quantity')
        assert body['params'] == {'available': 3}
        assert _held(line_id) == {'A': 3}

    def test_a_locked_side_is_a_409(self, api, me, placed):
        line_id, a, b = placed
        locations.set_locked(me, b, True)
        _error(self._move(api, line_id, a, b, 1), 409, 'location_locked')
        locations.set_locked(me, b, False)
        locations.set_locked(me, a, True)
        _error(self._move(api, line_id, a, None, 1), 409, 'location_locked')
        assert _held(line_id) == {'A': 3}

    def test_foreign_ids_are_a_404(self, api, them, placed):
        line_id, a, _ = placed
        theirs = locations.create_location(them, 'T')
        for args in ((_line(user='otheruser'), None, a), (line_id, a, theirs.rbloc_id),
                     (line_id, None, 9999)):
            resp = self._move(api, *args, 1)
            assert resp.status_code == 404 and resp.get_json() == NOT_FOUND
        assert _held(line_id) == {'A': 3}

    @pytest.mark.parametrize('body', [
        {'from_location_id': None, 'to_location_id': None, 'qty': 1},
        {'to_location_id': 1, 'qty': 0},
        {'to_location_id': 1},
        {'from_location_id': 1, 'to_location_id': 1, 'qty': 1},
        {'to_location_id': 'x', 'qty': 1},
    ])
    def test_a_malformed_body_is_a_400(self, api, placed, body):
        line_id = placed[0]
        _error(api.post(_url(line_id, '/move'), json=body), 400, 'validation_error')
        assert _held(line_id) == {'A': 3}
