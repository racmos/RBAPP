"""Seed data shared by the F5-d tests (decks API).

Catalog: legend "Azir, Emperor" (Calm Order, tag Azir), champion "Azir, Ascendant" (Calm, tag
Azir), units "Shurima Guard" (two printings: OGN/U1 and SFD/U1), "Desert Scout" (Order), spell
"Sandstorm" (Calm, unpriced), "Fury Bolt" (Fury, off identity), runes Calm / Order, four
battlefields and the token "Sand Soldier".

Prices (EUR, `avg7`): legend 5, champion 10, OGN/U1 2, SFD/U1 1, Desert Scout 0.5, Calm Rune
0.1, Field 1 0.2; everything else is unpriced.
"""
from datetime import datetime

from app import db
from app.models import (RbCard, RbDeckHead, RbDeckVersion, RbSet, RbcmPrice,
                        RbcmProductCardMap, User)
from app.schemas.deck_content import empty_content

BASE = '/riftbound/api/v1/decks'
NOT_FOUND = {'success': False, 'error': 'Not Found',
             'message': 'The requested resource was not found'}
WHEN = datetime(2026, 10, 1, 9, 0)

_CARDS = [
    ('OGN', 'L1', 'Azir, Emperor', 'Champion Legend', 'Calm Order', 'Azir', 'Rare'),
    ('OGN', 'C1', 'Azir, Ascendant', 'Champion Unit', 'Calm', 'Azir, Shurima', 'Rare'),
    ('OGN', 'U1', 'Shurima Guard', 'Unit', 'Calm', 'Shurima', 'Common'),
    ('SFD', 'U1', 'Shurima Guard', 'Unit', 'Calm', 'Shurima', 'Common'),
    ('OGN', 'U2', 'Desert Scout', 'Unit', 'Order', '', 'Common'),
    ('OGN', 'S1', 'Sandstorm', 'Spell', 'Calm', '', 'Uncommon'),
    ('OGN', 'F1', 'Fury Bolt', 'Spell', 'Fury', '', 'Common'),
    ('OGN', 'R1', 'Calm Rune', 'Basic Rune', 'Calm', '', 'Common'),
    ('OGN', 'R2', 'Order Rune', 'Basic Rune', 'Order', '', 'Common'),
    *[('OGN', f'B{n}', f'Field {n}', 'Battlefield', '', '', 'Common') for n in range(1, 5)],
    ('OGN', 'T1', 'Sand Soldier', 'Token Unit', 'Calm', '', 'Common'),
]
_PRICES = {('OGN', 'L1'): 5, ('OGN', 'C1'): 10, ('OGN', 'U1'): 2, ('SFD', 'U1'): 1,
           ('OGN', 'U2'): 0.5, ('OGN', 'R1'): 0.1, ('OGN', 'B1'): 0.2}


def seed_catalog():
    db.session.add_all([RbSet(rbset_id='OGN', rbset_name='Origins'),
                        RbSet(rbset_id='SFD', rbset_name='Spiritforged')])
    db.session.add_all([
        RbCard(rbcar_rbset_id=s, rbcar_id=i, rbcar_name=n, rbcar_type=t, rbcar_domain=d,
               rbcar_tags=g, rbcar_rarity=r) for s, i, n, t, d, g, r in _CARDS])
    for product, ((set_id, card_id), price) in enumerate(_PRICES.items(), start=1):
        db.session.add_all([
            RbcmProductCardMap(rbpcm_rbset_id=set_id, rbpcm_rbcar_id=card_id,
                               rbpcm_id_product=product, rbpcm_foil='N'),
            RbcmPrice(rbprc_date='20261020', rbprc_id_product=product, rbprc_avg7=price)])
    db.session.commit()


def user_id(name='testuser'):
    return User.query.filter_by(username=name).one().id


def ref(set_id, card_id):
    return {'set': set_id, 'id': card_id}


def line(set_id, card_id, qty=1):
    return {'set': set_id, 'id': card_id, 'qty': qty}


def content(**zones):
    out = empty_content()
    out.update(zones)
    return out


AZIR = content(
    legend=ref('OGN', 'L1'), champion=ref('OGN', 'C1'),
    main=[line('OGN', 'U1', 2), line('SFD', 'U1', 1), line('OGN', 'S1', 3)],
    runes=[line('OGN', 'R1', 6), line('OGN', 'R2', 6)],
    battlefields=[ref('OGN', 'B1'), ref('OGN', 'B2')],
    sideboard=[line('OGN', 'U2', 2)],
    workbench=[line('OGN', 'F1', 1), line('OGN', 'T1', 2), line('OGN', 'U2', 1)])


def make_deck(name='Azir', body=None, user='testuser', mode='1v1', at=WHEN, seqs=(1,)):
    """A committed head with one version per seq (all with `body`); the last is current."""
    head = RbDeckHead(rbdkh_user_id=user_id(user), rbdkh_name=name, rbdkh_mode=mode,
                      rbdkh_created_at=at, rbdkh_updated_at=at)
    db.session.add(head)
    db.session.flush()
    for seq in seqs:
        version = RbDeckVersion(rbdkv_deck_id=head.rbdkh_id, rbdkv_seq=seq,
                                rbdkv_content=body or empty_content(), rbdkv_created_at=at)
        db.session.add(version)
        db.session.flush()
    head.rbdkh_current_version_id = version.rbdkv_id
    db.session.commit()
    return head.rbdkh_id


def versions(deck_id):
    db.session.expire_all()
    return [(v.rbdkv_seq, v.rbdkv_content, v.rbdkv_note) for v in RbDeckVersion.query
            .filter_by(rbdkv_deck_id=deck_id).order_by(RbDeckVersion.rbdkv_seq)]


def head_row(deck_id):
    db.session.expire_all()
    return db.session.get(RbDeckHead, deck_id)


def data(resp, status=200):
    assert resp.status_code == status, resp.get_json()
    body = resp.get_json()
    assert body['success'] is True
    return body['data']


def error(resp, status, code):
    assert resp.status_code == status, resp.get_json()
    body = resp.get_json()
    assert body['success'] is False and body.get('code') == code, body
    return body
