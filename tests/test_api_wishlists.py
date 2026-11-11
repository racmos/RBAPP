"""F3-f-2: wishlists API (lists and lines): GET/POST /wishlists, PATCH/DELETE /wishlists/<id>,
PUT /wishlists/order, GET/POST /wishlists/<id>/lines, PATCH/DELETE /wishlists/<id>/lines/<id>,
POST /wishlists/<id>/lines/move (docs/requirements/F3/F3-f-wishlists-design.md)."""
import pytest
from sqlalchemy import event

from app import db
from app.models import RbWishlist, RbWishlistLine
from tests.conftest import login_as
from tests.wishlist_helpers import (BASE, LINE_KEYS, LIST_KEYS, NOT_FOUND, add, data,
                                    default_list, error, lines_of, lists_of, new_list, own,
                                    printing, seed_catalog, seed_fillers, user_id)


@pytest.fixture
def api(app, authenticated_client, make_user):
    make_user('otheruser')
    seed_catalog()
    return authenticated_client


@pytest.fixture
def other(app, api):
    """A client signed in as `otheruser` (the `api` user stays signed in on its own client)."""
    return login_as(app.test_client(), 'otheruser')


def _validation(resp, field=None):
    body = error(resp, 400, 'validation_error')
    if field is not None:
        assert field in {detail['field'] for detail in body['details']}, body
    return body


# --- lists -----------------------------------------------------------------------------------

class TestListLists:
    def test_first_call_creates_the_default_list(self, api):
        items = data(api.get(BASE))['items']
        assert len(items) == 1
        assert list(items[0]) == LIST_KEYS
        item = items[0]
        assert (item['name'], item['is_default'], item['position'], item['line_count']) == \
            ('Wishlist', True, 1, 0)
        assert item['created_at'].endswith('Z') and item['updated_at'].endswith('Z')

    def test_the_default_list_is_created_once(self, api):
        first = data(api.get(BASE))['items']
        second = data(api.get(BASE))['items']
        assert first == second
        assert len(lists_of()) == 1

    def test_items_follow_position_with_line_counts(self, api):
        default = default_list(api)
        second = new_list(api, 'Trades')
        add(api, second, **printing('1'))
        add(api, second, **printing('2'))
        items = data(api.get(BASE))['items']
        assert [(i['id'], i['name'], i['position'], i['line_count'], i['is_default'])
                for i in items] == [(default, 'Wishlist', 1, 0, True),
                                    (second, 'Trades', 2, 2, False)]

    def test_never_shows_another_users_lists(self, api, other):
        new_list(other, 'Secret')
        assert [i['name'] for i in data(api.get(BASE))['items']] == ['Wishlist']


class TestCreateList:
    def test_creates_a_list_last_in_order(self, api):
        default_list(api)
        resp = api.post(BASE, json={'name': '  Trades  '})
        item = data(resp, 201)
        assert list(item) == LIST_KEYS
        assert (item['name'], item['is_default'], item['position'], item['line_count']) == \
            ('Trades', False, 2, 0)

    def test_the_first_list_of_a_user_is_the_default(self, api):
        item = data(api.post(BASE, json={'name': 'Mine'}), 201)
        assert item['is_default'] is True and item['position'] == 1
        assert [i['name'] for i in data(api.get(BASE))['items']] == ['Mine']

    def test_duplicate_name_ignoring_case_is_a_409(self, api):
        default_list(api)
        new_list(api, 'Trades')
        error(api.post(BASE, json={'name': 'TRADES'}), 409, 'already_exists')
        error(api.post(BASE, json={'name': 'wishlist'}), 409, 'already_exists')
        assert len(lists_of()) == 2

    def test_another_user_may_use_the_same_name(self, api, other):
        new_list(other, 'Trades')
        default_list(api)
        new_list(api, 'Trades')

    @pytest.mark.parametrize('name', ['', '   ', 'x' * 81, None])
    def test_blank_or_long_names_are_refused(self, api, name):
        _validation(api.post(BASE, json={'name': name}), 'name')
        assert lists_of() == []

    def test_eighty_characters_is_fine(self, api):
        assert data(api.post(BASE, json={'name': 'x' * 80}), 201)['name'] == 'x' * 80

    def test_at_most_twenty_lists(self, api):
        default_list(api)
        for n in range(19):
            new_list(api, f'List {n}')
        body = error(api.post(BASE, json={'name': 'One too many'}), 409, 'wishlist_limit')
        assert body['params'] == {'scope': 'lists', 'max': 20}
        assert len(lists_of()) == 20


class TestUpdateList:
    def test_rename(self, api):
        default = default_list(api)
        item = data(api.patch(f'{BASE}/{default}', json={'name': ' Wants '}))
        assert list(item) == LIST_KEYS
        assert (item['name'], item['is_default']) == ('Wants', True)

    def test_rename_to_another_case_of_its_own_name(self, api):
        default = default_list(api)
        assert data(api.patch(f'{BASE}/{default}', json={'name': 'WISHLIST'}))['name'] == \
            'WISHLIST'

    def test_rename_to_a_taken_name_is_a_409(self, api):
        default = default_list(api)
        new_list(api, 'Trades')
        error(api.patch(f'{BASE}/{default}', json={'name': 'trades'}), 409, 'already_exists')
        assert lists_of()[0].rbwls_name == 'Wishlist'

    def test_starring_moves_the_default(self, api):
        default = default_list(api)
        second = new_list(api, 'Trades')
        item = data(api.patch(f'{BASE}/{second}', json={'is_default': True}))
        assert item['is_default'] is True
        assert [(row.rbwls_id, row.rbwls_is_default) for row in lists_of()] == \
            [(default, False), (second, True)]

    def test_starring_the_default_again_changes_nothing(self, api):
        default = default_list(api)
        assert data(api.patch(f'{BASE}/{default}', json={'is_default': True}))['is_default']

    def test_unstarring_the_default_is_refused(self, api):
        default = default_list(api)
        _validation(api.patch(f'{BASE}/{default}', json={'is_default': False}), 'is_default')
        assert lists_of()[0].rbwls_is_default is True

    def test_unstarring_a_list_that_is_not_the_default_changes_nothing(self, api):
        default_list(api)
        second = new_list(api, 'Trades')
        assert data(api.patch(f'{BASE}/{second}', json={'is_default': False}))[
            'is_default'] is False

    @pytest.mark.parametrize('body', [{'name': None}, {'is_default': None}, {'name': ''},
                                      {'is_default': 'yes'}])
    def test_invalid_values(self, api, body):
        default = default_list(api)
        _validation(api.patch(f'{BASE}/{default}', json=body))


class TestDeleteList:
    def test_the_default_list_cannot_be_deleted(self, api):
        default = default_list(api)
        new_list(api, 'Trades')
        body = error(api.delete(f'{BASE}/{default}'), 409, 'wishlist_default')
        assert 'Star another list' in body['message']
        assert len(lists_of()) == 2

    def test_the_only_list_cannot_be_deleted(self, api):
        default = default_list(api)
        error(api.delete(f'{BASE}/{default}'), 409, 'wishlist_default')

    def test_deletes_the_list_and_its_lines_and_returns_them(self, api):
        default = default_list(api)
        second = new_list(api, 'Trades')
        third = new_list(api, 'Later')
        line = add(api, second, **printing('1', qty=2))['line']
        add(api, default, **printing('1'))
        removed = data(api.delete(f'{BASE}/{second}'))
        assert removed['deleted']['id'] == second
        assert removed['deleted']['name'] == 'Trades'
        assert removed['deleted']['line_count'] == 1
        assert [item['id'] for item in removed['lines']] == [line['id']]
        assert list(removed['lines'][0]) == LINE_KEYS
        assert [(row.rbwls_id, row.rbwls_position) for row in lists_of()] == \
            [(default, 1), (third, 2)]
        assert RbWishlistLine.query.filter_by(rbwsl_list_id=second).count() == 0
        assert len(lines_of(default)) == 1

    def test_a_starred_list_can_be_deleted_after_starring_another(self, api):
        default = default_list(api)
        second = new_list(api, 'Trades')
        api.patch(f'{BASE}/{second}', json={'is_default': True})
        data(api.delete(f'{BASE}/{default}'))
        assert [(row.rbwls_name, row.rbwls_position) for row in lists_of()] == [('Trades', 1)]


class TestOrder:
    def test_reorders(self, api):
        a = default_list(api)
        b = new_list(api, 'B')
        c = new_list(api, 'C')
        items = data(api.put(f'{BASE}/order', json={'ids': [c, a, b]}))['items']
        assert [(i['id'], i['position']) for i in items] == [(c, 1), (a, 2), (b, 3)]
        assert [row.rbwls_id for row in lists_of()] == [c, a, b]

    @pytest.mark.parametrize('pick', [
        lambda a, b, x: [a],                 # missing one
        lambda a, b, x: [a, b, b],           # duplicated
        lambda a, b, x: [a, b, 999999],      # unknown
        lambda a, b, x: [a, b, x],           # another user's
        lambda a, b, x: [],
    ])
    def test_must_be_exactly_the_users_ids(self, api, other, pick):
        a = default_list(api)
        b = new_list(api, 'B')
        x = default_list(other)
        _validation(api.put(f'{BASE}/order', json={'ids': pick(a, b, x)}), 'ids')
        assert [row.rbwls_id for row in lists_of()] == [a, b]


# --- lines -----------------------------------------------------------------------------------

class TestAddLine:
    def test_adds_a_printing(self, api):
        default = default_list(api)
        result = add(api, default, **printing('1', foil='N', qty=3, max_price=12.345,
                                               note='  for the deck '))
        assert result['merged'] is False
        line = result['line']
        assert list(line) == LINE_KEYS
        assert (line['list_id'], line['name'], line['set_id'], line['card_id'], line['foil'],
                line['qty'], line['max_price'], line['note']) == \
            (default, 'Alpha Fury', 'OGN', '1', 'N', 3, 12.35, 'for the deck')
        assert line['card']['key'] == 'OGN-1'
        row = lines_of(default)[0]
        assert (row.rbwsl_name_key, row.rbwsl_rbset_id, row.rbwsl_rbcar_id) == \
            ('alpha fury', 'OGN', '1')

    def test_defaults(self, api):
        default = default_list(api)
        line = add(api, default, **printing('1'))['line']
        assert (line['foil'], line['qty'], line['max_price'], line['note'], line['reached']) == \
            ('any', 1, None, None, None)

    def test_adds_by_name_matching_the_catalog(self, api):
        default = default_list(api)
        line = add(api, default, name='  alpha   FURY ')['line']
        assert (line['name'], line['set_id'], line['card_id']) == ('Alpha Fury', None, None)
        assert line['card']['key'] == 'OGN-1'           # the base printing
        assert line['card']['is_base'] is True
        assert lines_of(default)[0].rbwsl_name_key == 'alpha fury'

    def test_unknown_name_is_refused(self, api):
        default = default_list(api)
        _validation(api.post(f'{BASE}/{default}/lines', json={'name': 'Nobody'}), 'name')
        assert lines_of(default) == []

    def test_unknown_printing_is_refused(self, api):
        default = default_list(api)
        _validation(api.post(f'{BASE}/{default}/lines', json=printing('999')), 'card_id')

    @pytest.mark.parametrize('body', [{'set_id': 'OGN'}, {'card_id': '1'},
                                      {'set_id': 'OGN', 'name': 'Alpha Fury'}, {}])
    def test_a_target_is_a_printing_or_a_name(self, api, body):
        default = default_list(api)
        _validation(api.post(f'{BASE}/{default}/lines', json=body))
        assert lines_of(default) == []

    @pytest.mark.parametrize('extra', [{'qty': 0}, {'qty': 100}, {'qty': '2'}, {'foil': 'Y'},
                                       {'max_price': -1}, {'note': 'x' * 201}])
    def test_invalid_values(self, api, extra):
        default = default_list(api)
        _validation(api.post(f'{BASE}/{default}/lines', json=printing('1', **extra)))

    def test_foil_on_a_card_without_foil_is_refused(self, api):
        default = default_list(api)
        body = error(api.post(f'{BASE}/{default}/lines', json=printing('79', foil='S')), 400,
                     'foil_not_allowed')
        assert body['message'] == 'This card has no foil version.'
        error(api.post(f'{BASE}/{default}/lines', json={'name': 'Jinx, Loose Cannon',
                                                        'foil': 'S'}), 400, 'foil_not_allowed')
        assert lines_of(default) == []

    def test_any_foil_is_always_fine(self, api):
        default = default_list(api)
        add(api, default, **printing('79', foil='any'))

    def test_the_same_target_merges_and_caps_at_99(self, api):
        default = default_list(api)
        first = add(api, default, **printing('1', foil='S', qty=60))['line']
        result = add(api, default, 200, **printing('1', foil='S', qty=30, max_price=25))
        assert result['merged'] is True
        assert (result['line']['id'], result['line']['qty'], result['line']['max_price']) == \
            (first['id'], 90, 25.0)
        capped = add(api, default, 200, **printing('1', foil='S', qty=50))['line']
        assert capped['qty'] == 99 and capped['max_price'] == 25.0
        assert len(lines_of(default)) == 1

    def test_by_name_targets_merge_too(self, api):
        default = default_list(api)
        add(api, default, name='Alpha Fury', qty=2)
        assert add(api, default, 200, name='ALPHA FURY', qty=3)['line']['qty'] == 5

    def test_foil_alt_art_and_by_name_are_different_lines(self, api):
        default = default_list(api)
        add(api, default, **printing('1', foil='N'))
        add(api, default, **printing('1', foil='S'))
        add(api, default, **printing('1', foil='any'))
        add(api, default, **printing('1a', foil='N'))
        add(api, default, **printing('5', set_id='SFD'))
        add(api, default, name='Alpha Fury')
        assert len(lines_of(default)) == 6

    def test_the_same_card_may_be_in_several_lists(self, api):
        default = default_list(api)
        second = new_list(api, 'Trades')
        add(api, default, **printing('1'))
        add(api, second, **printing('1'))

    def test_at_most_100_lines_and_a_merge_at_the_limit_still_works(self, api):
        default = default_list(api)
        for card_id in seed_fillers(100):
            db.session.add(RbWishlistLine(rbwsl_list_id=default, rbwsl_name_key=f'filler {card_id}',
                                          rbwsl_name=f'Filler {card_id}', rbwsl_rbset_id='OGN',
                                          rbwsl_rbcar_id=card_id, rbwsl_foil='any', rbwsl_qty=1))
        db.session.commit()
        body = error(api.post(f'{BASE}/{default}/lines', json=printing('1')), 409,
                     'wishlist_limit')
        assert body['params'] == {'scope': 'lines', 'max': 100}
        assert len(lines_of(default)) == 100
        assert add(api, default, 200, **printing('100', qty=4))['line']['qty'] == 5


class TestUpdateLine:
    def _line(self, api, **body):
        default = default_list(api)
        return default, add(api, default, **printing('1', **body))['line']

    def test_changes_the_sent_fields(self, api):
        default, line = self._line(api, qty=2, max_price=5, note='keep')
        updated = data(api.patch(f'{BASE}/{default}/lines/{line["id"]}',
                                 json={'qty': 7, 'foil': 'S', 'note': 'trade'}))
        assert list(updated) == LINE_KEYS
        assert (updated['qty'], updated['foil'], updated['max_price'], updated['note']) == \
            (7, 'S', 5.0, 'trade')

    def test_null_clears_the_max_price_and_the_note(self, api):
        default, line = self._line(api, max_price=5, note='keep')
        updated = data(api.patch(f'{BASE}/{default}/lines/{line["id"]}',
                                 json={'max_price': None, 'note': None}))
        assert (updated['max_price'], updated['note'], updated['reached']) == (None, None, None)

    @pytest.mark.parametrize('body', [{'qty': None}, {'foil': None}, {'qty': 100},
                                      {'max_price': -0.01}])
    def test_invalid_values(self, api, body):
        default, line = self._line(api)
        _validation(api.patch(f'{BASE}/{default}/lines/{line["id"]}', json=body))

    def test_foil_on_a_card_without_foil_is_refused(self, api):
        default = default_list(api)
        line = add(api, default, **printing('79'))['line']
        error(api.patch(f'{BASE}/{default}/lines/{line["id"]}', json={'foil': 'S'}), 400,
              'foil_not_allowed')

    def test_a_foil_change_that_collides_is_a_409(self, api):
        default = default_list(api)
        add(api, default, **printing('1', foil='S'))
        line = add(api, default, **printing('1', foil='N'))['line']
        error(api.patch(f'{BASE}/{default}/lines/{line["id"]}', json={'foil': 'S'}), 409,
              'already_exists')
        assert [row.rbwsl_foil for row in lines_of(default)] == ['S', 'N']


class TestDeleteLine:
    def test_returns_the_line_and_posting_it_back_restores_it(self, api):
        default = default_list(api)
        line = add(api, default, **printing('1', foil='S', qty=3, max_price=20,
                                               note='gift'))['line']
        by_name = add(api, default, name='Beta Calm', qty=2)['line']
        removed = data(api.delete(f'{BASE}/{default}/lines/{line["id"]}'))['deleted']
        assert removed == line
        assert [row.rbwsl_id for row in lines_of(default)] == [by_name['id']]
        restored = data(api.post(f'{BASE}/{default}/lines', json=removed), 201)['line']
        for key in ('name', 'set_id', 'card_id', 'foil', 'qty', 'max_price', 'note'):
            assert restored[key] == line[key]
        removed = data(api.delete(f'{BASE}/{default}/lines/{by_name["id"]}'))['deleted']
        restored = data(api.post(f'{BASE}/{default}/lines', json=removed), 201)['line']
        assert (restored['set_id'], restored['name'], restored['qty']) == (None, 'Beta Calm', 2)


class TestMove:
    def _setup(self, api):
        source = default_list(api)
        target = new_list(api, 'Trades')
        a = add(api, source, **printing('1', qty=2))['line']
        b = add(api, source, **printing('2', qty=60, max_price=3))['line']
        c = add(api, source, name='Jinx, Loose Cannon')['line']
        add(api, target, **printing('2', qty=50))
        return source, target, a, b, c

    def test_move_merges_collisions(self, api):
        source, target, a, b, c = self._setup(api)
        result = data(api.post(f'{BASE}/{source}/lines/move',
                               json={'line_ids': [a['id'], b['id']], 'to_list_id': target,
                                     'mode': 'move'}))
        assert result == {'moved': 1, 'merged': 1, 'skipped': 0}
        assert [row.rbwsl_id for row in lines_of(source)] == [c['id']]
        moved = {(row.rbwsl_rbcar_id, row.rbwsl_qty, row.rbwsl_max_price is not None)
                 for row in lines_of(target)}
        assert moved == {('1', 2, False), ('2', 99, True)}

    def test_copy_keeps_the_source(self, api):
        source, target, a, b, c = self._setup(api)
        result = data(api.post(f'{BASE}/{source}/lines/move',
                               json={'line_ids': [a['id'], c['id']], 'to_list_id': target,
                                     'mode': 'copy'}))
        assert result == {'moved': 2, 'merged': 0, 'skipped': 0}
        assert len(lines_of(source)) == 3
        assert len(lines_of(target)) == 3

    def test_a_target_already_at_99_is_skipped(self, api):
        source, target, a, b, c = self._setup(api)
        api.patch(f'{BASE}/{target}/lines/{lines_of(target)[0].rbwsl_id}', json={'qty': 99})
        result = data(api.post(f'{BASE}/{source}/lines/move',
                               json={'line_ids': [b['id']], 'to_list_id': target,
                                     'mode': 'copy'}))
        assert result == {'moved': 0, 'merged': 0, 'skipped': 1}

    def test_a_full_target_changes_nothing(self, api):
        source, target, a, b, c = self._setup(api)
        for card_id in seed_fillers(99):
            db.session.add(RbWishlistLine(rbwsl_list_id=target, rbwsl_name_key=f'filler {card_id}',
                                          rbwsl_name=f'Filler {card_id}', rbwsl_rbset_id='OGN',
                                          rbwsl_rbcar_id=card_id, rbwsl_foil='any', rbwsl_qty=1))
        db.session.commit()
        body = error(api.post(f'{BASE}/{source}/lines/move',
                              json={'line_ids': [a['id'], b['id'], c['id']],
                                    'to_list_id': target, 'mode': 'move'}),
                     409, 'wishlist_limit')
        assert body['params'] == {'scope': 'lines', 'max': 100}
        assert len(lines_of(source)) == 3 and len(lines_of(target)) == 100
        assert lines_of(target)[0].rbwsl_qty == 50
        # Only the colliding line: no new line, so it fits.
        assert data(api.post(f'{BASE}/{source}/lines/move',
                             json={'line_ids': [b['id']], 'to_list_id': target,
                                   'mode': 'move'})) == {'moved': 0, 'merged': 1, 'skipped': 0}

    def test_lines_of_another_list_or_the_same_list(self, api):
        source, target, a, b, c = self._setup(api)
        in_target = lines_of(target)[0].rbwsl_id
        assert api.post(f'{BASE}/{source}/lines/move',
                        json={'line_ids': [a['id'], in_target], 'to_list_id': target,
                              'mode': 'move'}).status_code == 404
        _validation(api.post(f'{BASE}/{source}/lines/move',
                             json={'line_ids': [a['id']], 'to_list_id': source, 'mode': 'move'}),
                    'to_list_id')
        _validation(api.post(f'{BASE}/{source}/lines/move',
                             json={'line_ids': [], 'to_list_id': target, 'mode': 'move'}))
        _validation(api.post(f'{BASE}/{source}/lines/move',
                             json={'line_ids': [a['id']], 'to_list_id': target, 'mode': 'x'}))
        assert len(lines_of(source)) == 3


# --- the read model --------------------------------------------------------------------------

class TestLinesRead:
    def test_items_in_added_order_with_meta(self, api):
        default = default_list(api)
        a = add(api, default, **printing('2', qty=2))['line']
        b = add(api, default, **printing('1', foil='N', qty=3))['line']
        resp = api.get(f'{BASE}/{default}/lines')
        body = resp.get_json()
        assert [item['id'] for item in body['data']['items']] == [a['id'], b['id']]
        assert body['meta'] == {'total': 2, 'line_count': 2, 'max_lines': 100,
                                'market_total': 30.0, 'unpriced': 1}

    def test_q_filters_by_name(self, api):
        default = default_list(api)
        add(api, default, **printing('2'))
        jinx = add(api, default, **printing('79'))['line']
        body = api.get(f'{BASE}/{default}/lines?q=LOOSE').get_json()
        assert [item['id'] for item in body['data']['items']] == [jinx['id']]
        assert (body['meta']['total'], body['meta']['line_count']) == (1, 2)

    @pytest.mark.parametrize('target, value, source, where', [
        (printing('1', foil='N'), 10.0, 'avg7', ('OGN', '1', False)),
        (printing('1', foil='S'), 30.0, 'avg7_foil', ('OGN', '1', True)),
        (printing('1', foil='any'), 10.0, 'avg7', ('OGN', '1', False)),
        (printing('79'), 20.0, 'avg7', ('OGN', '79', False)),
        ({'name': 'Alpha Fury'}, 4.0, 'avg7', ('SFD', '5', False)),   # the cheapest printing
    ])
    def test_market(self, api, target, value, source, where):
        default = default_list(api)
        line = add(api, default, **target)['line']
        assert line['market'] == {'value': value, 'source': source, 'as_of': '2026-10-20',
                                  'set_id': where[0], 'card_id': where[1], 'foil': where[2]}

    def test_market_is_null_without_a_price(self, api):
        default = default_list(api)
        line = add(api, default, **printing('2', max_price=1))['line']
        assert line['market'] is None and line['reached'] is False

    @pytest.mark.parametrize('max_price, reached', [(None, None), (9.99, False), (10, True),
                                                    (10.01, True)])
    def test_reached(self, api, max_price, reached):
        default = default_list(api)
        line = add(api, default, **printing('1', foil='N', max_price=max_price))['line']
        assert line['reached'] is reached

    def test_owned_indicators(self, api, other):
        own('1', 3)
        own('1', 1, foil='S')
        own('1a', 2)
        own('5', 1, set_id='SFD', foil='S')
        own('1', 9, user='otheruser')
        default = default_list(api)
        base = add(api, default, **printing('1'))['line']
        alt = add(api, default, **printing('1a'))['line']
        by_name = add(api, default, name='Alpha Fury')['line']
        jinx = add(api, default, **printing('79'))['line']
        assert base['owned'] == {'this_version': {'total': 4, 'foil': 1},
                                 'other_versions': {'total': 3, 'alt_art': 3, 'foil': 1}}
        assert alt['owned'] == {'this_version': {'total': 2, 'foil': 0},
                                'other_versions': {'total': 5, 'alt_art': 1, 'foil': 2}}
        assert by_name['owned'] == {'this_version': {'total': 7, 'foil': 2},
                                    'other_versions': {'total': 0, 'alt_art': 0, 'foil': 0}}
        assert jinx['owned'] == {'this_version': {'total': 0, 'foil': 0},
                                 'other_versions': {'total': 0, 'alt_art': 0, 'foil': 0}}
        items = api.get(f'{BASE}/{default}/lines').get_json()['data']['items']
        assert [item['owned'] for item in items] == \
            [base['owned'], alt['owned'], by_name['owned'], jinx['owned']]
        assert base['card']['owned_total'] == 4

    def test_the_number_of_statements_does_not_grow_with_the_lines(self, app, api):
        default = default_list(api)
        own('1', 1)
        add(api, default, **printing('1'))
        few = _count(app, lambda: api.get(f'{BASE}/{default}/lines'))
        for card_id in seed_fillers(8):
            add(api, default, **printing(card_id, max_price=1))
            own(card_id, 2)
        add(api, default, name='Beta Calm')
        add(api, default, **printing('1a', foil='S'))
        many = _count(app, lambda: api.get(f'{BASE}/{default}/lines'))
        assert few == many
        assert many == 7   # list, lines, cards, sets, price mapping, prices, copies

    def test_the_lists_are_two_statements(self, app, api):
        default = default_list(api)
        new_list(api, 'Trades')
        add(api, default, **printing('1'))
        assert _count(app, lambda: api.get(BASE)) == 2   # lists, line counts


def _count(app, call):
    """SELECT statements of one request, without the session's user lookup."""
    counted = []

    def before(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith('SELECT') and 'rbusers' not in statement:
            counted.append(statement)

    event.listen(db.engine, 'before_cursor_execute', before)
    try:
        resp = call()
    finally:
        event.remove(db.engine, 'before_cursor_execute', before)
    assert resp.status_code == 200
    return len(counted)


# --- ownership and authentication ------------------------------------------------------------

def _routes(list_id, line_id, target_id):
    return [
        ('patch', f'{BASE}/{list_id}', {'name': 'Mine'}),
        ('delete', f'{BASE}/{list_id}', None),
        ('get', f'{BASE}/{list_id}/lines', None),
        ('post', f'{BASE}/{list_id}/lines', printing('1')),
        ('patch', f'{BASE}/{list_id}/lines/{line_id}', {'qty': 5}),
        ('delete', f'{BASE}/{list_id}/lines/{line_id}', None),
        ('post', f'{BASE}/{list_id}/lines/move',
         {'line_ids': [line_id], 'to_list_id': target_id, 'mode': 'move'}),
    ]


class TestOwnership:
    def test_another_users_list_and_lines_are_404_everywhere(self, api, other):
        theirs = default_list(other)
        their_second = new_list(other, 'Trades')
        line = add(other, their_second, **printing('1'))['line']
        mine = default_list(api)
        for method, url, body in _routes(their_second, line['id'], mine):
            resp = getattr(api, method)(url, json=body) if body else getattr(api, method)(url)
            assert resp.status_code == 404, (method, url)
            assert resp.get_json() == NOT_FOUND
        # Their line under my list, and my move into their list.
        mine_line = add(api, mine, **printing('2'))['line']
        assert api.patch(f'{BASE}/{mine}/lines/{line["id"]}', json={'qty': 2}).status_code == 404
        assert api.delete(f'{BASE}/{mine}/lines/{line["id"]}').status_code == 404
        assert api.post(f'{BASE}/{mine}/lines/move',
                        json={'line_ids': [mine_line['id']], 'to_list_id': theirs,
                              'mode': 'copy'}).status_code == 404
        assert len(lines_of(their_second)) == 1 and lines_of(their_second)[0].rbwsl_qty == 1
        assert [row.rbwls_name for row in lists_of('otheruser')] == ['Wishlist', 'Trades']
        assert len(lines_of(theirs)) == 0

    def test_a_line_under_another_list_of_mine_is_a_404(self, api):
        default = default_list(api)
        second = new_list(api, 'Trades')
        line = add(api, default, **printing('1'))['line']
        assert api.patch(f'{BASE}/{second}/lines/{line["id"]}', json={'qty': 2}).status_code \
            == 404
        assert api.delete(f'{BASE}/{second}/lines/{line["id"]}').status_code == 404

    def test_anonymous_gets_401_everywhere(self, client, app):
        seed_catalog()
        for method, url, body in [('get', BASE, None), ('post', BASE, {'name': 'x'}),
                                  ('put', f'{BASE}/order', {'ids': [1]}),
                                  *_routes(1, 1, 2)]:
            resp = getattr(client, method)(url, json=body) if body else \
                getattr(client, method)(url)
            assert resp.status_code == 401, (method, url)
        assert RbWishlist.query.count() == 0
