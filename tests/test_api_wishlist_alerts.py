"""F4-g-2: wishlist price alerts API: GET /wishlist-alerts, GET /wishlist-alerts/<id>/lists,
POST /wishlist-alerts/read (docs/api.md "Wishlist alerts (F4-g-2)")."""
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy import event

from app import db
from app.models import RbWishlistAlert
from app.services.bans import name_key
from tests.conftest import login_as
from tests.wishlist_helpers import (NOT_FOUND, add, default_list, error, new_list, own,
                                    printing, seed_catalog, user_id)

BASE = '/riftbound/api/v1/wishlist-alerts'
WISHLISTS = '/riftbound/api/v1/wishlists'
ALERT_KEYS = ['id', 'name', 'card', 'set_id', 'card_id', 'price', 'max_price', 'price_date',
              'created_at', 'read_at']
LIST_KEYS = ['id', 'name', 'is_default', 'qty', 'max_price']
T0 = datetime(2026, 10, 20, 7, 0)


@pytest.fixture
def api(app, authenticated_client, make_user):
    make_user('otheruser')
    seed_catalog()
    return authenticated_client


@pytest.fixture
def other(app, api):
    return login_as(app.test_client(), 'otheruser')


def alert(card_id='1', *, user='testuser', set_id='OGN', name=None, price=10, max_price=10,
          day=date(2026, 10, 20), created=T0, read_at=None):
    """An alert row as the job writes it; `name` makes it a by-name alert."""
    shown = name or {'1': 'Alpha Fury', '79': 'Jinx, Loose Cannon', '2': 'Beta Calm'}[card_id]
    row = RbWishlistAlert(
        rbwal_user_id=user_id(user), rbwal_name_key=name_key(shown), rbwal_name=shown,
        rbwal_rbset_id=None if name else set_id, rbwal_rbcar_id=None if name else card_id,
        rbwal_price=Decimal(str(price)), rbwal_max_price=Decimal(str(max_price)),
        rbwal_price_date=day, rbwal_created_at=created, rbwal_read_at=read_at)
    db.session.add(row)
    db.session.commit()
    return row.rbwal_id


def body(resp, status=200):
    assert resp.status_code == status, resp.get_json()
    payload = resp.get_json()
    assert payload['success'] is True
    return payload


def unread_ids():
    db.session.expire_all()
    return sorted(row.rbwal_id for row in db.session.execute(sa.select(RbWishlistAlert).where(
        RbWishlistAlert.rbwal_read_at.is_(None))).scalars())


class TestList:
    def test_shape_of_an_item(self, api):
        own('1', 2)
        alert_id = alert('1', price=9.5, max_price=10)
        payload = body(api.get(BASE))
        item = payload['data']['items'][0]
        assert list(item) == ALERT_KEYS
        assert {k: v for k, v in item.items() if k != 'card'} == {
            'id': alert_id, 'name': 'Alpha Fury', 'set_id': 'OGN', 'card_id': '1',
            'price': 9.5, 'max_price': 10.0, 'price_date': '2026-10-20',
            'created_at': '2026-10-20T07:00:00Z', 'read_at': None}
        card = item['card']
        assert (card['set_id'], card['card_id'], card['name'], card['market'],
                card['owned_total'], card['is_base']) == ('OGN', '1', 'Alpha Fury', 10.0, 2, True)
        assert payload['meta'] == {'page': 1, 'per_page': 25, 'total': 1, 'pages': 1,
                                   'unread_count': 1}

    def test_a_by_name_alert_shows_the_base_printing(self, api):
        alert(name='Alpha Fury', price=4, max_price=5)
        item = body(api.get(BASE))['data']['items'][0]
        assert (item['set_id'], item['card_id']) == (None, None)
        assert (item['card']['set_id'], item['card']['card_id']) == ('OGN', '1')

    def test_a_card_that_left_the_catalog_has_no_card(self, api):
        alert('1', set_id='ZZZ')
        assert body(api.get(BASE))['data']['items'][0]['card'] is None

    def test_newest_first(self, api):
        older = alert('1', created=T0)
        newer = alert('79', created=T0 + timedelta(days=1), day=date(2026, 10, 21))
        same_time = alert('2', created=T0 + timedelta(days=1), day=date(2026, 10, 21))
        ids = [item['id'] for item in body(api.get(BASE))['data']['items']]
        assert ids == [same_time, newer, older]

    def test_empty(self, api):
        payload = body(api.get(BASE))
        assert payload['data'] == {'items': []}
        assert payload['meta'] == {'page': 1, 'per_page': 25, 'total': 0, 'pages': 0,
                                   'unread_count': 0}

    def test_paging(self, api):
        ids = [alert('1', day=date(2026, 1, 1) + timedelta(days=n),
                     created=T0 + timedelta(minutes=n)) for n in range(30)]
        first = body(api.get(f'{BASE}?per_page=25'))
        second = body(api.get(f'{BASE}?page=2&per_page=25'))
        assert [i['id'] for i in first['data']['items']] == ids[::-1][:25]
        assert [i['id'] for i in second['data']['items']] == ids[::-1][25:]
        assert second['meta'] == {'page': 2, 'per_page': 25, 'total': 30, 'pages': 2,
                                  'unread_count': 30}
        assert body(api.get(f'{BASE}?page=3'))['data']['items'] == []

    @pytest.mark.parametrize('query, field', [('per_page=10', 'per_page'),
                                              ('per_page=x', 'per_page'),
                                              ('page=0', 'page'), ('unread=maybe', 'unread')])
    def test_invalid_query(self, api, query, field):
        payload = error(api.get(f'{BASE}?{query}'), 400, 'validation_error')
        assert field in {detail['field'] for detail in payload['details']}

    def test_unread_filter(self, api):
        read = alert('1', read_at=T0)
        unread = alert('79')
        payload = body(api.get(f'{BASE}?unread=true'))
        assert [i['id'] for i in payload['data']['items']] == [unread]
        assert (payload['meta']['total'], payload['meta']['unread_count']) == (1, 1)
        everything = body(api.get(f'{BASE}?unread=false'))
        assert {i['id'] for i in everything['data']['items']} == {read, unread}
        assert (everything['meta']['total'], everything['meta']['unread_count']) == (2, 1)
        read_item = next(i for i in everything['data']['items'] if i['id'] == read)
        assert read_item['read_at'] == '2026-10-20T07:00:00Z'

    def test_never_shows_another_users_alerts(self, api):
        alert('1', user='otheruser')
        mine = alert('79')
        payload = body(api.get(BASE))
        assert [i['id'] for i in payload['data']['items']] == [mine]
        assert payload['meta']['unread_count'] == 1

    def test_statements(self, app, api):
        assert _count(app, lambda: api.get(f'{BASE}?unread=true&per_page=25')) == 2
        alert('1')
        few = _count(app, lambda: api.get(BASE))
        for n in range(10):
            alert('79', day=date(2026, 1, 1) + timedelta(days=n))
        alert(name='Alpha Fury')
        many = _count(app, lambda: api.get(BASE))
        assert few == many
        assert many == 7   # counts, page, cards, sets, price mapping, prices, copies


class TestLists:
    def test_lists_holding_the_printing_now_in_list_order(self, api):
        default = default_list(api)
        trades = new_list(api, 'Trades')
        spare = new_list(api, 'Spare')
        add(api, trades, **printing('1', foil='N', qty=2, max_price=10))
        add(api, trades, **printing('1', foil='S', qty=1, max_price=8))
        add(api, default, name='Alpha Fury', qty=3)            # by-name: holds it too
        add(api, spare, **printing('1a'))                      # another printing: not it
        alert_id = alert('1')
        items = body(api.get(f'{BASE}/{alert_id}/lists'))['data']['items']
        assert [list(item) for item in items] == [LIST_KEYS, LIST_KEYS]
        assert items == [
            {'id': default, 'name': 'Wishlist', 'is_default': True, 'qty': 3, 'max_price': None},
            {'id': trades, 'name': 'Trades', 'is_default': False, 'qty': 3, 'max_price': 8.0}]

    def test_a_by_name_alert_matches_every_printing_of_the_name(self, api):
        default = default_list(api)
        spare = new_list(api, 'Spare')
        add(api, spare, **printing('1a', max_price=60))
        add(api, default, **printing('79'))
        alert_id = alert(name='Alpha Fury')
        items = body(api.get(f'{BASE}/{alert_id}/lists'))['data']['items']
        assert [(i['id'], i['qty'], i['max_price']) for i in items] == [(spare, 1, 60.0)]

    def test_a_deleted_list_is_not_listed(self, api):
        default = default_list(api)
        trades = new_list(api, 'Trades')
        add(api, default, **printing('1'))
        add(api, trades, **printing('1'))
        alert_id = alert('1')
        body(api.delete(f'{WISHLISTS}/{trades}'))
        items = body(api.get(f'{BASE}/{alert_id}/lists'))['data']['items']
        assert [i['id'] for i in items] == [default]

    def test_no_list_holds_it_any_more(self, api):
        default_list(api)
        alert_id = alert('1')
        assert body(api.get(f'{BASE}/{alert_id}/lists'))['data'] == {'items': []}

    def test_never_lists_another_users_lists(self, api, other):
        add(other, default_list(other), **printing('1'))
        alert_id = alert('1')
        assert body(api.get(f'{BASE}/{alert_id}/lists'))['data'] == {'items': []}

    def test_two_statements(self, app, api):
        default = default_list(api)
        add(api, default, **printing('1'))
        alert_id = alert('1')
        assert _count(app, lambda: api.get(f'{BASE}/{alert_id}/lists')) == 2


class TestRead:
    def test_marks_the_ids_sent(self, api):
        first, second, third = alert('1'), alert('79'), alert('2')
        payload = body(api.post(f'{BASE}/read', json={'ids': [first, third]}))
        assert payload['data'] == {'marked': 2}
        assert unread_ids() == [second]
        row = db.session.get(RbWishlistAlert, first)
        assert row.rbwal_read_at is not None

    @pytest.mark.parametrize('sent', [{}, {'ids': []}, {'ids': None}])
    def test_absent_or_empty_ids_mark_all_of_mine(self, api, sent):
        alert('1')
        alert('79')
        theirs = alert('1', user='otheruser')
        assert body(api.post(f'{BASE}/read', json=sent))['data'] == {'marked': 2}
        assert unread_ids() == [theirs]

    def test_already_read_unknown_and_foreign_ids_are_ignored(self, api, frozen_clock):
        read = alert('1', read_at=T0)
        theirs = alert('79', user='otheruser')
        mine = alert('2')
        payload = body(api.post(f'{BASE}/read', json={'ids': [read, theirs, mine, 999999]}))
        assert payload['data'] == {'marked': 1}
        assert unread_ids() == [theirs]
        db.session.expire_all()
        assert db.session.get(RbWishlistAlert, read).rbwal_read_at == T0   # kept
        assert db.session.get(RbWishlistAlert, mine).rbwal_read_at == frozen_clock()

    @pytest.mark.parametrize('sent', [{'ids': 'all'}, {'ids': [0]}, {'ids': ['1']},
                                      {'ids': list(range(1, 502))}])
    def test_invalid_bodies(self, api, sent):
        alert('1')
        error(api.post(f'{BASE}/read', json=sent), 400, 'validation_error')
        assert len(unread_ids()) == 1

    def test_the_unread_count_follows(self, api):
        alert('1')
        alert('79')
        body(api.post(f'{BASE}/read', json={}))
        assert body(api.get(f'{BASE}?unread=true'))['meta']['unread_count'] == 0


class TestOwnershipAndAuth:
    def test_another_users_alert_lists_are_404(self, api):
        theirs = alert('1', user='otheruser')
        resp = api.get(f'{BASE}/{theirs}/lists')
        assert resp.status_code == 404 and resp.get_json() == NOT_FOUND
        assert api.get(f'{BASE}/999999/lists').status_code == 404

    def test_anonymous_gets_401_everywhere(self, client, app):
        for method, url, sent in [('get', BASE, None), ('get', f'{BASE}/1/lists', None),
                                  ('post', f'{BASE}/read', {})]:
            resp = getattr(client, method)(url, json=sent) if sent is not None else \
                getattr(client, method)(url)
            assert resp.status_code == 401, (method, url)


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
