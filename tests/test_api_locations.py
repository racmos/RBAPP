"""F16-b S1-S6: GET/POST /locations, GET /locations/next-code, PATCH/DELETE /locations/<id>,
PUT /locations/order."""
import pytest

from app import db
from app.models import RbCollectionLocation, RbLocation, User
from app.services import locations
from tests.collection_read_helpers import line, seed_catalog

BASE = '/riftbound/api/v1/locations'
NOT_FOUND = {'success': False, 'error': 'Not Found',
             'message': 'The requested resource was not found'}
ITEM_KEYS = ['id', 'code', 'description', 'position', 'locked', 'deck_id', 'copies', 'cards']


@pytest.fixture
def api(app, authenticated_client, make_user):
    make_user('otheruser')
    seed_catalog()
    return authenticated_client


def _user(name='testuser'):
    return User.query.filter_by(username=name).one()


def _line(card='1', qty=6, user='testuser'):
    row = line(card, qty, user=user)
    db.session.add(row)
    db.session.commit()
    return row.rbcol_id


def _rows(user='testuser'):
    db.session.expire_all()
    return [(loc.rbloc_code, loc.rbloc_description, loc.rbloc_position, loc.rbloc_locked)
            for loc in RbLocation.query.filter_by(rbloc_user=user)
            .order_by(RbLocation.rbloc_position)]


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


class TestList:
    def test_empty(self, api):
        resp = api.get(BASE)
        assert resp.get_json() == {'success': True, 'data': {'items': []},
                                   'meta': {'unassigned_copies': 0}}

    def test_items_follow_the_users_order_with_their_copies_and_cards(self, api):
        me = _user()
        a = locations.create_location(me, 'A', 'Binder')
        b = locations.create_location(me, 'B')
        first, second = _line('1', 6), _line('2', 3)
        locations.assign_copies(me, first, a.rbloc_id, 2)
        locations.assign_copies(me, second, a.rbloc_id, 1)
        locations.assign_copies(me, first, b.rbloc_id, 4)
        locations.reorder_locations(me, [b.rbloc_id, a.rbloc_id])
        locations.set_locked(me, a.rbloc_id, True)
        resp = api.get(BASE)
        body = resp.get_json()
        assert list(body['data']['items'][0]) == ITEM_KEYS
        assert body['data']['items'] == [
            {'id': b.rbloc_id, 'code': 'B', 'description': None, 'position': 1, 'locked': False,
             'deck_id': None, 'copies': 4, 'cards': 1},
            {'id': a.rbloc_id, 'code': 'A', 'description': 'Binder', 'position': 2,
             'locked': True, 'deck_id': None, 'copies': 3, 'cards': 2},
        ]
        assert body['meta'] == {'unassigned_copies': 2}   # 9 copies, 7 placed

    def test_only_my_locations(self, api):
        locations.create_location(_user('otheruser'), 'THEIRS')
        _line('1', 5, user='otheruser')
        assert api.get(BASE).get_json()['data']['items'] == []
        assert api.get(BASE).get_json()['meta'] == {'unassigned_copies': 0}

    def test_anonymous_is_refused(self, app):
        assert app.test_client().get(BASE).status_code == 401


class TestCreate:
    def test_created_last_and_returned(self, api):
        locations.create_location(_user(), 'FIRST')
        item = _data(api.post(BASE, json={'code': 'B001-F001-P0001',
                                          'description': 'Blue binder'}), 201)
        assert list(item) == ITEM_KEYS
        assert {k: item[k] for k in ITEM_KEYS if k != 'id'} == {
            'code': 'B001-F001-P0001', 'description': 'Blue binder', 'position': 2,
            'locked': False, 'deck_id': None, 'copies': 0, 'cards': 0}
        assert _rows()[-1] == ('B001-F001-P0001', 'Blue binder', 2, False)

    def test_description_is_optional_and_trimmed(self, api):
        assert _data(api.post(BASE, json={'code': 'POOL'}), 201)['description'] is None
        assert _data(api.post(BASE, json={'code': 'BOX', 'description': '  '}),
                     201)['description'] is None
        assert _data(api.post(BASE, json={'code': 'BOX2', 'description': ' Shelf '}),
                     201)['description'] == 'Shelf'

    def test_a_duplicate_code_ignoring_case_is_a_409(self, api):
        locations.create_location(_user(), 'Box-1')
        body = _error(api.post(BASE, json={'code': 'BOX-1'}), 409, 'already_exists')
        assert body['error'] == 'Conflict'
        assert _rows() == [('Box-1', None, 1, False)]

    def test_another_users_code_is_free(self, api):
        locations.create_location(_user('otheruser'), 'BOX')
        _data(api.post(BASE, json={'code': 'BOX'}), 201)

    @pytest.mark.parametrize('code, detail', [
        ('', 'too_short'), ('a b', 'invalid_format'), ('ab_c', 'invalid_format'),
        ('ñu', 'invalid_format'), ('x' * 33, 'too_long'), (None, 'invalid_value'),
        (12, 'invalid_value'),
    ])
    def test_a_bad_code_is_a_400(self, api, code, detail):
        body = _error(api.post(BASE, json={'code': code}), 400, 'validation_error')
        assert body['details'][0]['field'] == 'code'
        assert body['details'][0]['code'] == detail
        assert _rows() == []

    def test_a_missing_code_or_long_description_is_a_400(self, api):
        assert _error(api.post(BASE, json={}), 400,
                      'validation_error')['details'][0]['code'] == 'required'
        body = _error(api.post(BASE, json={'code': 'A', 'description': 'x' * 201}), 400,
                      'validation_error')
        assert body['details'][0]['field'] == 'description'
        assert _rows() == []


class TestNextCode:
    def test_first_suggestion_without_patterned_codes(self, api):
        locations.create_location(_user(), 'POOL')
        assert _data(api.get(f'{BASE}/next-code', query_string={'bump': 'pack'})) == {
            'code': 'B001-F001-P0001'}

    @pytest.mark.parametrize('bump, expected', [
        ('pack', 'B001-F002-P0004'), ('row', 'B001-F003-P0001'), ('block', 'B002-F001-P0001'),
    ])
    def test_bumps_the_users_newest_patterned_code(self, api, bump, expected):
        me = _user()
        locations.create_location(me, 'B001-F002-P0003')
        locations.create_location(me, 'DECK-001')
        locations.create_location(_user('otheruser'), 'B009-F009-P0009')
        assert _data(api.get(f'{BASE}/next-code', query_string={'bump': bump})) == {
            'code': expected}

    def test_after_a_given_code(self, api):
        assert _data(api.get(f'{BASE}/next-code', query_string={
            'bump': 'row', 'after': 'b001-f007-p0002'})) == {'code': 'b001-f008-p0001'}

    def test_after_a_code_without_the_pattern_is_null(self, api):
        assert _data(api.get(f'{BASE}/next-code', query_string={
            'bump': 'pack', 'after': 'Binder'})) == {'code': None}

    @pytest.mark.parametrize('params', [{}, {'bump': 'shelf'}, {'bump': 'pack', 'after': 'x' * 33}])
    def test_a_bad_query_is_a_400(self, api, params):
        _error(api.get(f'{BASE}/next-code', query_string=params), 400, 'validation_error')


class TestPatch:
    def test_changes_only_what_is_sent(self, api):
        loc = locations.create_location(_user(), 'A', 'old')
        item = _data(api.patch(f'{BASE}/{loc.rbloc_id}', json={'description': 'new'}))
        assert (item['code'], item['description'], item['locked']) == ('A', 'new', False)
        item = _data(api.patch(f'{BASE}/{loc.rbloc_id}', json={'code': 'A2'}))
        assert (item['code'], item['description']) == ('A2', 'new')
        item = _data(api.patch(f'{BASE}/{loc.rbloc_id}', json={'description': None}))
        assert item['description'] is None
        assert _rows() == [('A2', None, 1, False)]

    def test_lock_and_unlock(self, api):
        loc = locations.create_location(_user(), 'A')
        assert _data(api.patch(f'{BASE}/{loc.rbloc_id}', json={'locked': True}))['locked'] is True
        assert _rows() == [('A', None, 1, True)]
        assert _data(api.patch(f'{BASE}/{loc.rbloc_id}',
                               json={'locked': False}))['locked'] is False

    def test_a_locked_location_can_be_renamed(self, api):
        loc = locations.create_location(_user(), 'A')
        locations.set_locked(_user(), loc.rbloc_id, True)
        item = _data(api.patch(f'{BASE}/{loc.rbloc_id}', json={'code': 'B', 'description': 'd'}))
        assert (item['code'], item['description'], item['locked']) == ('B', 'd', True)

    def test_the_item_carries_its_counts(self, api):
        loc = locations.create_location(_user(), 'A')
        locations.assign_copies(_user(), _line('1', 4), loc.rbloc_id, 3)
        item = _data(api.patch(f'{BASE}/{loc.rbloc_id}', json={'description': 'x'}))
        assert (item['copies'], item['cards']) == (3, 1)

    def test_a_duplicate_code_is_a_409_and_nothing_changes(self, api):
        me = _user()
        locations.create_location(me, 'A')
        b = locations.create_location(me, 'B')
        _error(api.patch(f'{BASE}/{b.rbloc_id}', json={'code': 'a', 'locked': True}), 409,
               'already_exists')
        assert _rows() == [('A', None, 1, False), ('B', None, 2, False)]

    @pytest.mark.parametrize('body', [{'code': None}, {'locked': None}, {'code': 'a b'},
                                      {'locked': 'yes'}, {'description': 'x' * 201}])
    def test_bad_values_are_a_400(self, api, body):
        loc = locations.create_location(_user(), 'A')
        _error(api.patch(f'{BASE}/{loc.rbloc_id}', json=body), 400, 'validation_error')
        assert _rows() == [('A', None, 1, False)]

    def test_a_foreign_or_unknown_id_is_a_404(self, api):
        theirs = locations.create_location(_user('otheruser'), 'T')
        for location_id in (theirs.rbloc_id, 9999):
            resp = api.patch(f'{BASE}/{location_id}', json={'description': 'mine'})
            assert resp.status_code == 404 and resp.get_json() == NOT_FOUND
        assert _rows('otheruser') == [('T', None, 1, False)]


class TestDelete:
    def test_returns_the_deleted_item_frees_its_copies_and_closes_the_order(self, api):
        me = _user()
        a = locations.create_location(me, 'A')
        locations.create_location(me, 'B')
        line_id = _line('1', 5)
        locations.assign_copies(me, line_id, a.rbloc_id, 3)
        deleted = _data(api.delete(f'{BASE}/{a.rbloc_id}'))['deleted']
        assert deleted == {'id': a.rbloc_id, 'code': 'A', 'description': None, 'position': 1,
                           'locked': False, 'deck_id': None, 'copies': 3, 'cards': 1}
        assert _rows() == [('B', None, 1, False)]
        assert db.session.query(RbCollectionLocation).count() == 0
        assert api.get(BASE).get_json()['meta'] == {'unassigned_copies': 5}

    def test_a_locked_ordinary_location_can_be_deleted(self, api):
        loc = locations.create_location(_user(), 'A')
        locations.set_locked(_user(), loc.rbloc_id, True)
        assert _data(api.delete(f'{BASE}/{loc.rbloc_id}'))['deleted']['locked'] is True
        assert _rows() == []

    def test_a_locked_deck_location_is_a_409(self, api):
        loc = locations.create_location(_user(), 'DECK-001')
        db.session.get(RbLocation, loc.rbloc_id).rbloc_deck_id = 7
        db.session.commit()
        locations.set_locked(_user(), loc.rbloc_id, True)
        body = _error(api.delete(f'{BASE}/{loc.rbloc_id}'), 409, 'location_locked')
        assert body['error'] == 'Conflict'
        assert _rows() == [('DECK-001', None, 1, True)]

    def test_a_foreign_or_unknown_id_is_a_404(self, api):
        theirs = locations.create_location(_user('otheruser'), 'T')
        for location_id in (theirs.rbloc_id, 9999):
            resp = api.delete(f'{BASE}/{location_id}')
            assert resp.status_code == 404 and resp.get_json() == NOT_FOUND
        assert _rows('otheruser') == [('T', None, 1, False)]


class TestOrder:
    def test_sets_the_whole_order_and_returns_the_items(self, api):
        me = _user()
        a, b, c = (locations.create_location(me, code) for code in 'ABC')
        data = _data(api.put(f'{BASE}/order', json={'ids': [c.rbloc_id, a.rbloc_id,
                                                            b.rbloc_id]}))
        assert [(item['code'], item['position']) for item in data['items']] == [
            ('C', 1), ('A', 2), ('B', 3)]
        assert [row[0] for row in _rows()] == ['C', 'A', 'B']

    @pytest.mark.parametrize('pick', [
        lambda a, b, t: [a],                 # missing
        lambda a, b, t: [a, b, b],           # repeated
        lambda a, b, t: [a, b, t],           # foreign
        lambda a, b, t: [a, b, 9999],        # unknown
    ])
    def test_anything_but_every_id_once_is_a_400_and_nothing_changes(self, api, pick):
        me = _user()
        a, b = locations.create_location(me, 'A'), locations.create_location(me, 'B')
        theirs = locations.create_location(_user('otheruser'), 'T')
        body = _error(api.put(f'{BASE}/order', json={
            'ids': pick(a.rbloc_id, b.rbloc_id, theirs.rbloc_id)}), 400, 'validation_error')
        assert body['details'][0]['field'] == 'ids'
        assert body['details'][0]['code'] == 'invalid_value'
        assert [row[0] for row in _rows()] == ['A', 'B']

    @pytest.mark.parametrize('body', [{}, {'ids': 'A'}, {'ids': ['x']}, {'ids': [0]}])
    def test_a_malformed_body_is_a_400(self, api, body):
        _error(api.put(f'{BASE}/order', json=body), 400, 'validation_error')

    def test_no_locations_and_an_empty_list(self, api):
        assert _data(api.put(f'{BASE}/order', json={'ids': []})) == {'items': []}
