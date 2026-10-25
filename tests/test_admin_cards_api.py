"""F13-b S6-S8, S10 (AC2): cards admin API."""
from datetime import date

import pytest
from sqlalchemy import event

from app import db
from app.models.audit import RbAdminAudit
from app.models.card import RbCard
from app.models.collection import RbCollection
from app.models.deck import RbDeck
from app.models.set import RbSet
from app.models.user import User

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
    db.session.add(RbDeck(rbdck_user=user.username, rbdck_name='Deck',
                          rbdck_cards={'main': [{'set': 'SFD', 'id': '1', 'qty': 2}],
                                       'sideboard': []}))
    db.session.commit()
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

    def test_banned_is_refused(self, admin_client, catalog):
        resp = admin_client.patch(f'{URL}/OGN/1', json={'rbcar_banned': 'S'})
        assert resp.status_code == 400

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
