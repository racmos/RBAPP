"""Shared Cardmarket matching data (CM-b): the legacy characterization tests and the
`/admin/cardmarket` matching API tests build the same rows, written directly.

Latest product date is D2; D1 only holds an older snapshot (product 900 is gone on D2).

Cards: OGN-001 Jinx (common), OGN-002 Vi (rare), OGN-003 Ahri (Legend, epic, tags
"Nine-Tailed Fox"), OGNX-002 Vi (rare promo), OGN-004 Rune of Fury (Rune, common).
Expansions: 10 -> OGN, 11 -> OGNX, 12 unmapped.

D2 products (single unless said):
  100 Jinx              metacard 1, exp 10, low 0.10
  101 Jinx (Foil)       metacard 1, exp 10, low 1.00
  200 Vi                metacard 2, exp 10, low 2.00
  201 Vi (Promo)        metacard 2, exp 11, low 5.00
  250 Ahri, Nine-Tailed Fox  metacard 3, exp 10, low 9.00
  300 Origins Booster Box  nonsingle, exp 10, low 100.00 (rbproducts row 300 exists)
  301 Origins Playmat   nonsingle, exp 12, no price
  400 Mystery Card      metacard 4, exp 10, low 0.50 (no candidate card)
  500 Ignored Thing     metacard 5, exp 10 (ignored pair)
  501 Renamed Thing     metacard 6, exp 10 (ignored under another name: still listed)
"""
from datetime import datetime

from app import db
from app.models import RbCard, RbSet
from app.models.cardmarket import (RbcmExpansion, RbcmIgnored, RbcmPrice, RbcmProduct,
                                   RbcmProductCardMap, RbProducts)

D1, D2 = '20301001', '20301002'


def card(set_id, car_id, name, rarity, card_type='Unit', tags=None, image=None):
    db.session.add(RbCard(rbcar_rbset_id=set_id, rbcar_id=car_id, rbcar_name=name,
                          rbcar_rarity=rarity, rbcar_type=card_type, rbcar_tags=tags,
                          image=image))


def product(id_product, name, metacard=None, expansion=10, type_='single', date=D2,
            category=None):
    db.session.add(RbcmProduct(
        rbprd_date=date, rbprd_id_product=id_product, rbprd_name=name,
        rbprd_id_metacard=metacard, rbprd_id_expansion=expansion, rbprd_type=type_,
        rbprd_category_name=category or ('Riftbound Single' if type_ == 'single'
                                         else 'Riftbound Booster Box')))


def price(id_product, low, date=D2, **extra):
    db.session.add(RbcmPrice(rbprc_date=date, rbprc_id_product=id_product, rbprc_low=low,
                             **extra))


def link(id_product, set_id, car_id, foil=None, match_type='manual', confidence=1.0):
    db.session.add(RbcmProductCardMap(
        rbpcm_id_product=id_product, rbpcm_rbset_id=set_id, rbpcm_rbcar_id=car_id,
        rbpcm_foil=foil, rbpcm_match_type=match_type, rbpcm_confidence=confidence))


def ignore(id_product, name, at=None):
    db.session.add(RbcmIgnored(rbig_id_product=id_product, rbig_name=name,
                               rbig_ignored_at=at or datetime(2030, 10, 2, 8)))


def build():
    db.session.add(RbSet(rbset_id='OGN', rbset_name='Origins', rbset_ncard=300))
    db.session.add(RbSet(rbset_id='OGNX', rbset_name='Origins Promos', rbset_ncard=50))
    db.session.flush()
    card('OGN', '001', 'Jinx', 'Common', image='ogn_001.png')
    card('OGN', '002', 'Vi', 'Rare')
    card('OGN', '003', 'Ahri', 'Epic', card_type='Legend', tags='Nine-Tailed Fox')
    card('OGNX', '002', 'Vi', 'Rare')
    card('OGN', '004', 'Rune of Fury', 'Common', card_type='Basic Rune')
    db.session.add(RbcmExpansion(rbexp_id=10, rbexp_name='Origins', rbexp_rbset_id='OGN'))
    db.session.add(RbcmExpansion(rbexp_id=11, rbexp_name='Origins Promos',
                                 rbexp_rbset_id='OGNX'))
    db.session.add(RbcmExpansion(rbexp_id=12, rbexp_name='Accessories'))
    # D1: an older snapshot
    for pid, name in ((100, 'Jinx'), (200, 'Vi'), (900, 'Gone Card')):
        product(pid, name, metacard=pid, date=D1)
        price(pid, 0.01, date=D1)
    # D2: the latest snapshot
    product(100, 'Jinx', metacard=1)
    product(101, 'Jinx (Foil)', metacard=1)
    product(200, 'Vi', metacard=2)
    product(201, 'Vi (Promo)', metacard=2, expansion=11)
    product(250, 'Ahri, Nine-Tailed Fox', metacard=3)
    product(300, 'Origins Booster Box', type_='nonsingle')
    product(301, 'Origins Playmat', type_='nonsingle', expansion=12,
            category='Riftbound Playmats')
    product(400, 'Mystery Card', metacard=4)
    product(500, 'Ignored Thing', metacard=5)
    product(501, 'Renamed Thing', metacard=6)
    for pid, low in ((100, 0.10), (101, 1.00), (200, 2.00), (201, 5.00), (250, 9.00),
                     (300, 100.00), (400, 0.50)):
        price(pid, low)
    db.session.add(RbProducts(rbpdt_id_product=300, rbpdt_id_set='OGN',
                              rbpdt_name='Origins Booster Box', rbpdt_type='nonsingle',
                              rbpdt_kind='box'))
    ignore(500, 'Ignored Thing')
    ignore(501, 'Old Name', at=datetime(2030, 10, 1, 8))
    db.session.commit()
