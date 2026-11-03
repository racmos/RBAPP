"""F16-a S10 (F16-R7): the existing collection writes keep the location quantities of a line
within its quantity. A drop takes copies in the take order (unlocked locations by position,
then unassigned) and is refused, changing nothing, when only locked locations hold the rest:
`LockedCopies`, a 409 `insufficient_quantity` through the existing API."""
import pytest

from app import db
from app.models import RbCollection, RbCollectionLocation, RbLocation, User
from app.services import collection_write, locations
from tests.collection_write_helpers import BASE, all_rows, card, fetch, line, seed_catalog


@pytest.fixture
def api(app, authenticated_client):
    """testuser: line L of OGN/1 with 5 copies (A, 1st: 2; B, 2nd, locked: 0; C, 3rd: 2;
    unassigned 1) and line M of OGN/2 with 2 unassigned copies."""
    seed_catalog()
    user = User.query.filter_by(username='testuser').one()
    mine = line('1', 5, purchase=8)
    other = line('2', 2)
    db.session.add_all([mine, other])
    db.session.commit()
    a, b, c = (locations.create_location(user, code) for code in ('A', 'B', 'C'))
    locations.assign_copies(user, mine.rbcol_id, a.rbloc_id, 2)
    locations.assign_copies(user, mine.rbcol_id, c.rbloc_id, 2)
    authenticated_client.user = user
    authenticated_client.L, authenticated_client.M = mine.rbcol_id, other.rbcol_id
    authenticated_client.A, authenticated_client.B = a.rbloc_id, b.rbloc_id
    authenticated_client.C = c.rbloc_id
    return authenticated_client


def _held(line_id):
    db.session.expire_all()
    return dict(db.session.query(RbLocation.rbloc_code, RbCollectionLocation.rbcll_qty).join(
        RbLocation, RbLocation.rbloc_id == RbCollectionLocation.rbcll_location_id).filter(
        RbCollectionLocation.rbcll_line_id == line_id).all())


def _lock_two_in_b(api):
    locations.move_copies(api.user, api.L, api.C, api.B, 2)
    locations.set_locked(api.user, api.B, True)


def _refused(response, available):
    assert response.status_code == 409
    body = response.get_json()
    assert (body['code'], body['params']) == ('insufficient_quantity', {'available': available})


class TestEdit:
    def test_a_drop_takes_from_unlocked_locations_in_order_then_unassigned(self, api):
        assert api.patch(f'{BASE}/{api.L}', json={'qty': 2}).status_code == 200
        assert fetch(api.L).rbcol_quantity == 2
        assert _held(api.L) == {'C': 1}
        assert locations.unassigned(fetch(api.L)) == 1

    def test_a_drop_that_only_locked_copies_could_cover_is_refused(self, api):
        _lock_two_in_b(api)
        _refused(api.patch(f'{BASE}/{api.L}', json={'qty': 1, 'condition': 'EX'}), 3)
        row = fetch(api.L)
        assert (row.rbcol_quantity, row.rbcol_condition) == (5, 'NM')
        assert _held(api.L) == {'A': 2, 'B': 2}

    def test_a_drop_down_to_the_locked_copies_is_allowed(self, api):
        _lock_two_in_b(api)
        assert api.patch(f'{BASE}/{api.L}', json={'qty': 2}).status_code == 200
        assert _held(api.L) == {'B': 2}
        assert locations.unassigned(fetch(api.L)) == 0

    def test_a_raise_or_other_fields_keep_the_locations(self, api):
        assert api.patch(f'{BASE}/{api.L}', json={'qty': 9}).status_code == 200
        assert api.patch(f'{BASE}/{api.L}', json={'condition': 'EX'}).status_code == 200
        assert _held(api.L) == {'A': 2, 'C': 2}
        assert locations.unassigned(fetch(api.L)) == 5

    def test_the_service_error_names_the_locked_locations(self, api):
        from app.schemas.validators import CollectionLinePatch
        _lock_two_in_b(api)
        with pytest.raises(collection_write.LockedCopies) as exc:
            collection_write.edit_line(api.user, api.L, CollectionLinePatch(qty=1))
        assert isinstance(exc.value, collection_write.InsufficientQuantity)
        assert exc.value.available == 3
        assert exc.value.locked == [{'location_id': api.B, 'code': 'B', 'qty': 2}]


class TestDelete:
    def test_deleting_a_line_deletes_its_location_quantities(self, api):
        assert api.delete(f'{BASE}/{api.L}').status_code == 200
        assert fetch(api.L) is None
        assert db.session.query(RbCollectionLocation).count() == 0

    def test_a_line_with_locked_copies_cannot_be_deleted(self, api):
        _lock_two_in_b(api)
        _refused(api.delete(f'{BASE}/{api.L}'), 3)
        assert fetch(api.L).rbcol_quantity == 5
        assert _held(api.L) == {'A': 2, 'B': 2}

    def test_bulk_delete_is_all_or_nothing(self, api):
        _lock_two_in_b(api)
        _refused(api.post(f'{BASE}/bulk', json={'ids': [api.L, api.M], 'delete': True}), 3)
        assert [row.rbcol_id for row in all_rows()] == [api.L, api.M]
        assert _held(api.L) == {'A': 2, 'B': 2}
        locations.set_locked(api.user, api.B, False)
        assert api.post(f'{BASE}/bulk', json={'ids': [api.L, api.M],
                                              'delete': True}).status_code == 200
        assert all_rows() == []
        assert db.session.query(RbCollectionLocation).count() == 0


class TestSplit:
    def test_the_split_copies_keep_their_locations_on_the_new_line(self, api):
        response = api.post(f'{BASE}/{api.L}/split', json={'qty': 3, 'condition': 'EX'})
        assert response.status_code == 200
        target = response.get_json()['data']['target']['id']
        assert (fetch(api.L).rbcol_quantity, fetch(target).rbcol_quantity) == (2, 3)
        assert _held(api.L) == {'C': 1}
        assert _held(target) == {'A': 2, 'C': 1}
        assert locations.unassigned(fetch(api.L)) == 1
        assert locations.unassigned(fetch(target)) == 0

    def test_a_split_into_an_existing_line_adds_to_its_locations(self, api):
        twin = line('1', 1, purchase=8, condition='EX')
        db.session.add(twin)
        db.session.commit()
        locations.assign_copies(api.user, twin.rbcol_id, api.A, 1)
        response = api.post(f'{BASE}/{api.L}/split', json={'qty': 2, 'condition': 'EX'})
        assert response.get_json()['data']['merged'] is True
        assert _held(twin.rbcol_id) == {'A': 3}
        assert _held(api.L) == {'C': 2}

    def test_a_split_that_needs_locked_copies_is_refused(self, api):
        _lock_two_in_b(api)
        _refused(api.post(f'{BASE}/{api.L}/split', json={'qty': 4, 'condition': 'EX'}), 3)
        assert len(all_rows()) == 2
        assert fetch(api.L).rbcol_quantity == 5
        assert _held(api.L) == {'A': 2, 'B': 2}


def test_adding_identical_copies_keeps_the_locations(api):
    response = api.post(BASE, json=card('1', qty=2, condition='NM', language='English',
                                        purchase_price=8))
    assert response.get_json()['data']['merged'] is True
    assert fetch(api.L).rbcol_quantity == 7
    assert _held(api.L) == {'A': 2, 'C': 2}


def test_other_lines_are_untouched(api):
    db.session.add(RbCollectionLocation(rbcll_line_id=api.M, rbcll_location_id=api.A,
                                        rbcll_qty=1))
    db.session.commit()
    api.patch(f'{BASE}/{api.L}', json={'qty': 1})
    assert _held(api.M) == {'A': 1}
    assert db.session.get(RbCollection, api.M).rbcol_quantity == 2
