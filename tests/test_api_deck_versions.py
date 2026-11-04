"""F5-d S7-S14: PUT /decks/<id>/content (hard limits, soft rules), versions (list, snapshot,
one version, restore), diff, and the owner-only / signed-in-only guard of every deck route."""
import pytest

from app import db
from app.models import RbCard, RbDeckHead, RbDeckVersion
from app.schemas.deck_content import empty_content
from tests.deck_api_helpers import (AZIR, BASE, NOT_FOUND, WHEN, content, data, error,
                                    head_row, line, make_deck, ref, seed_catalog, versions)

VERSION_KEYS = ['seq', 'note', 'created_at', 'is_current']
VERSION_DETAIL_KEYS = VERSION_KEYS + ['content', 'cards', 'unknown_cards', 'domains', 'counts',
                                      'value', 'value_unpriced', 'legality']
ZONES = ['legend', 'champion', 'main', 'runes', 'battlefields', 'sideboard', 'workbench']
NOW = '2030-01-01T12:00:00Z'


@pytest.fixture
def api(app, authenticated_client, make_user):
    make_user('otheruser')
    seed_catalog()
    return authenticated_client


def add_version(deck_id, seq, body, current=True):
    version = RbDeckVersion(rbdkv_deck_id=deck_id, rbdkv_seq=seq, rbdkv_content=body,
                            rbdkv_created_at=WHEN)
    db.session.add(version)
    db.session.flush()
    if current:
        db.session.get(RbDeckHead, deck_id).rbdkh_current_version_id = version.rbdkv_id
    db.session.commit()


def put(api, deck_id, body):
    return api.put(f'{BASE}/{deck_id}/content', json={'content': body})


def unchanged(deck_id, before):
    head = head_row(deck_id)
    assert (head.rbdkh_updated_at, head.rbdkh_current_version_id) == before[0]
    assert versions(deck_id) == before[1]


def state(deck_id):
    head = head_row(deck_id)
    return (head.rbdkh_updated_at, head.rbdkh_current_version_id), versions(deck_id)


class TestPutContent:
    def test_saves_the_current_version_in_place(self, api, frozen_clock):
        deck_id = make_deck('Azir', seqs=(1, 2))
        deck = data(put(api, deck_id, AZIR))
        assert deck['current_seq'] == 2 and deck['content'] == AZIR
        assert deck['updated_at'] == NOW and deck['created_at'] == '2026-10-01T09:00:00Z'
        assert deck['counts']['main'] == 6 and deck['legality']['1v1']['legal'] is False
        assert versions(deck_id) == [(1, empty_content(), None), (2, AZIR, None)]
        assert head_row(deck_id).rbdkh_updated_at == frozen_clock.now

    def test_a_missing_zone_is_saved_empty(self, api):
        deck_id = make_deck('Azir')
        deck = data(put(api, deck_id, {'v': 2, 'main': [line('OGN', 'U1', 2)]}))
        assert deck['content'] == content(main=[line('OGN', 'U1', 2)])
        assert versions(deck_id)[0][1] == content(main=[line('OGN', 'U1', 2)])

    def test_soft_rules_never_block_and_come_back_as_issues(self, api):
        deck_id = make_deck('Azir')
        body = content(legend=ref('OGN', 'L1'), main=[line('OGN', 'F1', 1)],
                       battlefields=[ref('OGN', 'B1'), ref('OGN', 'B1')],
                       runes=[line('OGN', 'R1', 2)], sideboard=[line('OGN', 'U2', 1)])
        deck = data(put(api, deck_id, body))
        codes = [i['code'] for i in deck['legality']['1v1']['issues']]
        assert codes == ['champion_missing', 'main_size', 'runes_count', 'battlefields_count',
                         'battlefields_duplicate', 'sideboard_size', 'card_off_identity']
        assert versions(deck_id)[0][1] == body

    @pytest.mark.parametrize('body, params, message', [
        (content(main=[line('OGN', 'U1', 2), line('SFD', 'U1', 1)],
                 workbench=[line('SFD', 'U1', 1)]),
         {'rule': 'copies', 'max': 3, 'name': 'Shurima Guard'},
         'copies (max 3) ("Shurima Guard")'),
        (content(sideboard=[line('OGN', 'U1', 3), line('OGN', 'U2', 3), line('OGN', 'S1', 3),
                            line('OGN', 'F1', 2)]),
         {'rule': 'sideboard', 'max': 10}, 'sideboard (max 10)'),
        (content(battlefields=[ref('OGN', f'B{n}') for n in range(1, 5)]),
         {'rule': 'battlefields', 'max': 3}, 'battlefields (max 3)'),
        (content(runes=[line('OGN', 'R1', 7), line('OGN', 'R2', 6)]),
         {'rule': 'runes', 'max': 12}, 'runes (max 12)'),
        (content(sideboard=[line('OGN', 'T1', 1)]),
         {'rule': 'token', 'max': 0, 'name': 'Sand Soldier'}, 'token (max 0) ("Sand Soldier")'),
    ])
    def test_a_hard_limit_is_400_and_stores_nothing(self, api, frozen_clock, body, params,
                                                    message):
        deck_id = make_deck('Azir', AZIR)
        before = state(deck_id)
        resp = error(put(api, deck_id, body), 400, 'deck_limit_exceeded')
        assert resp['params'] == params
        assert resp['message'] == f'The deck goes over a limit: {message}.'
        assert resp['error'] == 'Validation Error'
        unchanged(deck_id, before)

    def test_more_than_100_workbench_names_is_a_hard_limit(self, api):
        db.session.add_all([RbCard(rbcar_rbset_id='OGN', rbcar_id=f'W{n}', rbcar_name=f'Bench {n}',
                                   rbcar_type='Unit', rbcar_domain='Calm') for n in range(101)])
        db.session.commit()
        deck_id = make_deck('Azir')
        bench = [line('OGN', f'W{n}') for n in range(100)]
        data(put(api, deck_id, content(workbench=bench)))
        resp = error(put(api, deck_id, content(workbench=bench + [line('OGN', 'W100')])), 400,
                     'deck_limit_exceeded')
        assert resp['params'] == {'rule': 'workbench', 'max': 100}
        assert len(versions(deck_id)[0][1]['workbench']) == 100

    def test_every_limit_is_named_and_the_first_is_the_params(self, api):
        deck_id = make_deck('Azir')
        resp = error(put(api, deck_id, content(
            main=[line('OGN', 'T1', 1), line('OGN', 'U2', 4)],
            runes=[line('OGN', 'R1', 13)])), 400, 'deck_limit_exceeded')
        assert resp['params'] == {'rule': 'copies', 'max': 3, 'name': 'Desert Scout'}
        assert resp['message'] == ('The deck goes over a limit: copies (max 3) ("Desert Scout"); '
                                   'runes (max 12); token (max 0) ("Sand Soldier").')

    def test_an_unknown_card_is_a_validation_error(self, api):
        deck_id = make_deck('Azir', AZIR)
        before = state(deck_id)
        resp = error(put(api, deck_id, content(legend=ref('XXX', 'L'),
                                               main=[line('OGN', 'U1'), line('XXX', '9', 2)])),
                     400, 'validation_error')
        assert resp['details'] == [
            {'field': 'content.legend', 'message': 'unknown card XXX-L', 'type': 'value_error',
             'code': 'invalid_value'},
            {'field': 'content.main.1', 'message': 'unknown card XXX-9', 'type': 'value_error',
             'code': 'invalid_value'}]
        unchanged(deck_id, before)

    @pytest.mark.parametrize('body, field', [
        ({}, 'content'),
        ({'content': {'main': []}}, 'content.v'),
        ({'content': {'v': 1}}, 'content.v'),
        ({'content': {'v': 2, 'main': [{'set': 'OGN', 'id': 'U1', 'qty': 0}]}},
         'content.main.0.qty'),
        ({'content': {'v': 2, 'main': [{'set': 'OGN', 'id': 'U1', 'qty': '2'}]}},
         'content.main.0.qty'),
        ({'content': {'v': 2, 'battlefields': [{'set': 'OGN', 'id': 'B1', 'qty': 1}]}},
         'content.battlefields.0.qty'),
        ({'content': {'v': 2, 'extra': []}}, 'content.extra'),
    ])
    def test_a_bad_shape_is_400_and_stores_nothing(self, api, body, field):
        deck_id = make_deck('Azir', AZIR)
        before = state(deck_id)
        resp = error(api.put(f'{BASE}/{deck_id}/content', json=body), 400, 'validation_error')
        assert [d['field'] for d in resp['details']] == [field]
        unchanged(deck_id, before)

    def test_a_save_moves_the_deck_to_the_top_of_the_list(self, api, frozen_clock):
        old = make_deck('Old')
        make_deck('New', at=WHEN.replace(day=2))
        data(put(api, old, AZIR))
        assert [item['name'] for item in data(api.get(BASE))['items']] == ['Old', 'New']


class TestVersions:
    def test_list_newest_first_with_the_current_one(self, api):
        deck_id = make_deck('Azir', seqs=(1, 2, 3))
        items = data(api.get(f'{BASE}/{deck_id}/versions'))['items']
        assert [list(item) for item in items] == [VERSION_KEYS] * 3
        assert [(i['seq'], i['note'], i['created_at'], i['is_current']) for i in items] == [
            (3, None, '2026-10-01T09:00:00Z', True), (2, None, '2026-10-01T09:00:00Z', False),
            (1, None, '2026-10-01T09:00:00Z', False)]

    def test_snapshot_adds_the_next_seq_and_makes_it_current(self, api, frozen_clock):
        deck_id = make_deck('Azir', AZIR, seqs=(1, 2))
        version = data(api.post(f'{BASE}/{deck_id}/versions', json={'note': '  Before cup '}),
                       201)
        assert list(version) == VERSION_DETAIL_KEYS
        assert (version['seq'], version['note'], version['created_at'],
                version['is_current']) == (3, 'Before cup', NOW, True)
        assert version['content'] == AZIR and version['counts']['main'] == 6
        assert list(version['legality']) == ['1v1', '2v2']
        assert versions(deck_id) == [(1, AZIR, None), (2, AZIR, None), (3, AZIR, 'Before cup')]
        head = head_row(deck_id)
        assert head.rbdkh_updated_at == frozen_clock.now
        assert data(api.get(f'{BASE}/{deck_id}'))['current_seq'] == 3
        # the next autosave edits the snapshot, the older versions stay as they were
        data(put(api, deck_id, content(main=[line('OGN', 'U1', 1)])))
        assert versions(deck_id)[:2] == [(1, AZIR, None), (2, AZIR, None)]
        assert versions(deck_id)[2][1] == content(main=[line('OGN', 'U1', 1)])

    @pytest.mark.parametrize('body', [{}, {'note': None}, {'note': '   '}])
    def test_snapshot_without_a_note(self, api, body):
        deck_id = make_deck('Azir')
        version = data(api.post(f'{BASE}/{deck_id}/versions', json=body), 201)
        assert (version['seq'], version['note']) == (2, None)

    def test_a_note_over_200_characters_is_400(self, api):
        deck_id = make_deck('Azir')
        resp = error(api.post(f'{BASE}/{deck_id}/versions', json={'note': 'x' * 201}), 400,
                     'validation_error')
        assert [(d['field'], d['code']) for d in resp['details']] == [('note', 'too_long')]
        assert len(versions(deck_id)) == 1

    def test_one_version_with_its_cards(self, api):
        deck_id = make_deck('Azir', AZIR)
        add_version(deck_id, 2, empty_content())
        version = data(api.get(f'{BASE}/{deck_id}/versions/1'))
        assert list(version) == VERSION_DETAIL_KEYS
        assert (version['seq'], version['is_current']) == (1, False)
        assert version['content'] == AZIR and 'OGN-L1' in version['cards']
        assert version['value'] == 21.8
        assert data(api.get(f'{BASE}/{deck_id}/versions/2'))['is_current'] is True

    def test_an_unknown_seq_is_404(self, api):
        deck_id = make_deck('Azir')
        for method, path in (('get', 'versions/9'), ('post', 'versions/9/restore'),
                             ('get', 'diff?a=1&b=9'), ('get', 'diff?a=9&b=1')):
            resp = getattr(api, method)(f'{BASE}/{deck_id}/{path}')
            assert resp.status_code == 404 and resp.get_json() == NOT_FOUND, path
        assert len(versions(deck_id)) == 1


class TestRestore:
    def test_copies_the_version_into_a_new_current_one(self, api, frozen_clock):
        deck_id = make_deck('Azir', AZIR)
        add_version(deck_id, 2, content(main=[line('OGN', 'U2', 1)]))
        version = data(api.post(f'{BASE}/{deck_id}/versions/1/restore'), 201)
        assert list(version) == VERSION_DETAIL_KEYS
        assert (version['seq'], version['note'], version['is_current'],
                version['created_at']) == (3, 'Restored from version 1.', True, NOW)
        assert version['content'] == AZIR
        assert versions(deck_id) == [(1, AZIR, None),
                                     (2, content(main=[line('OGN', 'U2', 1)]), None),
                                     (3, AZIR, 'Restored from version 1.')]
        assert head_row(deck_id).rbdkh_updated_at == frozen_clock.now
        assert data(api.get(f'{BASE}/{deck_id}'))['current_seq'] == 3


NEW = content(legend=ref('OGN', 'L1'),
              main=[line('OGN', 'U1', 3), line('OGN', 'S1', 3), line('OGN', 'F1', 1),
                    line('XXX', '9', 1)],
              runes=[line('OGN', 'R1', 12)], battlefields=[ref('OGN', 'B1'), ref('OGN', 'B3')],
              sideboard=[line('OGN', 'U2', 2)])


def entry(set_id, card_id, before, after):
    return {'set': set_id, 'id': card_id, 'before': before, 'after': after}


class TestDiff:
    def test_added_removed_and_changed_per_zone(self, api):
        deck_id = make_deck('Azir', AZIR)
        add_version(deck_id, 2, NEW)
        diff = data(api.get(f'{BASE}/{deck_id}/diff?a=1&b=2'))
        assert list(diff) == ['a', 'b', 'zones', 'cards']
        assert (diff['a'], diff['b']) == (1, 2)
        assert list(diff['zones']) == ZONES
        empty = {'added': [], 'removed': [], 'changed': []}
        assert diff['zones'] == {
            'legend': empty,
            'champion': {'added': [], 'removed': [entry('OGN', 'C1', 1, 0)], 'changed': []},
            'main': {'added': [entry('OGN', 'F1', 0, 1), entry('XXX', '9', 0, 1)],
                     'removed': [entry('SFD', 'U1', 1, 0)],
                     'changed': [entry('OGN', 'U1', 2, 3)]},
            'runes': {'added': [], 'removed': [entry('OGN', 'R2', 6, 0)],
                      'changed': [entry('OGN', 'R1', 6, 12)]},
            'battlefields': {'added': [entry('OGN', 'B3', 0, 1)],
                             'removed': [entry('OGN', 'B2', 1, 0)], 'changed': []},
            'sideboard': empty,
            'workbench': {'added': [], 'changed': [], 'removed': [
                entry('OGN', 'U2', 1, 0), entry('OGN', 'F1', 1, 0), entry('OGN', 'T1', 2, 0)]},
        }
        assert sorted(diff['cards']) == sorted(['OGN-C1', 'OGN-F1', 'SFD-U1', 'OGN-U1', 'OGN-R2',
                                                'OGN-R1', 'OGN-B3', 'OGN-B2', 'OGN-U2',
                                                'OGN-T1'])
        assert diff['cards']['OGN-C1']['name'] == 'Azir, Ascendant'
        back = data(api.get(f'{BASE}/{deck_id}/diff?a=2&b=1'))['zones']
        assert back['champion']['added'] == [entry('OGN', 'C1', 0, 1)]
        assert back['main']['changed'] == [entry('OGN', 'U1', 3, 2)]

    def test_a_version_against_itself_has_no_changes(self, api):
        deck_id = make_deck('Azir', AZIR)
        diff = data(api.get(f'{BASE}/{deck_id}/diff?a=1&b=1'))
        assert all(zone == {'added': [], 'removed': [], 'changed': []}
                   for zone in diff['zones'].values())
        assert diff['cards'] == {}

    @pytest.mark.parametrize('query, fields', [
        ('', ['a', 'b']), ('?a=1', ['b']), ('?a=0&b=1', ['a']), ('?a=x&b=1', ['a']),
    ])
    def test_bad_version_numbers_are_400(self, api, query, fields):
        deck_id = make_deck('Azir')
        resp = error(api.get(f'{BASE}/{deck_id}/diff{query}'), 400, 'validation_error')
        assert resp['message'] == 'Invalid query parameters'
        assert sorted(d['field'] for d in resp['details']) == fields


# Every deck route: (method, path under /decks/<id>, JSON body or None).
ROUTES = [
    ('get', '', None), ('patch', '', {'name': 'Mine'}), ('delete', '', None),
    ('put', '/content', {'content': empty_content()}), ('get', '/versions', None),
    ('post', '/versions', {}), ('get', '/versions/1', None),
    ('post', '/versions/1/restore', None), ('get', '/diff?a=1&b=1', None),
]


def call(client, method, path, body):
    kwargs = {'json': body} if body is not None else {}
    return getattr(client, method)(path, **kwargs)


class TestOwnerOnly:
    @pytest.mark.parametrize('method, path, body', ROUTES)
    def test_another_users_deck_is_404_and_stays_as_it_was(self, api, method, path, body):
        theirs = make_deck('Azir', AZIR, user='otheruser')
        before = state(theirs)
        resp = call(api, method, f'{BASE}/{theirs}{path}', body)
        assert resp.status_code == 404 and resp.get_json() == NOT_FOUND
        unchanged(theirs, before)
        assert head_row(theirs).rbdkh_name == 'Azir'

    @pytest.mark.parametrize('method, path, body', ROUTES)
    def test_an_unknown_id_is_404(self, api, method, path, body):
        resp = call(api, method, f'{BASE}/999{path}', body)
        assert resp.status_code == 404 and resp.get_json() == NOT_FOUND

    @pytest.mark.parametrize('method, path, body', ROUTES + [('get', None, None),
                                                              ('post', None, {'name': 'A',
                                                                              'mode': '1v1'})])
    def test_anonymous_gets_a_json_401(self, app, client, method, path, body):
        url = BASE if path is None else f'{BASE}/1{path}'
        resp = call(client, method, url, body)
        assert resp.status_code == 401
        body = resp.get_json()
        assert (body['success'], body['error'], body['code']) == (False, 'Unauthorized',
                                                                   'unauthenticated')
        assert RbDeckHead.query.count() == 0
