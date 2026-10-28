"""Seed data shared by the F3-b tests (GET /collection).

Prices (EUR, `avg7` / `avg7_foil`): OGN/1 non-foil 10 (8 ten days earlier, so +25 % in 7 days),
OGN/1 foil 30, OGN/2 5, OGN/79 20; SFD/10 and SFD/257 have no product (unpriced).
"""
from datetime import date, datetime

from app import db
from app.models import RbCard, RbCollection, RbSet, RbcmPrice, RbcmProductCardMap

URL = '/riftbound/api/v1/collection'


def seed_catalog():
    db.session.add_all([
        RbSet(rbset_id='OGN', rbset_name='Origins', rbset_outdat=date(2025, 10, 31)),
        RbSet(rbset_id='SFD', rbset_name='Spiritforged', rbset_outdat=date(2025, 11, 30)),
    ])
    db.session.add_all([
        RbCard(rbcar_rbset_id='OGN', rbcar_id='1', rbcar_name='Alpha Fury', rbcar_domain='Fury',
               rbcar_type='Unit', rbcar_rarity='Common', rbcar_tags='Noxus'),
        RbCard(rbcar_rbset_id='OGN', rbcar_id='2', rbcar_name='Beta Calm', rbcar_domain='Calm',
               rbcar_type='Spell', rbcar_rarity='Uncommon', rbcar_tags='Ionia'),
        RbCard(rbcar_rbset_id='OGN', rbcar_id='79', rbcar_name='Jinx, Loose Cannon',
               rbcar_domain='Chaos', rbcar_type='Champion Unit', rbcar_rarity='Rare',
               rbcar_tags='Zaun'),
        RbCard(rbcar_rbset_id='SFD', rbcar_id='10', rbcar_name='Delta Gear', rbcar_domain='Order',
               rbcar_type='Gear', rbcar_rarity='Epic', rbcar_tags=''),
        RbCard(rbcar_rbset_id='SFD', rbcar_id='257', rbcar_name='Jinx, Loose Cannon',
               rbcar_domain='Chaos', rbcar_type='Champion Unit', rbcar_rarity='Rare',
               rbcar_tags='Zaun'),
    ])
    db.session.add_all([
        RbcmProductCardMap(rbpcm_rbset_id='OGN', rbpcm_rbcar_id='1', rbpcm_id_product=1,
                           rbpcm_foil='N'),
        RbcmProductCardMap(rbpcm_rbset_id='OGN', rbpcm_rbcar_id='1', rbpcm_id_product=11,
                           rbpcm_foil='S'),
        RbcmProductCardMap(rbpcm_rbset_id='OGN', rbpcm_rbcar_id='2', rbpcm_id_product=2,
                           rbpcm_foil='N'),
        RbcmProductCardMap(rbpcm_rbset_id='OGN', rbpcm_rbcar_id='79', rbpcm_id_product=79,
                           rbpcm_foil='N'),
        RbcmPrice(rbprc_date='20261010', rbprc_id_product=1, rbprc_avg7=8),
        RbcmPrice(rbprc_date='20261020', rbprc_id_product=1, rbprc_avg7=10),
        RbcmPrice(rbprc_date='20261020', rbprc_id_product=11, rbprc_avg7_foil=30),
        RbcmPrice(rbprc_date='20261020', rbprc_id_product=2, rbprc_avg7=5),
        RbcmPrice(rbprc_date='20261020', rbprc_id_product=79, rbprc_avg7=20),
    ])
    db.session.commit()


def line(card, qty, *, set_id='OGN', foil='N', user='testuser', condition='NM',
         language='English', purchase=None, selling='N', sell_qty=0, sell_price=None,
         changed=datetime(2026, 10, 1, 9, 30)):
    return RbCollection(
        rbcol_rbset_id=set_id, rbcol_rbcar_id=card, rbcol_foil=foil, rbcol_user=user,
        rbcol_quantity=qty, rbcol_condition=condition, rbcol_language=language,
        rbcol_purchase_price=purchase, rbcol_selling=selling, rbcol_sell_qty=sell_qty,
        rbcol_sell_price=sell_price, rbcol_chadat=changed)


def seed_lines(user='testuser'):
    """Seven lines in six groups for `user`, plus nine copies of OGN/1 for `otheruser`."""
    db.session.add_all([
        line('1', 4, purchase=8, selling='Y', sell_qty=1, sell_price=12.5,
             changed=datetime(2026, 10, 3, 9, 0)),                                  # L1
        line('1', 2, condition='LP', language='Spanish',
             changed=datetime(2026, 10, 4, 9, 0)),                                  # L2
        line('1', 1, foil='S', purchase=20, changed=datetime(2026, 10, 5, 9, 0)),   # L3
        line('2', 3, condition='EX', language='French', purchase=0, selling='Y', sell_qty=3,
             changed=datetime(2026, 10, 2, 9, 0)),                                  # L4
        line('79', 1, condition='MT', purchase=25, changed=datetime(2026, 10, 6, 9, 0)),  # L5
        line('10', 2, set_id='SFD', language='German',
             changed=datetime(2026, 10, 7, 9, 0)),                                  # L6
        line('257', 1, set_id='SFD', changed=datetime(2026, 10, 8, 9, 0)),          # L7
    ])
    db.session.add(line('1', 9, user='otheruser'))
    db.session.commit()


def seed_all(app):
    with app.app_context():
        seed_catalog()
        seed_lines()
