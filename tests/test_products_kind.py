"""F14-a S3 (AC2): `kind_for(category)`, the Cardmarket category -> product kind rules."""
import pytest

from app.models.cardmarket import PRODUCT_KINDS
from app.services.products import kind_for


# S1(a) on the dev database (2026-10-28): every non-single category and its kind.
# 'Riftbound Riftbound Box Sets' and 'RB Set' end in `other` (listed in the PR for the owner).
PREFLIGHT = [
    ('Riftbound Booster', 'booster'),
    ('Riftbound Riftbound Box Sets', 'other'),
    ('Riftbound Display', 'box'),
    ('RB Set', 'other'),
    ('Riftbound Champion Decks', 'starter'),
]


@pytest.mark.parametrize('category, kind', PREFLIGHT)
def test_every_preflight_category(category, kind):
    assert kind_for(category) == kind


@pytest.mark.parametrize('category, kind', [
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
])
def test_each_rule(category, kind):
    assert kind_for(category) == kind


@pytest.mark.parametrize('category, kind', [
    ('BOOSTER BOX CASE', 'case'),
    ('booster box', 'box'),
    ('DeCk BoX', 'accessory'),
    ('SLEEVES', 'sleeves'),
])
def test_matching_ignores_case(category, kind):
    assert kind_for(category) == kind


@pytest.mark.parametrize('category, kind', [
    ('Booster Display Case', 'case'),     # case before box and booster
    ('Booster Box', 'box'),               # booster box before booster
    ('Booster Bundle', 'booster'),        # booster before bundle
    ('Gift Deck', 'bundle'),              # gift before deck
    ('Starter Deck Box', 'starter'),      # starter wins before the deck box rule
    ('Deck Box Sleeves', 'sleeves'),      # deck box is not a deck; sleeve comes first
    ('Deck Box', 'accessory'),
])
def test_the_first_rule_that_matches_wins(category, kind):
    assert kind_for(category) == kind


def test_every_kind_is_allowed_by_the_check():
    assert set(kind for _, kind in PREFLIGHT) <= set(PRODUCT_KINDS)
    assert PRODUCT_KINDS == ('booster', 'box', 'case', 'bundle', 'starter', 'sleeves',
                             'accessory', 'other')
