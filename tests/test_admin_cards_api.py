"""F13-b S6-S8, S10 (AC2): cards admin API."""
from datetime import date

import pytest
from sqlalchemy import event

from app import db
from app.models.audit import RbAdminAudit
from app.models.card import RbCard
from app.models.collection import RbCollection
from app.models.deck_v2 import RbDeckVersion
from app.models.set import RbSet
from app.services import catalog_admin
from tests.deck_api_helpers import content, line, make_deck, ref

URL = '/riftbound/api/v1/admin/cards'


@pytest.fixture
def catalog(app, make_user):
    db.session.add_all([
        RbSet(rbset_id='OGN', rbset_name='Origen', rbset_ncard=3,
              rbset_outdat=date(2026, 1, 1)),
        RbSet(rbset_id='SFD', rbset_name='Segundo', rbset_ncard=2),
        RbCard(rbcar_rbset_id='OGN', rbcar_id='1', rbcar_name='Alpha Unit',
               rbcar_domain='fury', rbcar_type='Unit', rbcar_rarity='Común',
               image='ogn_1.png'),
        RbCard(rbcar_rbset_id='OGN', rbcar_id='2', rbcar_name='Beta Spell',
               rbcar_domain='calm', rbcar_type='Spell', rbcar_rarity='Rara',
               image=None),
        RbCard(rbcar_rbset_id='OGN', rbcar_id='10', rbcar_name='Gamma Unit',
               rbcar_domain='fury', rbcar_type='Unit', rbcar_rarity='Común',
               image=''),
        RbCard(rbcar_rbset_id='SFD', rbcar_id='1', rbcar_name='Delta Unit',
               rbcar_domain='mind', rbcar_type='Unit', rbcar_rarity='Común'),
    ])
    user = make_user('owner')
    db.session.add(RbCollection(rbcol_user=user.username, rbcol_rbset_id='OGN',
                                rbcol_rbcar_id='1', rbcol_quantity=1))
    db.session.commit()
    make_deck(name='Deck', body=content(main=[line('SFD', '1', 2)]), user=user.username)
    return app


def payload(resp):
    return resp.get_json()


def ids(body):
    return [(i['set_id'], i['card_id']) for i in body['data']['items']]


class TestList:
    def test_default_order_is_set_then_natural_id(self, admin_client, catalog):
        body = payload(admin_client.get(URL))
        assert body['data']['meta'] == {'page': 1, 'per_page': 50, 'total': 4, 'pages': 1}
        assert ids(body) == [('OGN', '1'), ('OGN', '2'), ('OGN', '10'), ('SFD', '1')]

    def test_repeatable_set_filter(self, admin_client, catalog):
        assert ids(payload(admin_client.get(f'{URL}?set=SFD'))) == [('SFD', '1')]
        body = payload(admin_client.get(f'{URL}?set=OGN&set=SFD'))
        assert body['data']['meta']['total'] == 4

    def test_rarity_is_exact_and_case_insensitive(self, admin_client, catalog):
        assert ids(payload(admin_client.get(f'{URL}?rarity=común'))) == [
            ('OGN', '1'), ('OGN', '10'), ('SFD', '1')]

    def test_type_and_domain_are_substrings(self, admin_client, catalog):
        assert ids(payload(admin_client.get(f'{URL}?type=nit'))) == [
            ('OGN', '1'), ('OGN', '10'), ('SFD', '1')]
        assert ids(payload(admin_client.get(f'{URL}?domain=UR'))) == [('OGN', '1'), ('OGN', '10')]

    def test_missing_image(self, admin_client, catalog):
        assert ids(payload(admin_client.get(f'{URL}?missing_image=true'))) == [
            ('OGN', '2'), ('OGN', '10'), ('SFD', '1')]

    def test_q_matches_name_id_and_key(self, admin_client, catalog):
        assert ids(payload(admin_client.get(f'{URL}?q=nit'))) == [
            ('OGN', '1'), ('OGN', '10'), ('SFD', '1')]
        assert ids(payload(admin_client.get(f'{URL}?q=2'))) == [('OGN', '2')]
        assert ids(payload(admin_client.get(f'{URL}?q=OGN-10'))) == [('OGN', '10')]

    def test_sort_name_desc_and_pagination(self, admin_client, catalog):
        body = payload(admin_client.get(f'{URL}?sort=name&dir=desc&per_page=50'))
        assert ids(body) == [('OGN', '10'), ('SFD', '1'), ('OGN', '2'), ('OGN', '1')]
        body = payload(admin_client.get(f'{URL}?per_page=50&page=2'))
        assert body['data']['meta'] == {'page': 2, 'per_page': 50, 'total': 4, 'pages': 1}
        assert ids(body) == []

    def test_mixed_ids_sort_naturally(self, admin_client, app):
        """Owner feedback S6: ids mixing digits and text never 500 (int vs str)."""
        db.session.add(RbSet(rbset_id='VEN', rbset_name='Vendetta', rbset_ncard=7))
        for card_id in ('P01', '10a', 'OGN-001', '2', '257s', '10', '1'):
            db.session.add(RbCard(rbcar_rbset_id='VEN', rbcar_id=card_id,
                                  rbcar_name=f'Card {card_id}'))
        db.session.commit()
        resp = admin_client.get(URL)
        assert resp.status_code == 200
        expected = ['1', '2', '10', '10a', '257s', 'OGN-001', 'P01']
        assert [c for _, c in ids(payload(resp))] == expected
        body = payload(admin_client.get(f'{URL}?dir=desc'))
        assert [c for _, c in ids(body)] == expected[::-1]
        same_name = payload(admin_client.get(f'{URL}?sort=name'))
        assert [c for _, c in ids(same_name)] == [
            '1', '10', '10a', '2', '257s', 'OGN-001', 'P01']

    def test_bad_params_are_400(self, admin_client):
        for query in ('sort=bogus', 'dir=sideways', 'page=0', 'per_page=7',
                      'missing_image=maybe', 'unknown_param=1'):
            resp = admin_client.get(f'{URL}?{query}')
            assert resp.status_code == 400, query
            assert payload(resp)['code'] == 'validation_error'

    def test_bounded_queries(self, admin_client, catalog):
        counted = []

        def before(conn, cursor, statement, params, context, executemany):
            if statement.lstrip().upper().startswith('SELECT'):
                counted.append(statement)

        event.listen(db.engine, 'before_cursor_execute', before)
        try:
            assert admin_client.get(URL).status_code == 200
        finally:
            event.remove(db.engine, 'before_cursor_execute', before)
        assert len(counted) <= 3, counted

    def test_item_shape(self, admin_client, catalog):
        item = payload(admin_client.get(f'{URL}?q=Alpha'))['data']['items'][0]
        assert item == {'set_id': 'OGN', 'card_id': '1', 'key': 'OGN-1',
                        'name': 'Alpha Unit', 'domain': 'fury', 'type': 'Unit',
                        'tags': None, 'energy': None, 'power': None, 'might': None,
                        'ability': None, 'rarity': 'Común', 'artist': None,
                        'image': 'ogn_1.png', 'image_url': '/riftbound/media/cards/ogn/ogn_1.png',
                        'image_src': '/riftbound/media/cards/ogn/ogn_1.png'}


class TestCreate:
    def test_create(self, admin_client, catalog):
        body = payload(admin_client.post(URL, json={
            'set_id': 'SFD', 'card_id': 'Ab9', 'name': '  New Card ',
            'type': 'Unit', 'energy': 3}))
        assert body['data']['key'] == 'SFD-ab9'
        assert body['data']['name'] == 'New Card'
        assert RbAdminAudit.query.one().rbaud_action == 'card.create'

    def test_unknown_set_is_400(self, admin_client):
        resp = admin_client.post(URL, json={'set_id': 'NOPE', 'card_id': '1',
                                            'name': 'X'})
        assert resp.status_code == 400
        assert any(d['field'] == 'set_id' and d['code'] == 'invalid_value'
                   for d in payload(resp)['details'])

    def test_duplicate_key_is_409(self, admin_client, catalog):
        resp = admin_client.post(URL, json={'set_id': 'OGN', 'card_id': '1',
                                            'name': 'Dup'})
        assert resp.status_code == 409
        body = payload(resp)
        assert body['code'] == 'already_exists'
        assert body['params'] == {'field': 'card_id'}

    def test_bad_card_id_is_400(self, admin_client, catalog):
        resp = admin_client.post(URL, json={'set_id': 'OGN', 'card_id': 'BIG ID!',
                                            'name': 'X'})
        assert resp.status_code == 400


class TestPatch:
    def test_patch(self, admin_client, catalog):
        body = payload(admin_client.patch(f'{URL}/OGN/1', json={'name': 'Renamed'}))
        assert body['data']['name'] == 'Renamed'
        row = RbAdminAudit.query.one()
        assert row.rbaud_action == 'card.update'
        assert row.rbaud_details == {'name': ['Alpha Unit', 'Renamed']}

    def test_keys_are_refused(self, admin_client, catalog):
        for field in ('set_id', 'card_id'):
            resp = admin_client.patch(f'{URL}/OGN/1', json={field: 'X'})
            assert resp.status_code == 400, field
            assert any(d['field'] == field and d['code'] == 'invalid_value'
                       for d in payload(resp)['details'])

    @pytest.mark.parametrize('field', ['rbcar_banned', 'banned'])
    def test_banned_is_refused(self, admin_client, catalog, field):
        # Bans live in rbcardbans (`flask bans`); `rbcar_banned` was dropped in F11-f.
        resp = admin_client.patch(f'{URL}/OGN/1', json={field: 'S'})
        assert resp.status_code == 400
        assert any(d['field'] == field for d in payload(resp)['details'])

    def test_unknown_card_is_404(self, admin_client):
        assert admin_client.patch(f'{URL}/OGN/999', json={'name': 'X'}).status_code == 404


class TestDelete:
    def test_collection_use_blocks(self, admin_client, catalog):
        resp = admin_client.delete(f'{URL}/OGN/1')
        assert resp.status_code == 409
        body = payload(resp)
        assert body['code'] == 'card_in_use'
        assert body['params'] == {'collection_lines': 1, 'decks': 0}

    def test_deck_use_blocks(self, admin_client, catalog):
        resp = admin_client.delete(f'{URL}/SFD/1')
        assert resp.status_code == 409
        assert payload(resp)['params'] == {'collection_lines': 0, 'decks': 1}

    def test_delete(self, admin_client, catalog):
        body = payload(admin_client.delete(f'{URL}/OGN/2'))
        assert body['data'] == {'deleted': 'OGN-2'}
        assert RbCard.query.filter_by(rbcar_rbset_id='OGN', rbcar_id='2').one_or_none() is None
        row = RbAdminAudit.query.one()
        assert (row.rbaud_action, row.rbaud_target_id) == ('card.delete', 'OGN-2')


def _v2_deck(name, user='owner', **zones):
    """A v2 deck of `user` whose single (current) version holds `zones`."""
    return make_deck(name=name, body=content(**zones), user=user)


def _in_use(admin_client, card='OGN/2'):
    resp = admin_client.delete(f'{URL}/{card}')
    assert resp.status_code == 409, resp.get_json()
    body = payload(resp)
    assert body['code'] == 'card_in_use'
    assert RbCard.query.filter_by(rbcar_rbset_id='OGN', rbcar_id='2').one_or_none() is not None
    return body['params']


class TestDeleteDecksV2:
    """The delete guard reads decks v2 too: the current version of every deck, any user,
    every zone including the workbench (a workbench line is still a reference)."""

    @pytest.mark.parametrize('zones', [
        {'main': [line('OGN', '2', 2)]},
        {'sideboard': [line('OGN', '2', 1)]},
        {'runes': [line('OGN', '2', 6)]},
        {'battlefields': [ref('OGN', '2')]},
        {'legend': ref('OGN', '2')},
        {'champion': ref('OGN', '2')},
        {'workbench': [line('OGN', '2', 1)]},
    ], ids=['main', 'sideboard', 'runes', 'battlefields', 'legend', 'champion', 'workbench'])
    def test_any_zone_of_the_current_version_blocks(self, admin_client, catalog, zones):
        _v2_deck('V2', **zones)
        assert _in_use(admin_client) == {'collection_lines': 0, 'decks': 1}
        assert RbAdminAudit.query.count() == 0

    def test_a_card_in_two_zones_of_one_deck_counts_one_deck(self, admin_client, catalog):
        _v2_deck('V2', main=[line('OGN', '2', 2)], workbench=[line('OGN', '2', 1)])
        assert _in_use(admin_client) == {'collection_lines': 0, 'decks': 1}

    def test_two_v2_decks_count_two(self, admin_client, catalog):
        _v2_deck('One', main=[line('OGN', '2', 1)])
        _v2_deck('Two', sideboard=[line('OGN', '2', 1)])
        assert _in_use(admin_client) == {'collection_lines': 0, 'decks': 2}

    def test_another_users_deck_blocks(self, admin_client, catalog, make_user):
        make_user('someone')
        _v2_deck('Theirs', user='someone', main=[line('OGN', '2', 1)])
        assert _in_use(admin_client) == {'collection_lines': 0, 'decks': 1}

    def test_only_an_older_version_does_not_block(self, admin_client, catalog):
        deck_id = make_deck(name='Old', body=content(main=[line('OGN', '1', 1)]),
                            user='owner', seqs=(1, 2))
        first = RbDeckVersion.query.filter_by(rbdkv_deck_id=deck_id, rbdkv_seq=1).one()
        first.rbdkv_content = content(main=[line('OGN', '2', 3)])
        db.session.commit()
        resp = admin_client.delete(f'{URL}/OGN/2')
        assert resp.status_code == 200, resp.get_json()
        assert payload(resp)['data'] == {'deleted': 'OGN-2'}

    def test_a_v2_deck_without_the_card_does_not_block(self, admin_client, catalog):
        _v2_deck('Other', main=[line('OGN', '10', 1)], workbench=[line('OGN', '10', 1)])
        assert admin_client.delete(f'{URL}/OGN/2').status_code == 200

    def test_the_guard_runs_two_statements(self, app, catalog):
        for n in range(5):
            _v2_deck(f'Deck {n}', main=[line('OGN', '2', 1)])
        counted = []

        def before(conn, cursor, statement, *args):
            counted.append(statement)

        event.listen(db.engine, 'before_cursor_execute', before)
        try:
            assert catalog_admin.card_use_count('OGN', '2') == (0, 5)
        finally:
            event.remove(db.engine, 'before_cursor_execute', before)
        assert len(counted) == 2, counted
