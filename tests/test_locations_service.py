"""F16-a S3-S9: `app/services/locations.py`: location CRUD, order, lock, suggested codes,
copies per location and the take-in-order function."""
from datetime import datetime

import pytest

from app import db
from app.models import RbCollection, RbCollectionLocation, RbLocation
from app.services import locations
from app.services.locations import Move, Want
from tests.collection_read_helpers import line, seed_catalog


@pytest.fixture
def ana(app, make_user, frozen_clock):
    make_user('bo')
    seed_catalog()
    return make_user('ana')


@pytest.fixture
def bo(ana):
    from app.models import User
    return User.query.filter_by(username='bo').one()


def _line(card='1', qty=6, user='ana', **kw):
    row = line(card, qty, user=user, **kw)
    db.session.add(row)
    db.session.commit()
    return row.rbcol_id


def _locations(user='ana'):
    db.session.expire_all()
    return [(loc.rbloc_code, loc.rbloc_description, loc.rbloc_position, loc.rbloc_locked)
            for loc in RbLocation.query.filter_by(rbloc_user=user)
            .order_by(RbLocation.rbloc_position)]


def _held(line_id):
    """{location code: qty} of a line."""
    db.session.expire_all()
    found = db.session.query(RbLocation.rbloc_code, RbCollectionLocation.rbcll_qty).join(
        RbLocation, RbLocation.rbloc_id == RbCollectionLocation.rbcll_location_id).filter(
        RbCollectionLocation.rbcll_line_id == line_id).all()
    return dict(found)


def _quantity(line_id):
    db.session.expire_all()
    return db.session.get(RbCollection, line_id).rbcol_quantity


# --- S3 create, update ---------------------------------------------------------------------

class TestCreate:
    def test_new_locations_go_last_with_the_next_position(self, ana, frozen_clock):
        first = locations.create_location(ana, 'B001-F001-P0001', 'Binder 1')
        locations.create_location(ana, 'POOL')
        assert _locations() == [('B001-F001-P0001', 'Binder 1', 1, False),
                                ('POOL', None, 2, False)]
        assert first.rbloc_updated_at == frozen_clock.now
        assert first.rbloc_deck_id is None

    def test_the_code_is_unique_per_owner_ignoring_case(self, ana, bo):
        locations.create_location(ana, 'Box-1')
        with pytest.raises(locations.DuplicateCode):
            locations.create_location(ana, 'BOX-1', 'again')
        locations.create_location(bo, 'box-1')
        assert _locations() == [('Box-1', None, 1, False)]
        assert _locations('bo') == [('box-1', None, 1, False)]

    @pytest.mark.parametrize('code', ['', 'a b', 'ab_c', 'caja/1', 'ñu', 'x' * 33, None])
    def test_a_code_outside_the_rules_is_refused(self, ana, code):
        with pytest.raises(locations.InvalidCode):
            locations.create_location(ana, code)
        assert _locations() == []

    def test_a_description_over_200_characters_is_refused(self, ana):
        locations.create_location(ana, 'A', 'x' * 200)
        with pytest.raises(locations.InvalidDescription):
            locations.create_location(ana, 'B', 'x' * 201)
        assert [code for code, *_ in _locations()] == ['A']

    def test_an_empty_description_is_stored_as_none(self, ana):
        locations.create_location(ana, 'A', '')
        assert _locations() == [('A', None, 1, False)]


class TestUpdate:
    def test_code_and_description_change(self, ana, frozen_clock):
        loc = locations.create_location(ana, 'A', 'old')
        frozen_clock.advance(minutes=5)
        locations.update_location(ana, loc.rbloc_id, code='a', description='new')
        assert _locations() == [('a', 'new', 1, False)]
        assert db.session.get(RbLocation, loc.rbloc_id).rbloc_updated_at == frozen_clock.now

    def test_only_the_sent_fields_change(self, ana):
        loc = locations.create_location(ana, 'A', 'keep')
        locations.update_location(ana, loc.rbloc_id, code='B')
        locations.update_location(ana, loc.rbloc_id, description=None)
        assert _locations() == [('B', None, 1, False)]

    def test_renaming_to_another_locations_code_is_refused(self, ana):
        locations.create_location(ana, 'A')
        loc = locations.create_location(ana, 'B')
        with pytest.raises(locations.DuplicateCode):
            locations.update_location(ana, loc.rbloc_id, code='a')
        with pytest.raises(locations.InvalidCode):
            locations.update_location(ana, loc.rbloc_id, code='a b')
        assert [code for code, *_ in _locations()] == ['A', 'B']

    def test_a_locked_location_can_be_renamed(self, ana):
        loc = locations.create_location(ana, 'A')
        locations.set_locked(ana, loc.rbloc_id, True)
        locations.update_location(ana, loc.rbloc_id, code='Z', description='still locked')
        assert _locations() == [('Z', 'still locked', 1, True)]

    def test_another_users_location_is_not_found(self, ana, bo):
        loc = locations.create_location(bo, 'A')
        for call in (lambda: locations.update_location(ana, loc.rbloc_id, code='B'),
                     lambda: locations.delete_location(ana, loc.rbloc_id),
                     lambda: locations.set_locked(ana, loc.rbloc_id, True),
                     lambda: locations.update_location(ana, 9999, code='B')):
            with pytest.raises(locations.LocationNotFound):
                call()
        assert _locations('bo') == [('A', None, 1, False)]


# --- S4 delete -----------------------------------------------------------------------------

class TestDelete:
    def test_an_empty_location_is_deleted_and_the_order_closes_up(self, ana):
        locs = [locations.create_location(ana, code) for code in ('A', 'B', 'C')]
        assert locations.delete_location(ana, locs[1].rbloc_id) == 0
        assert _locations() == [('A', None, 1, False), ('C', None, 2, False)]

    def test_its_copies_go_back_to_unassigned(self, ana):
        line_id = _line(qty=5)
        loc = locations.create_location(ana, 'A')
        locations.assign_copies(ana, line_id, loc.rbloc_id, 3)
        assert locations.delete_location(ana, loc.rbloc_id) == 3
        assert _held(line_id) == {}
        assert _quantity(line_id) == 5
        assert locations.unassigned(db.session.get(RbCollection, line_id)) == 5

    def test_a_locked_deck_location_cannot_be_deleted(self, ana):
        line_id = _line(qty=2)
        loc = locations.create_location(ana, 'DECK-001')
        locations.assign_copies(ana, line_id, loc.rbloc_id, 2)
        loc.rbloc_deck_id = 42
        db.session.commit()
        locations.set_locked(ana, loc.rbloc_id, True)
        with pytest.raises(locations.LocationLocked):
            locations.delete_location(ana, loc.rbloc_id)
        assert _locations() == [('DECK-001', None, 1, True)]
        assert _held(line_id) == {'DECK-001': 2}
        locations.set_locked(ana, loc.rbloc_id, False)
        assert locations.delete_location(ana, loc.rbloc_id) == 2
        assert _locations() == []

    def test_a_locked_ordinary_location_can_be_deleted(self, ana):
        loc = locations.create_location(ana, 'A')
        locations.set_locked(ana, loc.rbloc_id, True)
        locations.delete_location(ana, loc.rbloc_id)
        assert _locations() == []


# --- S5 order ------------------------------------------------------------------------------

class TestReorder:
    def test_the_full_list_sets_the_order(self, ana, frozen_clock):
        a, b, c = (locations.create_location(ana, code) for code in ('A', 'B', 'C'))
        locations.reorder_locations(ana, [c.rbloc_id, a.rbloc_id, b.rbloc_id])
        assert [(code, pos) for code, _, pos, _ in _locations()] == [('C', 1), ('A', 2), ('B', 3)]
        locations.create_location(ana, 'D')
        assert [code for code, *_ in _locations()] == ['C', 'A', 'B', 'D']

    @pytest.mark.parametrize('ids', ['missing', 'foreign', 'twice', 'unknown'])
    def test_anything_but_the_owners_full_list_changes_nothing(self, ana, bo, ids):
        a, b = locations.create_location(ana, 'A'), locations.create_location(ana, 'B')
        theirs = locations.create_location(bo, 'X')
        wanted = {'missing': [b.rbloc_id],
                  'foreign': [b.rbloc_id, a.rbloc_id, theirs.rbloc_id],
                  'twice': [b.rbloc_id, a.rbloc_id, a.rbloc_id],
                  'unknown': [b.rbloc_id, a.rbloc_id, 9999]}[ids]
        with pytest.raises(locations.InvalidOrder):
            locations.reorder_locations(ana, wanted)
        assert [code for code, *_ in _locations()] == ['A', 'B']
        assert _locations('bo') == [('X', None, 1, False)]

    def test_list_locations_follows_the_order(self, ana, bo):
        a, b = locations.create_location(ana, 'A'), locations.create_location(ana, 'B')
        locations.create_location(bo, 'X')
        locations.reorder_locations(ana, [b.rbloc_id, a.rbloc_id])
        assert [loc.rbloc_code for loc in locations.list_locations(ana)] == ['B', 'A']


# --- S6 lock -------------------------------------------------------------------------------

def test_lock_and_unlock(ana):
    loc = locations.create_location(ana, 'A')
    locations.set_locked(ana, loc.rbloc_id, True)
    assert _locations() == [('A', None, 1, True)]
    locations.set_locked(ana, loc.rbloc_id, False)
    assert _locations() == [('A', None, 1, False)]


# --- S7 suggested code ---------------------------------------------------------------------

class TestSuggestNextCode:
    @pytest.mark.parametrize('last, bump, expected', [
        ('B001-F001-P0001', 'pack', 'B001-F001-P0002'),
        ('B001-F001-P0001', 'row', 'B001-F002-P0001'),
        ('B001-F001-P0001', 'block', 'B002-F001-P0001'),
        ('B003-F007-P0042', 'row', 'B003-F008-P0001'),
        ('B003-F007-P0042', 'block', 'B004-F001-P0001'),
        ('B009-F010-P0099', 'pack', 'B009-F010-P0100'),
        ('B1-F1-P1', 'row', 'B1-F2-P1'),
        ('B999-F001-P0001', 'block', 'B1000-F001-P0001'),
        ('b001-f001-p0001', 'pack', 'b001-f001-p0002'),
    ])
    def test_the_chosen_part_is_incremented_and_the_parts_to_its_right_reset(
            self, ana, last, bump, expected):
        assert locations.suggest_next_code(ana, last, bump) == expected

    @pytest.mark.parametrize('last', ['DECK-001', 'Binder', 'B001-F001', 'B001-F001-P0001-X',
                                      'BA01-F001-P0001'])
    def test_a_code_without_the_pattern_has_no_suggestion(self, ana, last):
        assert locations.suggest_next_code(ana, last, 'pack') is None

    def test_without_a_last_code_the_first_one_or_the_newest_patterned_one_is_used(self, ana):
        assert locations.suggest_next_code(ana, None, 'pack') == 'B001-F001-P0001'
        locations.create_location(ana, 'B002-F003-P0004')
        locations.create_location(ana, 'POOL')
        assert locations.suggest_next_code(ana, None, 'pack') == 'B002-F003-P0005'
        assert locations.suggest_next_code(ana, None, 'row') == 'B002-F004-P0001'

    def test_a_code_the_owner_already_has_is_skipped(self, ana, bo):
        locations.create_location(ana, 'b001-f001-p0002')
        locations.create_location(bo, 'B001-F001-P0003')
        assert locations.suggest_next_code(ana, 'B001-F001-P0001', 'pack') == 'B001-F001-P0003'

    def test_an_unknown_bump_is_an_error(self, ana):
        with pytest.raises(ValueError):
            locations.suggest_next_code(ana, 'B001-F001-P0001', 'shelf')


# --- S8 copies per location ----------------------------------------------------------------

class TestCopies:
    def test_assign_adds_to_the_location_and_unassigned_is_derived(self, ana):
        line_id = _line(qty=6)
        a, b = locations.create_location(ana, 'A'), locations.create_location(ana, 'B')
        locations.assign_copies(ana, line_id, a.rbloc_id, 2)
        locations.assign_copies(ana, line_id, a.rbloc_id, 1)
        locations.assign_copies(ana, line_id, b.rbloc_id, 2)
        assert _held(line_id) == {'A': 3, 'B': 2}
        assert locations.unassigned(db.session.get(RbCollection, line_id)) == 1
        assert _quantity(line_id) == 6

    def test_over_assigning_is_refused_and_changes_nothing(self, ana):
        line_id = _line(qty=3)
        a, b = locations.create_location(ana, 'A'), locations.create_location(ana, 'B')
        locations.assign_copies(ana, line_id, a.rbloc_id, 2)
        with pytest.raises(locations.LocationOverQuantity) as exc:
            locations.assign_copies(ana, line_id, b.rbloc_id, 2)
        assert exc.value.available == 1
        assert _held(line_id) == {'A': 2}

    def test_line_locations_lists_them_in_the_owners_order(self, ana):
        line_id = _line(qty=6)
        a, b = locations.create_location(ana, 'A', 'first'), locations.create_location(ana, 'B')
        locations.assign_copies(ana, line_id, a.rbloc_id, 1)
        locations.assign_copies(ana, line_id, b.rbloc_id, 2)
        locations.reorder_locations(ana, [b.rbloc_id, a.rbloc_id])
        found = locations.line_locations(ana, line_id)
        assert found == {
            'locations': [
                {'location_id': b.rbloc_id, 'code': 'B', 'description': None, 'locked': False,
                 'qty': 2},
                {'location_id': a.rbloc_id, 'code': 'A', 'description': 'first', 'locked': False,
                 'qty': 1}],
            'unassigned': 3}

    def test_move_between_locations_and_back_to_unassigned(self, ana):
        line_id = _line(qty=4)
        a, b = locations.create_location(ana, 'A'), locations.create_location(ana, 'B')
        locations.assign_copies(ana, line_id, a.rbloc_id, 3)
        locations.move_copies(ana, line_id, a.rbloc_id, b.rbloc_id, 2)
        assert _held(line_id) == {'A': 1, 'B': 2}
        locations.move_copies(ana, line_id, None, b.rbloc_id, 1)
        assert _held(line_id) == {'A': 1, 'B': 3}
        locations.remove_copies(ana, line_id, a.rbloc_id, 1)
        assert _held(line_id) == {'B': 3}
        assert db.session.query(RbCollectionLocation).count() == 1

    def test_moving_more_than_the_source_holds_is_refused(self, ana):
        line_id = _line(qty=4)
        a, b = locations.create_location(ana, 'A'), locations.create_location(ana, 'B')
        locations.assign_copies(ana, line_id, a.rbloc_id, 3)
        with pytest.raises(locations.NotEnoughCopies) as exc:
            locations.move_copies(ana, line_id, a.rbloc_id, b.rbloc_id, 4)
        assert exc.value.available == 3
        with pytest.raises(locations.NotEnoughCopies) as exc:
            locations.remove_copies(ana, line_id, b.rbloc_id, 1)
        assert exc.value.available == 0
        with pytest.raises(locations.NotEnoughCopies) as exc:
            locations.move_copies(ana, line_id, None, b.rbloc_id, 2)
        assert exc.value.available == 1
        assert _held(line_id) == {'A': 3}

    def test_a_locked_location_is_read_only(self, ana):
        line_id = _line(qty=4)
        a, b = locations.create_location(ana, 'A'), locations.create_location(ana, 'B')
        locations.assign_copies(ana, line_id, a.rbloc_id, 2)
        locations.set_locked(ana, a.rbloc_id, True)
        for call in (lambda: locations.assign_copies(ana, line_id, a.rbloc_id, 1),
                     lambda: locations.remove_copies(ana, line_id, a.rbloc_id, 1),
                     lambda: locations.move_copies(ana, line_id, a.rbloc_id, b.rbloc_id, 1),
                     lambda: locations.move_copies(ana, line_id, b.rbloc_id, a.rbloc_id, 1)):
            with pytest.raises(locations.LocationLocked):
                call()
        assert _held(line_id) == {'A': 2}

    def test_foreign_lines_and_locations_are_not_found(self, ana, bo):
        mine, theirs = _line(qty=4), _line(qty=4, user='bo')
        a, x = locations.create_location(ana, 'A'), locations.create_location(bo, 'X')
        with pytest.raises(locations.LineNotFound):
            locations.assign_copies(ana, theirs, a.rbloc_id, 1)
        with pytest.raises(locations.LineNotFound):
            locations.line_locations(ana, theirs)
        with pytest.raises(locations.LocationNotFound):
            locations.assign_copies(ana, mine, x.rbloc_id, 1)
        assert db.session.query(RbCollectionLocation).count() == 0

    @pytest.mark.parametrize('qty', [0, -1])
    def test_a_quantity_below_one_is_an_error(self, ana, qty):
        line_id = _line(qty=4)
        a = locations.create_location(ana, 'A')
        with pytest.raises(ValueError):
            locations.assign_copies(ana, line_id, a.rbloc_id, qty)
        assert _held(line_id) == {}


# --- S9 take in order ----------------------------------------------------------------------

@pytest.fixture
def shelf(ana):
    """One line of OGN/1 with 6 copies: A (1st) 1, B (2nd, locked) 2, C (3rd) 1, unassigned 2;
    and an empty locked target location D (a mounted deck in F16-e)."""
    line_id = _line(qty=6)
    a, b, c, d = (locations.create_location(ana, code) for code in ('A', 'B', 'C', 'D'))
    for loc, qty in ((a, 1), (b, 2), (c, 1)):
        locations.assign_copies(ana, line_id, loc.rbloc_id, qty)
    locations.set_locked(ana, b.rbloc_id, True)
    locations.set_locked(ana, d.rbloc_id, True)
    return dict(line=line_id, A=a.rbloc_id, B=b.rbloc_id, C=c.rbloc_id, D=d.rbloc_id)


class TestTakeCopies:
    def test_unlocked_locations_in_order_then_unassigned_last(self, ana, shelf):
        moves = locations.take_copies(ana, [Want(3, line_ids=(shelf['line'],))], shelf['D'])
        assert moves == [Move(shelf['line'], shelf['A'], shelf['D'], 1),
                         Move(shelf['line'], shelf['C'], shelf['D'], 1),
                         Move(shelf['line'], None, shelf['D'], 1)]
        assert _held(shelf['line']) == {'B': 2, 'D': 3}
        assert _quantity(shelf['line']) == 6
        assert locations.unassigned(db.session.get(RbCollection, shelf['line'])) == 1

    def test_the_owners_order_decides(self, ana, shelf):
        locations.reorder_locations(ana, [shelf['C'], shelf['B'], shelf['A'], shelf['D']])
        moves = locations.take_copies(ana, [Want(1, line_ids=(shelf['line'],))], shelf['D'])
        assert moves == [Move(shelf['line'], shelf['C'], shelf['D'], 1)]

    def test_a_shortfall_changes_nothing_and_names_the_locked_locations(self, ana, shelf):
        with pytest.raises(locations.Shortfall) as exc:
            locations.take_copies(ana, [Want(5, set_id='OGN', card_id='1')], shelf['D'])
        assert exc.value.missing == [{'index': 0, 'line_ids': [], 'set_id': 'OGN',
                                      'card_id': '1', 'name': None, 'qty': 5, 'available': 4}]
        assert exc.value.locked == [{'location_id': shelf['B'], 'code': 'B', 'qty': 2}]
        assert _held(shelf['line']) == {'A': 1, 'B': 2, 'C': 1}

    def test_one_short_card_refuses_the_whole_take(self, ana, shelf):
        other = _line('2', qty=1)
        with pytest.raises(locations.Shortfall) as exc:
            locations.take_copies(ana, [Want(2, line_ids=(shelf['line'],)),
                                        Want(2, line_ids=(other,))], shelf['D'])
        assert [(m['index'], m['qty'], m['available']) for m in exc.value.missing] == [(1, 2, 1)]
        assert exc.value.locked == []
        assert _held(shelf['line']) == {'A': 1, 'B': 2, 'C': 1}

    def test_wants_sharing_lines_do_not_count_a_copy_twice(self, ana, shelf):
        with pytest.raises(locations.Shortfall) as exc:
            locations.take_copies(ana, [Want(3, line_ids=(shelf['line'],)),
                                        Want(2, set_id='OGN', card_id='1')], shelf['D'])
        assert [(m['index'], m['available']) for m in exc.value.missing] == [(1, 1)]

    def test_a_printing_takes_from_every_line_of_it_by_location_order(self, ana, shelf):
        foil = _line(qty=2, foil='S', changed=datetime(2026, 10, 2))
        c = shelf['C']
        locations.assign_copies(ana, foil, shelf['A'], 1)
        moves = locations.take_copies(ana, [Want(4, set_id='OGN', card_id='1')], shelf['D'])
        assert moves == [Move(shelf['line'], shelf['A'], shelf['D'], 1),
                         Move(foil, shelf['A'], shelf['D'], 1),
                         Move(shelf['line'], c, shelf['D'], 1),
                         Move(shelf['line'], None, shelf['D'], 1)]

    def test_a_card_name_takes_any_printing(self, ana, shelf):
        ogn, sfd = _line('79', qty=1), _line('257', set_id='SFD', qty=1)
        locations.assign_copies(ana, sfd, shelf['A'], 1)
        moves = locations.take_copies(ana, [Want(2, name='jinx, loose cannon')], shelf['D'])
        assert moves == [Move(sfd, shelf['A'], shelf['D'], 1), Move(ogn, None, shelf['D'], 1)]

    def test_other_users_copies_are_never_taken(self, ana, bo, shelf):
        _line(qty=9, user='bo')
        with pytest.raises(locations.Shortfall):
            locations.take_copies(ana, [Want(5, set_id='OGN', card_id='1')], shelf['D'])

    def test_the_target_must_be_the_owners(self, ana, bo, shelf):
        theirs = locations.create_location(bo, 'X')
        with pytest.raises(locations.LocationNotFound):
            locations.take_copies(ana, [Want(1, line_ids=(shelf['line'],))], theirs.rbloc_id)
        with pytest.raises(locations.LineNotFound):
            locations.take_copies(ana, [Want(1, line_ids=(9999,))], shelf['D'])
        assert _held(shelf['line']) == {'A': 1, 'B': 2, 'C': 1}

    @pytest.mark.parametrize('want', [lambda: Want(1), lambda: Want(1, set_id='OGN'),
                                      lambda: Want(1, line_ids=(1,), name='x'),
                                      lambda: Want(0, name='x')])
    def test_a_want_needs_one_selector_and_a_positive_quantity(self, want):
        with pytest.raises(ValueError):
            want()
