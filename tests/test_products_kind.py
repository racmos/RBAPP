"""F14-a S3 (AC2): `kind_for(category, name=None)`, the Cardmarket category -> product kind
rules.

CM-g (owner, 2026-11-20, after looking at the real products): 'Riftbound Riftbound Box Sets' is
Cardmarket's category of boxed, promotional and collection products, and the product NAME
decides: a name with `deck` (the trial decks, champion decks for the owner) is a starter,
anything else there (vaults, event kits, bundles, collection boxes, the runes box) is a bundle
("Bundle / set"). 'RB Set' (loose cards by rarity, not sold) gets no rule: it stays `other`.
The name is read only by the box set rule; every other mapping is unchanged. `kind_sql(category,
name)` is the same rules as SQL (the expansion products filter and counters) and must agree with
`kind_for` on every case below.
"""
import pytest
import sqlalchemy as sa

from app import db
from app.models.cardmarket import PRODUCT_KINDS
from app.services.products import kind_for, kind_sql


# S1(a) on the dev database (2026-10-28): every non-single category and its kind, without a
# name. CM-g (2026-11-20): 'Riftbound Riftbound Box Sets' was `other`; now `bundle` (a starter
# only by its name). 'RB Set' stays `other`.
PREFLIGHT = [
    ('Riftbound Booster', 'booster'),
    ('Riftbound Riftbound Box Sets', 'bundle'),
    ('Riftbound Display', 'box'),
    ('RB Set', 'other'),
    ('Riftbound Champion Decks', 'starter'),
]

BOX_SETS = 'Riftbound Riftbound Box Sets'

# CM-g: the real products of the dev database (2026-11-20): (category, name, kind)
REAL = [
    *((BOX_SETS, f'{champion} Trial Deck', 'starter')
      for champion in ('Jinx', 'Viktor', 'Volibear', 'Yasuo')),
    *((BOX_SETS, name, 'bundle') for name in (
        'Bulk Runes Box', 'Proving Grounds', 'Proving Grounds (French)', 'Arcane Box Set',
        'Arcane Box Set (Chinese)', 'Worlds Bundle 2025', 'Worlds Bundle 2026',
        'Spiritforged: Pre-Rift Event Kit', 'Lunar Revel Bundle', 'Unleashed Vault',
        'Vendetta Vault', 'Vendetta Vault (French)', 'Vendetta: Pre-Rift Event Kit',
        'Unleashed: Prize Wall Rune Bundle', '1 Year Anniversary Box (Chinese)',
        'Gift of the Rift Bundle', 'Radiance Vault', 'Radiance: Pre-Rift Event Kit',
        'Secret Garden Box Set', 'Riftbound x T1 2025 Worlds Champion Signature Edition',
        'Legacy Vault', 'K/DA Couture Collection Box')),
    *(('RB Set', f'Origins: {rarity} Set', 'other')
      for rarity in ('Common', 'Uncommon', 'Rare', 'Epic', 'Full')),
    ('Riftbound Champion Decks', 'Jinx Champion Deck', 'starter'),
    ('Riftbound Booster', 'Origins Booster', 'booster'),
    ('Riftbound Display', 'Origins Booster Display', 'box'),
]

# CM-g: the box set name rule (case-insensitive, singular or plural) and what it leaves alone
NAMED = [
    ('Box Set', 'Some Deck', 'starter'),
    ('box sets', 'JINX TRIAL DECK', 'starter'),
    ('RIFTBOUND RIFTBOUND BOX SETS', 'Arcane Deck', 'starter'),
    ('Box Sets', 'Anything', 'bundle'),
    (BOX_SETS, '', 'bundle'),
    (BOX_SETS, None, 'bundle'),
    # the name counts only in a box set category
    ('Riftbound Booster', 'Jinx Trial Deck', 'booster'),
    ('Riftbound Display', 'Trial Deck Display', 'box'),
    ('RB Set', 'Jinx Trial Deck', 'other'),
    ('RB Set', None, 'other'),
    ('rb sets', 'Vault', 'other'),
    ('Promo Set', 'Trial Deck', 'other'),
    (None, 'Jinx Trial Deck', 'other'),
    # an earlier rule still wins
    ('Booster Box Set', 'Trial Deck', 'box'),
    ('Booster Set', None, 'booster'),
    # `set` alone is not the box set rule
    ('Promo Set', None, 'other'),
    ('Riftbound Set', None, 'other'),
]


@pytest.mark.parametrize('category, name, kind', REAL + NAMED)
def test_rb_set_and_box_set_names(category, name, kind):
    assert kind_for(category, name) == kind


@pytest.mark.parametrize('category, name, kind', REAL)
def test_the_name_is_a_keyword(category, name, kind):
    assert kind_for(category, name=name) == kind


@pytest.mark.parametrize('category, kind', PREFLIGHT)
def test_every_preflight_category(category, kind):
    assert kind_for(category) == kind


RULES = [
    # contains `case` -> case
    ('Booster Box Case', 'case'),
    ('Display Case', 'case'),
    # `booster box` or `display` -> box
    ('Booster Box', 'box'),
    ('Riftbound Display', 'box'),
    # `booster` -> booster
    ('Booster', 'booster'),
    ('Booster Pack', 'booster'),
    # `bundle` or `gift` -> bundle
    ('Bundle', 'bundle'),
    ('Gift Set', 'bundle'),
    # `starter` or `deck` (not `deck box`) -> starter
    ('Starter Deck', 'starter'),
    ('Champion Deck', 'starter'),
    ('Proving Grounds Starter', 'starter'),
    # `sleeve` -> sleeves
    ('Sleeves', 'sleeves'),
    ('Card Sleeve', 'sleeves'),
    # `deck box`, `playmat`, `binder`, `accessor`, `dice`, `token` -> accessory
    ('Deck Box', 'accessory'),
    ('Playmat', 'accessory'),
    ('Binder', 'accessory'),
    ('Accessories', 'accessory'),
    ('Dice', 'accessory'),
    ('Tokens', 'accessory'),
    # anything else -> other
    ('Promo Set', 'other'),
    ('', 'other'),
    (None, 'other'),
]


@pytest.mark.parametrize('category, kind', RULES)
def test_each_rule(category, kind):
    assert kind_for(category) == kind


CASES = [
    ('BOOSTER BOX CASE', 'case'),
    ('booster box', 'box'),
    ('DeCk BoX', 'accessory'),
    ('SLEEVES', 'sleeves'),
]


@pytest.mark.parametrize('category, kind', CASES)
def test_matching_ignores_case(category, kind):
    assert kind_for(category) == kind


ORDER = [
    ('Booster Display Case', 'case'),     # case before box and booster
    ('Booster Box', 'box'),               # booster box before booster
    ('Booster Bundle', 'booster'),        # booster before bundle
    ('Gift Deck', 'bundle'),              # gift before deck
    ('Starter Deck Box', 'starter'),      # starter wins before the deck box rule
    ('Deck Box Sleeves', 'sleeves'),      # deck box is not a deck; sleeve comes first
    ('Deck Box', 'accessory'),
]


@pytest.mark.parametrize('category, kind', ORDER)
def test_the_first_rule_that_matches_wins(category, kind):
    assert kind_for(category) == kind


def test_every_kind_is_allowed_by_the_check():
    assert set(kind for _, kind in PREFLIGHT) <= set(PRODUCT_KINDS)
    assert PRODUCT_KINDS == ('booster', 'box', 'case', 'bundle', 'starter', 'sleeves',
                             'accessory', 'other')


EVERY_CASE = ([(category, None, kind) for category, kind in
               PREFLIGHT + RULES + CASES + ORDER + [('Riftbound Single', 'other')]]
              + REAL + NAMED)


def text(value):
    return sa.cast(sa.literal(value), sa.Text)


@pytest.mark.parametrize('category, name, kind', EVERY_CASE)
def test_kind_sql_agrees_with_kind_for(app, category, name, kind):
    got = db.session.execute(sa.select(kind_sql(text(category), text(name))))
    assert got.scalar_one() == kind_for(category, name) == kind


@pytest.mark.parametrize('category, kind', PREFLIGHT + RULES)
def test_kind_sql_without_a_name(app, category, kind):
    got = db.session.execute(sa.select(kind_sql(text(category))))
    assert got.scalar_one() == kind
