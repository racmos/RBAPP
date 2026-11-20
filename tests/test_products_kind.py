"""Product kinds taxonomy (owner decision 2026-11-20): `kind_for(category, name=None)`, the
Cardmarket category -> our product kind, and its SQL twin `kind_sql`.

Cardmarket category -> our kind:
  Singles        -> `card` (virtual: singles are cards, never catalog products; not this function)
  Booster        -> `booster`
  Booster Boxes  -> `booster_box` (Cardmarket's `Display`; a case is a booster box too)
  Sets           -> not used (`unused`: `RB Set`, a pack of one card of each rarity)
  Sealed Products-> not used (`unused`)
  Champion Decks -> `champion_deck`
  Box Sets       -> `sealed_box_set`; NAME RULE (owner, 2026-11-20, removable): a product whose
                    name has `deck` (the Trial Decks) is a `champion_deck`
  Accessories    -> `accessory`, every subcategory (sleeves, playmats, binders, deck boxes, dice,
                    tokens...; the category name is kept in `rbpdt_category`)
  anything else  -> `other`
`kind_sql(category, name)` is the same rules as SQL and must agree with `kind_for` on every case.
"""
import pytest
import sqlalchemy as sa

from app import db
from app.models.cardmarket import NOT_USED_KIND, PRODUCT_KINDS
from app.services.products import kind_for, kind_sql

# Every non-single category of the dev database (2026-10-28, 2026-11-20), without a name
PREFLIGHT = [
    ('Riftbound Booster', 'booster'),
    ('Riftbound Riftbound Box Sets', 'sealed_box_set'),
    ('Riftbound Display', 'booster_box'),
    ('RB Set', 'unused'),
    ('Riftbound Champion Decks', 'champion_deck'),
]

BOX_SETS = 'Riftbound Riftbound Box Sets'

# The real products of the dev database (2026-11-20): (category, name, kind)
REAL = [
    *((BOX_SETS, f'{champion} Trial Deck', 'champion_deck')
      for champion in ('Jinx', 'Viktor', 'Volibear', 'Yasuo')),
    *((BOX_SETS, name, 'sealed_box_set') for name in (
        'Bulk Runes Box', 'Proving Grounds', 'Proving Grounds (French)', 'Arcane Box Set',
        'Arcane Box Set (Chinese)', 'Worlds Bundle 2025', 'Worlds Bundle 2026',
        'Spiritforged: Pre-Rift Event Kit', 'Lunar Revel Bundle', 'Unleashed Vault',
        'Vendetta Vault', 'Vendetta Vault (French)', 'Vendetta: Pre-Rift Event Kit',
        'Unleashed: Prize Wall Rune Bundle', '1 Year Anniversary Box (Chinese)',
        'Gift of the Rift Bundle', 'Radiance Vault', 'Radiance: Pre-Rift Event Kit',
        'Secret Garden Box Set', 'Riftbound x T1 2025 Worlds Champion Signature Edition',
        'Legacy Vault', 'K/DA Couture Collection Box')),
    *(('RB Set', f'Origins: {rarity} Set', 'unused')
      for rarity in ('Common', 'Uncommon', 'Rare', 'Epic', 'Full')),
    ('Riftbound Champion Decks', 'Jinx Champion Deck', 'champion_deck'),
    ('Riftbound Booster', 'Origins Booster', 'booster'),
    ('Riftbound Display', 'Origins Booster Display', 'booster_box'),
    ('Riftbound Display', 'Origins Case', 'booster_box'),
]

# The Box Sets name rule (case-insensitive) and what it leaves alone
NAMED = [
    ('Box Set', 'Some Deck', 'champion_deck'),
    ('box sets', 'JINX TRIAL DECK', 'champion_deck'),
    ('RIFTBOUND RIFTBOUND BOX SETS', 'Arcane Deck', 'champion_deck'),
    ('Box Sets', 'Anything', 'sealed_box_set'),
    (BOX_SETS, '', 'sealed_box_set'),
    (BOX_SETS, None, 'sealed_box_set'),
    # the name counts only in a box set category
    ('Riftbound Booster', 'Jinx Trial Deck', 'booster'),
    ('Riftbound Display', 'Trial Deck Display', 'booster_box'),
    ('RB Set', 'Jinx Trial Deck', 'unused'),
    ('Riftbound Sealed Products', 'Jinx Trial Deck', 'unused'),
    ('Sleeves', 'Trial Deck Sleeves', 'accessory'),
    (None, 'Jinx Trial Deck', 'other'),
    # an earlier rule still wins
    ('Booster Box Set', 'Trial Deck', 'booster_box'),
    ('Booster Set', None, 'booster'),
]


@pytest.mark.parametrize('category, name, kind', REAL + NAMED)
def test_real_products_and_the_box_sets_name_rule(category, name, kind):
    assert kind_for(category, name) == kind


@pytest.mark.parametrize('category, name, kind', REAL)
def test_the_name_is_a_keyword(category, name, kind):
    assert kind_for(category, name=name) == kind


@pytest.mark.parametrize('category, kind', PREFLIGHT)
def test_every_preflight_category(category, kind):
    assert kind_for(category) == kind


RULES = [
    # Cardmarket Sealed Products -> not used
    ('Sealed Products', 'unused'),
    ('Riftbound Sealed Products', 'unused'),
    ('Sealed Product', 'unused'),
    # Cardmarket Sets (a category ending in `set` / `sets`, not a box set) -> not used
    ('RB Set', 'unused'),
    ('Sets', 'unused'),
    ('Riftbound Sets', 'unused'),
    ('rb sets', 'unused'),
    ('Promo Set', 'unused'),
    # every accessory subcategory -> accessory
    ('Accessories', 'accessory'),
    ('Riftbound Accessories', 'accessory'),
    ('Sleeves', 'accessory'),
    ('Card Sleeve', 'accessory'),
    ('Playmats', 'accessory'),
    ('Play Mats', 'accessory'),
    ('Binders', 'accessory'),
    ('Albums', 'accessory'),
    ('Portfolios', 'accessory'),
    ('Deck Boxes', 'accessory'),
    ('Deck Box', 'accessory'),
    ('Storage Boxes', 'accessory'),
    ('Dice', 'accessory'),
    ('Tokens', 'accessory'),
    ('Life Counters', 'accessory'),
    ('Card Protectors', 'accessory'),
    # Booster Boxes / Display / a case -> booster box
    ('Booster Boxes', 'booster_box'),
    ('Booster Box', 'booster_box'),
    ('Riftbound Display', 'booster_box'),
    ('Booster Box Case', 'booster_box'),
    ('Display Case', 'booster_box'),
    # Booster -> booster
    ('Booster', 'booster'),
    ('Booster Pack', 'booster'),
    # Box Sets (and the old bundle / gift words) -> sealed box set
    ('Box Sets', 'sealed_box_set'),
    ('Bundle', 'sealed_box_set'),
    ('Gift Set', 'sealed_box_set'),
    # Champion Decks (and the old starter / deck words) -> champion deck
    ('Champion Decks', 'champion_deck'),
    ('Starter Deck', 'champion_deck'),
    ('Proving Grounds Starter', 'champion_deck'),
    # anything else -> other
    ('Riftbound Single', 'other'),
    ('Settings', 'other'),
    ('Set Pieces', 'other'),
    ('', 'other'),
    (None, 'other'),
]


@pytest.mark.parametrize('category, kind', RULES)
def test_each_rule(category, kind):
    assert kind_for(category) == kind


CASES = [
    ('BOOSTER BOX CASE', 'booster_box'),
    ('booster boxes', 'booster_box'),
    ('DeCk BoX', 'accessory'),
    ('SLEEVES', 'accessory'),
    ('SEALED PRODUCTS', 'unused'),
    ('RB SET', 'unused'),
]


@pytest.mark.parametrize('category, kind', CASES)
def test_matching_ignores_case(category, kind):
    assert kind_for(category) == kind


ORDER = [
    ('Sealed Products Booster', 'unused'),          # not used before anything else
    ('Booster Box Sleeves', 'accessory'),           # an accessory before box and booster
    ('Deck Box Case', 'accessory'),                 # deck box is an accessory, not a case
    ('Starter Deck Box', 'accessory'),
    ('Booster Display Case', 'booster_box'),
    ('Booster Bundle', 'booster'),                  # booster before bundle
    ('Gift Deck', 'sealed_box_set'),                # gift before deck
    ('Champion Deck Set', 'champion_deck'),         # a deck before the sets rule
]


@pytest.mark.parametrize('category, kind', ORDER)
def test_the_first_rule_that_matches_wins(category, kind):
    assert kind_for(category) == kind


def test_the_stored_kinds_and_the_virtual_ones():
    assert PRODUCT_KINDS == ('booster', 'booster_box', 'champion_deck', 'sealed_box_set',
                             'accessory', 'other')
    assert NOT_USED_KIND == 'unused'
    assert NOT_USED_KIND not in PRODUCT_KINDS and 'card' not in PRODUCT_KINDS
    every = {kind for _, kind in PREFLIGHT + RULES + CASES + ORDER}
    assert every == set(PRODUCT_KINDS) | {NOT_USED_KIND}


EVERY_CASE = ([(category, None, kind) for category, kind in PREFLIGHT + RULES + CASES + ORDER]
              + REAL + NAMED)


def text(value):
    return sa.cast(sa.literal(value), sa.Text)


@pytest.mark.parametrize('category, name, kind', EVERY_CASE)
def test_kind_sql_agrees_with_kind_for(app, category, name, kind):
    got = db.session.execute(sa.select(kind_sql(text(category), text(name))))
    assert got.scalar_one() == kind_for(category, name) == kind


@pytest.mark.parametrize('category, kind', PREFLIGHT + RULES + CASES + ORDER)
def test_kind_sql_without_a_name(app, category, kind):
    got = db.session.execute(sa.select(kind_sql(text(category))))
    assert got.scalar_one() == kind
