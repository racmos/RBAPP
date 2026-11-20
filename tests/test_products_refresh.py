"""F14-a S4 (AC3): `refresh_products(date)` builds the product catalog in `rbproducts` from the
non-single Cardmarket products of one day."""
from datetime import datetime

import pytest
import sqlalchemy as sa

from app import db
from app.models import RbcmExpansion, RbcmProduct, RbProducts
from app.services.products import NothingToRefresh, refresh_products

DAY = '20300101'
NEXT = '20300102'
NOON = datetime(2030, 1, 1, 12, 0, 0)

FIELDS = ('rbpdt_id_product', 'rbpdt_id_set', 'rbpdt_name', 'rbpdt_category', 'rbpdt_kind',
          'rbpdt_type', 'rbpdt_listed', 'rbpdt_kind_locked', 'rbpdt_set_locked', 'rbpdt_hidden',
          'rbpdt_updated_at')


def cm(day, product_id, name, category, expansion=None, type_='nonsingle'):
    db.session.add(RbcmProduct(rbprd_date=day, rbprd_id_product=product_id, rbprd_name=name,
                               rbprd_category_name=category, rbprd_id_expansion=expansion,
                               rbprd_type=type_))


def catalog():
    db.session.expire_all()
    return [tuple(getattr(p, f) for f in FIELDS) for p in db.session.execute(
        sa.select(RbProducts).order_by(RbProducts.rbpdt_id_product)).scalars()]


@pytest.fixture
def day_one(app):
    """Two mapped expansions (OGN, SFD), one unmapped; four non-singles and a single."""
    db.session.add_all([RbcmExpansion(rbexp_id=1, rbexp_rbset_id='OGN'),
                        RbcmExpansion(rbexp_id=2, rbexp_rbset_id='SFD'),
                        RbcmExpansion(rbexp_id=3, rbexp_rbset_id=None)])
    cm(DAY, 100, 'Origins Booster', 'Riftbound Booster', expansion=1)
    cm(DAY, 101, 'Origins Display', 'Riftbound Display', expansion=1)
    cm(DAY, 102, 'Mystery Bundle', 'Riftbound Gift Bundle', expansion=3)
    cm(DAY, 103, 'Jinx Deck', 'Riftbound Champion Decks')
    cm(DAY, 900, 'Some Card', 'Riftbound Single', expansion=1, type_='single')
    db.session.commit()


def test_new_products_are_inserted_with_kind_and_set(day_one, frozen_clock):
    assert refresh_products(DAY) == {'date': DAY, 'new': 4, 'updated': 0,
                                     'not_listed': 0, 'skipped': 0, 'total': 4}
    assert catalog() == [
        (100, 'OGN', 'Origins Booster', 'Riftbound Booster', 'booster', 'nonsingle', True,
         False, False, False, NOON),
        (101, 'OGN', 'Origins Display', 'Riftbound Display', 'booster_box', 'nonsingle', True,
         False, False, False, NOON),
        (102, None, 'Mystery Bundle', 'Riftbound Gift Bundle', 'sealed_box_set',
         'nonsingle', True,
         False, False, False, NOON),
        (103, None, 'Jinx Deck', 'Riftbound Champion Decks', 'champion_deck',
         'nonsingle', True,
         False, False, False, NOON),
    ]


def test_singles_and_other_days_are_ignored(day_one, frozen_clock):
    cm(NEXT, 104, 'Tomorrow Booster', 'Riftbound Booster')
    db.session.commit()
    refresh_products(DAY)
    ids = [row[0] for row in catalog()]
    assert 900 not in ids and 104 not in ids


def test_a_second_run_with_nothing_new_changes_nothing(day_one, frozen_clock):
    refresh_products(DAY)
    before = catalog()
    frozen_clock.advance(hours=1)
    assert refresh_products(DAY) == {'date': DAY, 'new': 0, 'updated': 0,
                                     'not_listed': 0, 'skipped': 0, 'total': 4}
    assert catalog() == before          # rbpdt_updated_at only moves on a change


def test_existing_products_are_updated(day_one, frozen_clock):
    refresh_products(DAY)
    db.session.add(RbcmExpansion(rbexp_id=4, rbexp_rbset_id='UNL'))
    cm(NEXT, 100, 'Origins Booster Pack', 'Riftbound Booster', expansion=1)   # new name
    cm(NEXT, 101, 'Origins Display', 'Riftbound Booster Box Case', expansion=4)  # kind, set
    cm(NEXT, 102, 'Mystery Bundle', 'Riftbound Gift Bundle', expansion=3)     # unchanged
    cm(NEXT, 103, 'Jinx Deck', 'Riftbound Champion Decks')                    # unchanged
    db.session.commit()
    later = frozen_clock.advance(days=1)
    assert refresh_products(NEXT) == {'date': NEXT, 'new': 0, 'updated': 2,
                                     'not_listed': 0, 'skipped': 0, 'total': 4}
    rows = catalog()
    assert rows[0][:5] == (100, 'OGN', 'Origins Booster Pack', 'Riftbound Booster', 'booster')
    assert rows[0][-1] == later
    assert rows[1][:5] == (101, 'UNL', 'Origins Display', 'Riftbound Booster Box Case',
                          'booster_box')
    assert rows[1][-1] == later
    assert rows[2][-1] == NOON and rows[3][-1] == NOON


def test_a_locked_kind_and_a_locked_set_stay(day_one, frozen_clock):
    refresh_products(DAY)
    product = db.session.get(RbProducts, 101)
    product.rbpdt_kind = 'other'
    product.rbpdt_kind_locked = True
    product.rbpdt_id_set = 'PROMO'
    product.rbpdt_set_locked = True
    db.session.commit()
    for product_id, name, category, expansion in (
            (100, 'Origins Booster', 'Riftbound Booster', 1),
            (101, 'Origins Display v2', 'Riftbound Booster Box Case', 2),
            (102, 'Mystery Bundle', 'Riftbound Gift Bundle', 3),
            (103, 'Jinx Deck', 'Riftbound Champion Decks', None)):
        cm(NEXT, product_id, name, category, expansion=expansion)
    db.session.commit()
    later = frozen_clock.advance(days=1)
    assert refresh_products(NEXT)['updated'] == 1
    row = catalog()[1]
    assert row[:5] == (101, 'PROMO', 'Origins Display v2', 'Riftbound Booster Box Case', 'other')
    assert row[7:10] == (True, True, False)
    assert row[-1] == later


def test_products_missing_from_the_day_are_not_listed_and_never_deleted(day_one, frozen_clock):
    refresh_products(DAY)
    cm(NEXT, 100, 'Origins Booster', 'Riftbound Booster', expansion=1)
    cm(NEXT, 105, 'Spiritforged Booster', 'Riftbound Booster', expansion=2)
    db.session.commit()
    later = frozen_clock.advance(days=1)
    assert refresh_products(NEXT) == {'date': NEXT, 'new': 1, 'updated': 0,
                                     'not_listed': 3, 'skipped': 0, 'total': 5}
    listed = {row[0]: (row[6], row[-1]) for row in catalog()}
    assert listed == {100: (True, NOON), 101: (False, later), 102: (False, later),
                      103: (False, later), 105: (True, later)}
    # back in the next file: listed again
    cm('20300103', 101, 'Origins Display', 'Riftbound Display', expansion=1)
    db.session.commit()
    assert refresh_products('20300103') == {'date': '20300103', 'new': 0, 'updated': 1,
                                            'not_listed': 4, 'skipped': 0, 'total': 5}
    assert {row[0]: row[6] for row in catalog()} == {100: False, 101: True, 102: False,
                                                     103: False, 105: False}


def test_rows_that_are_not_nonsingle_are_never_touched(day_one, frozen_clock):
    db.session.add(RbProducts(rbpdt_id_product=500, rbpdt_id_set='OGN', rbpdt_name='Manual',
                              rbpdt_type='single'))
    db.session.add(RbProducts(rbpdt_id_product=501, rbpdt_id_set='OGN', rbpdt_name='Untyped'))
    db.session.commit()
    result = refresh_products(DAY)
    assert (result['not_listed'], result['total']) == (0, 4)
    rows = {row[0]: row for row in catalog()}
    assert rows[500][1:] == ('OGN', 'Manual', None, None, 'single', True, False, False, False,
                             None)
    assert rows[501][1:] == ('OGN', 'Untyped', None, None, None, True, False, False, False,
                             None)


def test_a_manual_row_listed_as_a_non_single_becomes_a_product(day_one, frozen_clock):
    db.session.add(RbProducts(rbpdt_id_product=100, rbpdt_id_set='OGN', rbpdt_name='Old name'))
    db.session.commit()
    assert refresh_products(DAY) == {'date': DAY, 'new': 3, 'updated': 1,
                                     'not_listed': 0, 'skipped': 0, 'total': 4}
    assert catalog()[0] == (100, 'OGN', 'Origins Booster', 'Riftbound Booster', 'booster',
                            'nonsingle', True, False, False, False, NOON)


def test_hidden_is_kept(day_one, frozen_clock):
    refresh_products(DAY)
    db.session.get(RbProducts, 100).rbpdt_hidden = True
    db.session.commit()
    refresh_products(DAY)
    assert catalog()[0][9] is True


def test_a_day_without_non_singles_changes_nothing(day_one, frozen_clock):
    refresh_products(DAY)
    before = catalog()
    cm(NEXT, 901, 'Another Card', 'Riftbound Single', type_='single')
    db.session.commit()
    with pytest.raises(NothingToRefresh) as caught:
        refresh_products(NEXT)
    assert str(caught.value) == f'no non-single products for {NEXT}'
    assert catalog() == before


def test_the_taxonomy_box_sets_by_name_and_not_used_categories_skipped(day_one, frozen_clock):
    """Owner taxonomy (2026-11-20): Box Sets are sealed box sets except a name with `deck` (the
    Trial Decks: champion decks); a case is a booster box; every accessory subcategory is an
    accessory with its Cardmarket category kept; Cardmarket Sets (`RB Set`) and Sealed Products
    are not used: no `rbproducts` row is created, a row stored before is unlisted, never
    deleted, and its kind is left alone; a locked kind is never touched."""
    box_sets = 'Riftbound Riftbound Box Sets'
    rows = (
        (200, 'Jinx Trial Deck', box_sets, False, 'champion_deck'),
        (201, 'Bulk Runes Box', box_sets, False, 'sealed_box_set'),
        (203, 'Viktor Trial Deck', box_sets, True, 'other'),       # locked
        (204, 'Legacy Vault', box_sets, True, 'other'),            # locked
        (205, 'Spiritforged: Pre-Rift Event Kit', box_sets, False, 'sealed_box_set'),
        (206, 'K/DA Couture Collection Box', box_sets, False, 'sealed_box_set'),
        (207, 'Worlds Bundle 2025', box_sets, False, 'sealed_box_set'),
    )
    for pid, name, category, _, _ in rows:
        cm(DAY, pid, name, category, expansion=1)
    # rows of before the taxonomy: all `other`; 203 and 204 locked by the admin
    for pid, _, _, locked, _ in rows[:4]:
        db.session.add(RbProducts(rbpdt_id_product=pid, rbpdt_name='x', rbpdt_type='nonsingle',
                                  rbpdt_kind='other', rbpdt_kind_locked=locked))
    cm(DAY, 209, 'Yasuo Trial Deck', box_sets, expansion=1)
    cm(DAY, 210, 'Origins Case', 'Riftbound Display', expansion=1)
    cm(DAY, 211, 'Jinx Sleeves', 'Riftbound Sleeves', expansion=1)
    cm(DAY, 212, 'Rift Playmat', 'Playmats')
    # not used: Sets and Sealed Products; 220 has a row from before the taxonomy
    cm(DAY, 220, 'Origins: Full Set', 'RB Set', expansion=1)
    cm(DAY, 221, 'Origins: Rare Set', 'RB Set', expansion=1)
    cm(DAY, 222, 'Origins Sealed Lot', 'Riftbound Sealed Products', expansion=1)
    db.session.add(RbProducts(rbpdt_id_product=220, rbpdt_name='Origins: Full Set',
                              rbpdt_category='RB Set', rbpdt_type='nonsingle',
                              rbpdt_kind='other', rbpdt_listed=True, rbpdt_updated_at=NOON))
    db.session.commit()
    later = frozen_clock.advance(hours=1)
    assert refresh_products(DAY) == {'date': DAY, 'new': 4 + 3 + 4, 'updated': 4,
                                     'not_listed': 1, 'skipped': 3, 'total': 4 + 4 + 3 + 4 + 1}
    stored = {row[0]: row for row in catalog()}
    assert {pid: (stored[pid][4], stored[pid][7]) for pid, *_ in rows} == {
        pid: (kind, locked) for pid, _, _, locked, kind in rows}
    assert stored[209][4] == 'champion_deck'
    assert stored[210][4] == 'booster_box'
    assert stored[211][3:5] == ('Riftbound Sleeves', 'accessory')
    assert stored[212][3:5] == ('Playmats', 'accessory')
    assert 221 not in stored and 222 not in stored
    assert stored[220] == (220, None, 'Origins: Full Set', 'RB Set', 'other', 'nonsingle',
                           False, False, False, False, later)
