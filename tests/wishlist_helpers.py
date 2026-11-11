"""Seed data shared by the F3-f-2 tests (wishlists API).

Catalog (sets OGN 2025-10-31, SFD 2025-11-30):
  OGN/1   Alpha Fury         Common    base printing of "Alpha Fury"
  OGN/1a  Alpha Fury         Common    alternate art (not all digits: never the base)
  SFD/5   Alpha Fury         Common    reprint (later set: not the base)
  OGN/2   Beta Calm          Uncommon  unpriced
  OGN/79  Jinx, Loose Cannon Rare      no foil version
  OGN/3.. Filler n           Common    (`seed_fillers`, for the limits and the statement count)

Prices (EUR): OGN/1 non-foil 10 (avg7), foil 30 (avg7_foil); OGN/1a 50; SFD/5 4; OGN/79 20.
SFD/5 and OGN/1a have no foil product, so their foil price falls back to the non-foil product
(the app-wide rule of `price_summaries`).
"""
from datetime import date, datetime

from app import db
from app.models import (RbCard, RbCollection, RbSet, RbWishlist, RbWishlistLine, RbcmPrice,
                        RbcmProductCardMap, User)

BASE = '/riftbound/api/v1/wishlists'
NOT_FOUND = {'success': False, 'error': 'Not Found',
             'message': 'The requested resource was not found'}
LIST_KEYS = ['id', 'name', 'is_default', 'position', 'line_count', 'created_at', 'updated_at']
LINE_KEYS = ['id', 'list_id', 'name', 'set_id', 'card_id', 'card', 'foil', 'qty', 'max_price',
             'note', 'created_at', 'updated_at', 'market', 'reached', 'owned']


def seed_catalog():
    db.session.add_all([
        RbSet(rbset_id='OGN', rbset_name='Origins', rbset_outdat=date(2025, 10, 31)),
        RbSet(rbset_id='SFD', rbset_name='Spiritforged', rbset_outdat=date(2025, 11, 30)),
    ])
    db.session.add_all([
        RbCard(rbcar_rbset_id='OGN', rbcar_id='1', rbcar_name='Alpha Fury', rbcar_domain='Fury',
               rbcar_type='Unit', rbcar_rarity='Common'),
        RbCard(rbcar_rbset_id='OGN', rbcar_id='1a', rbcar_name='Alpha Fury', rbcar_domain='Fury',
               rbcar_type='Unit', rbcar_rarity='Common'),
        RbCard(rbcar_rbset_id='SFD', rbcar_id='5', rbcar_name='Alpha Fury', rbcar_domain='Fury',
               rbcar_type='Unit', rbcar_rarity='Common'),
        RbCard(rbcar_rbset_id='OGN', rbcar_id='2', rbcar_name='Beta Calm', rbcar_domain='Calm',
               rbcar_type='Spell', rbcar_rarity='Uncommon'),
        RbCard(rbcar_rbset_id='OGN', rbcar_id='79', rbcar_name='Jinx, Loose Cannon',
               rbcar_domain='Chaos', rbcar_type='Champion Unit', rbcar_rarity='Rare'),
    ])
    for set_id, card_id, foil, product in (('OGN', '1', 'N', 1), ('OGN', '1', 'S', 11),
                                           ('OGN', '1a', 'N', 2), ('SFD', '5', 'N', 3),
                                           ('OGN', '79', 'N', 79)):
        db.session.add(RbcmProductCardMap(rbpcm_rbset_id=set_id, rbpcm_rbcar_id=card_id,
                                          rbpcm_id_product=product, rbpcm_foil=foil))
    db.session.add_all([
        RbcmPrice(rbprc_date='20261020', rbprc_id_product=1, rbprc_avg7=10),
        RbcmPrice(rbprc_date='20261020', rbprc_id_product=11, rbprc_avg7_foil=30),
        RbcmPrice(rbprc_date='20261020', rbprc_id_product=2, rbprc_avg7=50),
        RbcmPrice(rbprc_date='20261020', rbprc_id_product=3, rbprc_avg7=4),
        RbcmPrice(rbprc_date='20261020', rbprc_id_product=79, rbprc_avg7=20),
    ])
    db.session.commit()


def seed_fillers(count, start=100):
    """`count` common cards `OGN/<n>` named `Filler <n>`; returns their card ids."""
    ids = [str(n) for n in range(start, start + count)]
    db.session.add_all([RbCard(rbcar_rbset_id='OGN', rbcar_id=card_id,
                               rbcar_name=f'Filler {card_id}', rbcar_type='Unit',
                               rbcar_rarity='Common') for card_id in ids])
    db.session.commit()
    return ids


def own(card_id, qty, *, set_id='OGN', foil='N', user='testuser'):
    db.session.add(RbCollection(
        rbcol_rbset_id=set_id, rbcol_rbcar_id=card_id, rbcol_foil=foil, rbcol_user=user,
        rbcol_quantity=qty, rbcol_condition='NM', rbcol_language='English', rbcol_selling='N',
        rbcol_sell_qty=0, rbcol_chadat=datetime(2026, 10, 1, 9, 0)))
    db.session.commit()


def user_id(name='testuser'):
    return User.query.filter_by(username=name).one().id


def lists_of(name='testuser'):
    db.session.expire_all()
    return RbWishlist.query.filter_by(rbwls_user_id=user_id(name)).order_by(
        RbWishlist.rbwls_position).all()


def lines_of(list_id):
    db.session.expire_all()
    return RbWishlistLine.query.filter_by(rbwsl_list_id=list_id).order_by(
        RbWishlistLine.rbwsl_id).all()


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


def default_list(client):
    """The caller's default list id (created on the first GET)."""
    items = data(client.get(BASE))['items']
    return next(item['id'] for item in items if item['is_default'])


def new_list(client, name):
    return data(client.post(BASE, json={'name': name}), 201)['id']


def add(client, list_id, status=201, **body):
    return data(client.post(f'{BASE}/{list_id}/lines', json=body), status)


def printing(card_id='1', set_id='OGN', **body):
    return {'set_id': set_id, 'card_id': card_id, **body}
