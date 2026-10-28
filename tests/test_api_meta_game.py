"""F2-b S9 (AC5, AC6): GET /meta/game is public and follows the contract."""
from datetime import date

from app import db
from app.models.card import RbCard
from app.models.cardmarket import RbcmPrice
from app.models.set import RbSet


def _seeded(app):
    db.session.add_all([
        RbSet(rbset_id='OGN', rbset_name='Origins', rbset_ncard=2,
              rbset_outdat=date(2025, 10, 31)),
        RbSet(rbset_id='SFD', rbset_name='Spiritforged', rbset_ncard=1),
        RbSet(rbset_id='ZZZ', rbset_name='Empty', rbset_ncard=0,
              rbset_outdat=date(2025, 1, 1)),
    ])
    db.session.add_all([
        RbCard(rbcar_rbset_id='OGN', rbcar_id='1', rbcar_name='A',
               rbcar_domain='Fury Chaos', rbcar_type='Champion Unit',
               rbcar_rarity='Rare'),
        RbCard(rbcar_rbset_id='OGN', rbcar_id='2', rbcar_name='B',
               rbcar_domain='Mind', rbcar_type='Spell', rbcar_rarity='Common'),
        RbCard(rbcar_rbset_id='SFD', rbcar_id='1', rbcar_name='C',
               rbcar_domain='Weird', rbcar_type='Creature',
               rbcar_rarity='Mythic'),
    ])
    db.session.add(RbcmPrice(rbprc_date='20261020', rbprc_id_product=1, rbprc_avg7=2.0))
    db.session.add(RbcmPrice(rbprc_date='20261019', rbprc_id_product=2, rbprc_avg7=1.0))
    db.session.commit()


def test_shape_order_and_extras(app, client):
    _seeded(app)
    body = client.get('/riftbound/api/v1/meta/game').get_json()
    assert body['success'] is True
    data = body['data']
    # jsonify sorts keys on the wire; order is pinned on the Python dict (AC1).
    assert set(data) == {'modes', 'domains', 'types', 'supertypes', 'rarities',
                         'sets', 'price', 'rules', 'conditions', 'languages'}
    assert data['modes'] == ['1v1', '2v2']
    assert data['domains'][:7] == ['Fury', 'Calm', 'Mind', 'Body', 'Chaos', 'Order',
                                   'Colorless']
    assert data['domains'][7:] == ['Fury Chaos', 'Weird']
    assert data['types'][:6] == ['Legend', 'Unit', 'Spell', 'Gear', 'Rune', 'Battlefield']
    assert data['types'][6:] == ['Champion Unit', 'Creature']
    assert data['supertypes'] == ['Champion', 'Signature', 'Token', 'Basic']
    assert data['rarities'] == ['Common', 'Uncommon', 'Rare', 'Epic', 'Showcase', 'Mythic']
    assert data['sets'] == [
        {'id': 'ZZZ', 'name': 'Empty', 'released_on': '2025-01-01', 'card_count': 0},
        {'id': 'OGN', 'name': 'Origins', 'released_on': '2025-10-31', 'card_count': 2},
        {'id': 'SFD', 'name': 'Spiritforged', 'released_on': None, 'card_count': 1},
    ]
    assert data['price'] == {'provider': 'cardmarket', 'currency': 'EUR',
                             'updated_on': '2026-10-20'}
    assert data['rules'] == {}


def test_conditions_best_to_worst_and_languages(app, client):
    """F3-b S7 (D-F3-4): the collection's closed lists, not read from the data."""
    _seeded(app)
    data = client.get('/riftbound/api/v1/meta/game').get_json()['data']
    assert data['conditions'] == ['MT', 'NM', 'EX', 'GD', 'LP', 'PL', 'PO']
    assert data['languages'] == [
        'English', 'French', 'German', 'Spanish', 'Italian', 'Simplified Chinese', 'Japanese',
        'Portuguese', 'Russian', 'Korean', 'Traditional Chinese']


def test_anonymous_and_signed_in_get_200(app, client, admin_client):
    _seeded(app)
    assert client.get('/riftbound/api/v1/meta/game').status_code == 200
    assert admin_client.get('/riftbound/api/v1/meta/game').status_code == 200


def test_no_cache_and_empty_db(app, client):
    response = client.get('/riftbound/api/v1/meta/game')
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-cache'
    body = response.get_json()['data']
    assert body['sets'] == []
    assert body['price']['updated_on'] is None


def test_authz_matrix_knows_meta_game():
    from tests.test_authz_matrix import MATRIX, classify
    from types import SimpleNamespace
    assert MATRIX['api_v1.meta_game'] == 'P'
    assert classify(SimpleNamespace(endpoint='api_v1.meta_game', rule='/x')) == 'P'
