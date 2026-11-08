"""CM-e: the admin audit log, `GET /admin/audit` and `GET /admin/audit/facets`.

Read-only views of `rbadminaudit` (the rows every admin write records through
`app.services.audit.record`): filters, paging, newest first, the system actor and the
stored `details` passed through as they are."""
from datetime import datetime

import pytest
from sqlalchemy import event

from app import db
from app.models.audit import RbAdminAudit
from tests.test_authz_matrix import classify

URL = '/riftbound/api/v1/admin/audit'
FACETS = f'{URL}/facets'
JSON = {'Accept': 'application/json'}


def row(action, target_type, target_id=None, details=None, actor=None,
        at=datetime(2030, 1, 1, 12, 0)):
    """One audit row; `actor` is a user, or None for the system."""
    entry = RbAdminAudit(
        rbaud_actor_id=actor.id if actor else None,
        rbaud_actor_username=actor.username if actor else 'system',
        rbaud_action=action, rbaud_target_type=target_type, rbaud_target_id=target_id,
        rbaud_details=details, rbaud_created_at=at)
    db.session.add(entry)
    return entry


def data(resp, status=200):
    assert resp.status_code == status, resp.get_json()
    return resp.get_json()['data']


@pytest.fixture
def admin(app, admin_client):
    from app.models.user import User
    return User.query.filter_by(username='admin').one()


@pytest.fixture
def trail(app, admin, make_user):
    """Six rows over three days, two actors and the system."""
    other = make_user('editor', is_admin=True)
    row('cardmarket.link', 'cardmarket_product', '501',
        {'set_id': 'OGN', 'card_id': '001', 'foil': 'N'}, admin, datetime(2030, 1, 1, 9))
    row('cardmarket.unlink', 'cardmarket_product', '501',
        {'set_id': 'OGN', 'card_id': '001', 'foil': 'N', 'match_type': 'manual'}, admin,
        datetime(2030, 1, 1, 10))
    row('cardmarket.expansion.map', 'cardmarket_expansion', '6567',
        {'name': None, 'set_id': 'OGN', 'previous': None}, other, datetime(2030, 1, 2, 8))
    row('riot.apply', 'card', 'OGN-001', {'fields': {'name': ['A', 'B']}}, None,
        datetime(2030, 1, 2, 23, 59, 59))
    row('set.create', 'set', 'UNL', {'name': 'Unleashed', 'release_date': '2030-02-01'},
        admin, datetime(2030, 1, 3, 0, 0))
    row('cardmarket.auto_match', 'cardmarket', '20300103',
        {'linked': 3, 'clear': 4, 'doubtful': 1, 'max_groups': 50}, admin,
        datetime(2030, 1, 3, 7))
    db.session.commit()
    return {'admin': admin, 'other': other}


class TestAuthorization:
    def test_anonymous_401_user_403(self, app, authenticated_client):
        anonymous = app.test_client()
        for url in (URL, FACETS):
            assert anonymous.get(url, headers=JSON).status_code == 401
            assert authenticated_client.get(url, headers=JSON).status_code == 403

    def test_the_rules_are_admin_in_the_matrix(self, app):
        rules = [rule for rule in app.url_map.iter_rules() if rule.rule.startswith(URL)]
        assert {rule.endpoint for rule in rules} == {'api_admin.list_audit',
                                                     'api_admin.audit_facets'}
        assert {classify(rule) for rule in rules} == {'A'}


class TestList:
    def test_newest_first_with_the_item_shape(self, admin_client, trail):
        body = admin_client.get(URL).get_json()
        items = body['data']['items']
        assert [item['action'] for item in items] == [
            'cardmarket.auto_match', 'set.create', 'riot.apply', 'cardmarket.expansion.map',
            'cardmarket.unlink', 'cardmarket.link']
        admin = trail['admin']
        assert items[0] == {
            'id': items[0]['id'], 'created_at': '2030-01-03T07:00:00',
            'actor': {'id': admin.id, 'username': admin.username},
            'action': 'cardmarket.auto_match', 'target_type': 'cardmarket',
            'target_id': '20300103',
            'detail': {'linked': 3, 'clear': 4, 'doubtful': 1, 'max_groups': 50}}
        assert body['data']['meta'] == {'page': 1, 'per_page': 50, 'total': 6, 'pages': 1}

    def test_the_system_actor_is_null(self, admin_client, trail):
        items = data(admin_client.get(f'{URL}?action=riot.apply'))['items']
        assert len(items) == 1
        assert items[0]['actor'] is None
        assert items[0]['detail'] == {'fields': {'name': ['A', 'B']}}

    def test_a_deleted_user_keeps_the_stored_username(self, admin_client, trail):
        row('card.delete', 'card', 'OGN-002', None, None, datetime(2030, 1, 4))
        gone = RbAdminAudit.query.filter_by(rbaud_action='card.delete').one()
        gone.rbaud_actor_username = 'former'
        db.session.commit()
        item = data(admin_client.get(f'{URL}?action=card.delete'))['items'][0]
        assert item['actor'] == {'id': None, 'username': 'former'}
        assert item['detail'] is None
        assert item['target_id'] == 'OGN-002'

    def test_equal_times_newest_id_first(self, admin_client, admin):
        same = datetime(2030, 1, 5, 12)
        first = row('set.update', 'set', 'A', None, admin, same)
        second = row('set.update', 'set', 'B', None, admin, same)
        db.session.commit()
        ids = [item['id'] for item in data(admin_client.get(URL))['items']]
        assert ids == [second.rbaud_id, first.rbaud_id]

    def test_details_are_passed_through_as_stored(self, admin_client, admin):
        stored = {'from': {'set_id': 'OGN', 'card_id': '001', 'foil': None},
                  'to': {'set_id': 'OGN', 'card_id': '002', 'foil': 'S'},
                  'list': [1, 'two', None], 'nested': {'deep': {'n': 1.5}}}
        row('cardmarket.relink', 'cardmarket_product', '7', stored, admin)
        row('cardmarket.ignore', 'cardmarket_product', '8', ['odd', 'shape'], admin,
            datetime(2030, 1, 1, 13))
        db.session.commit()
        by_target = {item['target_id']: item['detail']
                     for item in data(admin_client.get(URL))['items']}
        assert by_target == {'7': stored, '8': ['odd', 'shape']}

    def test_a_real_admin_write_is_listed(self, admin_client, admin, frozen_clock):
        resp = admin_client.post('/riftbound/api/v1/admin/sets', json={
            'id': 'NEW', 'name': 'New set', 'release_date': '2030-03-01'})
        assert resp.status_code == 201
        item = data(admin_client.get(URL))['items'][0]
        assert item['action'] == 'set.create'
        assert item['target_type'] == 'set'
        assert item['target_id'] == 'NEW'
        assert item['actor'] == {'id': admin.id, 'username': admin.username}
        assert item['detail'] == {'name': 'New set', 'release_date': '2030-03-01'}
        assert item['created_at'] == '2030-01-01T12:00:00'

    def test_an_empty_log(self, admin_client):
        body = data(admin_client.get(URL))
        assert body == {'items': [], 'meta': {'page': 1, 'per_page': 50, 'total': 0,
                                              'pages': 1}}


class TestFilters:
    def _actions(self, client, query):
        return [item['action'] for item in data(client.get(f'{URL}?{query}'))['items']]

    def test_action_is_exact(self, admin_client, trail):
        assert self._actions(admin_client, 'action=cardmarket.link') == ['cardmarket.link']
        assert self._actions(admin_client, 'action=cardmarket') == []

    def test_target_type_and_target_id(self, admin_client, trail):
        assert self._actions(admin_client, 'target_type=cardmarket_product') == [
            'cardmarket.unlink', 'cardmarket.link']
        assert self._actions(admin_client, 'target_type=card&target_id=OGN-001') == [
            'riot.apply']
        assert self._actions(admin_client, 'target_id=501') == [
            'cardmarket.unlink', 'cardmarket.link']

    def test_actor_is_a_case_insensitive_substring_and_system_matches(
            self, admin_client, trail):
        assert self._actions(admin_client, 'actor=EDIT') == ['cardmarket.expansion.map']
        assert self._actions(admin_client, 'actor=system') == ['riot.apply']
        assert self._actions(admin_client, 'actor=%25') == []
        assert self._actions(admin_client, 'actor=_') == []

    def test_dates_are_inclusive_utc_days(self, admin_client, trail):
        assert self._actions(admin_client, 'from=2030-01-02&to=2030-01-02') == [
            'riot.apply', 'cardmarket.expansion.map']
        assert self._actions(admin_client, 'from=2030-01-03') == [
            'cardmarket.auto_match', 'set.create']
        assert self._actions(admin_client, 'to=2030-01-01') == [
            'cardmarket.unlink', 'cardmarket.link']

    def test_filters_combine_and_meta_counts_the_filtered_rows(self, admin_client, trail):
        body = data(admin_client.get(f'{URL}?target_type=cardmarket_product&actor=adm'))
        assert body['meta']['total'] == 2
        body = data(admin_client.get(f'{URL}?target_type=cardmarket_product&actor=editor'))
        assert body['meta']['total'] == 0

    @pytest.mark.parametrize('query', [
        'per_page=25', 'per_page=abc', 'page=0', 'page=-1', 'from=2030-13-01',
        'to=yesterday', 'from=2030-01-03&to=2030-01-02', 'unknown=1', f'actor={"a" * 65}',
    ])
    def test_a_bad_query_is_400(self, admin_client, query):
        resp = admin_client.get(f'{URL}?{query}')
        assert resp.status_code == 400
        body = resp.get_json()
        assert body['code'] == 'validation_error'
        assert body['message'] == 'Invalid query parameters'

    def test_from_after_to_names_the_field(self, admin_client):
        body = admin_client.get(f'{URL}?from=2030-01-03&to=2030-01-02').get_json()
        assert [detail['field'] for detail in body['details']] == ['to']


class TestPaging:
    @pytest.fixture
    def many(self, app, admin):
        for n in range(120):
            row('set.update', 'set', f'S{n:03}', {'n': n}, admin,
                datetime(2030, 1, 1, n // 60, n % 60))
        db.session.commit()

    def test_pages_of_50_100_200(self, admin_client, many):
        body = data(admin_client.get(f'{URL}?page=2'))
        assert body['meta'] == {'page': 2, 'per_page': 50, 'total': 120, 'pages': 3}
        assert [item['target_id'] for item in body['items']][:2] == ['S069', 'S068']
        assert len(data(admin_client.get(f'{URL}?page=3'))['items']) == 20
        body = data(admin_client.get(f'{URL}?per_page=100&page=2'))
        assert len(body['items']) == 20
        assert body['meta']['pages'] == 2
        body = data(admin_client.get(f'{URL}?per_page=200'))
        assert len(body['items']) == 120
        assert body['meta']['pages'] == 1

    def test_a_page_past_the_end_is_empty(self, admin_client, many):
        body = data(admin_client.get(f'{URL}?page=9'))
        assert body['items'] == []
        assert body['meta']['total'] == 120


class TestFacets:
    def test_actions_and_target_types_with_counts(self, admin_client, trail):
        assert data(admin_client.get(FACETS)) == {
            'actions': [
                {'action': 'cardmarket.auto_match', 'count': 1},
                {'action': 'cardmarket.expansion.map', 'count': 1},
                {'action': 'cardmarket.link', 'count': 1},
                {'action': 'cardmarket.unlink', 'count': 1},
                {'action': 'riot.apply', 'count': 1},
                {'action': 'set.create', 'count': 1}],
            'target_types': [
                {'target_type': 'card', 'count': 1},
                {'target_type': 'cardmarket', 'count': 1},
                {'target_type': 'cardmarket_expansion', 'count': 1},
                {'target_type': 'cardmarket_product', 'count': 2},
                {'target_type': 'set', 'count': 1}]}

    def test_empty(self, admin_client):
        assert data(admin_client.get(FACETS)) == {'actions': [], 'target_types': []}

    def test_facets_take_no_parameters(self, admin_client):
        assert admin_client.get(f'{FACETS}?action=x').status_code == 400


class TestQueryBounds:
    def _selects(self, client, url):
        counted = []

        def before(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith('SELECT') and 'rbusers' not in statement:
                counted.append(statement)

        event.listen(db.engine, 'before_cursor_execute', before)
        try:
            assert client.get(url).status_code == 200
        finally:
            event.remove(db.engine, 'before_cursor_execute', before)
        return counted

    def test_the_list_is_two_statements_whatever_the_page(self, admin_client, admin):
        for n in range(60):
            row('set.update', 'set', f'S{n}', {'n': n}, admin)
        db.session.commit()
        assert len(self._selects(admin_client, f'{URL}?per_page=200')) == 2
        assert len(self._selects(admin_client, f'{URL}?actor=adm&action=set.update'
                                               '&from=2030-01-01&to=2030-01-01')) == 2

    def test_the_facets_are_two_statements(self, admin_client, trail):
        assert len(self._selects(admin_client, FACETS)) == 2
