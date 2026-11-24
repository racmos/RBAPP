"""CM-m S5 (owner decision 2026-11-24): a product of one card group with no price in the latest
load is the HIGHEST rarity. It sorts after every priced product, so it takes the highest-rank
printing while the cheapest priced product takes the lowest one; before, it counted as 0 and
took the lowest, and Auto-match refused to pair a group that had an unpriced product.

Covered here: the matcher's proposal (`auto_match`), the daily decision
(`daily_prices.classify_unmapped` through `_paired_by_rank`: one unpriced product and the right
number of printings is a clear case, two unpriced products stay ambiguous, the foil pair of a
common stays ambiguous) and the CM-h promo plan (`_Plans._pair`). The CM-k2 plated plan
(`_plated_items`) and the real PLAT pair 922477 / 922511 are pinned in
tests/test_promo_cards_plated.py.

"No price" is either no price row in the load or a row whose prices are all empty.
"""
import pytest

from app import db
from app.models import RbCard, RbSet
from app.models.cardmarket import RbcmExpansion, RbcmPrice, RbcmProduct, RbcmProductCardMap
from app.services import daily_prices, promo_cards
from app.services import cardmarket_matcher as matcher

DATE = '20301102'


def card(set_id, car_id, name, rarity, card_type='Unit', **extra):
    db.session.add(RbCard(rbcar_rbset_id=set_id, rbcar_id=car_id, rbcar_name=name,
                          rbcar_rarity=rarity, rbcar_type=card_type, **extra))


def product(id_product, name, metacard, low, expansion=6286, empty_row=False):
    """`low=None`: no price row, or (`empty_row`) a price row with every price empty."""
    db.session.add(RbcmProduct(rbprd_date=DATE, rbprd_id_product=id_product, rbprd_name=name,
                               rbprd_id_metacard=metacard, rbprd_id_expansion=expansion,
                               rbprd_type='single', rbprd_category_name='Riftbound Single'))
    if low is not None or empty_row:
        db.session.add(RbcmPrice(rbprc_date=DATE, rbprc_id_product=id_product, rbprc_low=low))


@pytest.fixture
def catalog(app):
    for set_id, name in (('OGN', 'Origins'), ('OGNX', 'Origins Promos')):
        db.session.add(RbSet(rbset_id=set_id, rbset_name=name))
    db.session.flush()
    db.session.add(RbcmExpansion(rbexp_id=6286, rbexp_name='Origins', rbexp_rbset_id='OGN'))
    db.session.add(RbcmExpansion(rbexp_id=6322, rbexp_name='Origins Promos',
                                 rbexp_rbset_id='OGNX'))
    db.session.commit()
    return app


def proposals():
    return {s['id_product']: (s['rbset_id'], s['rbcar_id'], s['rbpcm_foil'])
            for s in matcher.auto_match(dry_run=True)['samples']}


def decided():
    result = daily_prices.classify_unmapped(DATE)
    return dict(result['links']), {item['product_id']: item['reason']
                                   for item in result['review']}


class TestPriceOrder:
    def test_priced_ascending_then_unpriced(self):
        values = [5.0, None, 0.02, 0.0, 450.0]
        assert sorted(values, key=matcher.price_order) == [0.02, 5.0, 450.0, None, 0.0]


class TestMatcherAndDailyDecision:
    @pytest.mark.parametrize('empty_row', [False, True])
    def test_one_unpriced_product_takes_the_highest_printing_and_both_are_clear(
            self, catalog, empty_row):
        card('OGN', '141', 'Hexplosives Expert', 'Rare', 'Legend', rbcar_tags='Ziggs')
        card('OGN', '169', 'Hexplosives Expert', 'Showcase', 'Legend', rbcar_tags='Ziggs')
        product(10, 'Ziggs, Hexplosives Expert', 70, None, empty_row=empty_row)
        product(11, 'Ziggs, Hexplosives Expert', 70, 0.02)
        db.session.commit()
        assert proposals() == {11: ('OGN', '141', None), 10: ('OGN', '169', None)}
        links, review = decided()
        assert links == {11: ('OGN', '141', None), 10: ('OGN', '169', None)}
        assert review == {}

    def test_the_unpriced_product_is_last_whatever_the_product_ids(self, catalog):
        card('OGN', '060', 'Twin Star', 'Rare')
        card('OGN', '060a', 'Twin Star', 'Rare')
        card('OGN', '060s', 'Twin Star', 'Rare')
        product(70, 'Twin Star', 40, 30.0)
        product(71, 'Twin Star', 40, None)
        product(72, 'Twin Star', 40, 1.0)
        db.session.commit()
        links, review = decided()
        assert links == {72: ('OGN', '060', None), 70: ('OGN', '060a', None),
                         71: ('OGN', '060s', None)}
        assert review == {}

    def test_two_unpriced_products_in_one_group_stay_ambiguous(self, catalog):
        card('OGN', '061', 'Same Cost', 'Rare')
        card('OGN', '061a', 'Same Cost', 'Rare')
        card('OGN', '061s', 'Same Cost', 'Rare')
        product(73, 'Same Cost', 41, 2.0)
        product(74, 'Same Cost', 41, None)
        product(75, 'Same Cost', 41, None, empty_row=True)
        db.session.commit()
        links, review = decided()
        assert links == {}
        assert review == {73: 'ambiguous', 74: 'ambiguous', 75: 'ambiguous'}

    def test_an_unpriced_product_does_not_settle_more_products_than_printings(self, catalog):
        card('OGN', '062', 'Crowded', 'Rare')
        card('OGN', '062s', 'Crowded', 'Showcase')
        product(76, 'Crowded', 42, 1.0)
        product(77, 'Crowded', 42, 3.0)
        product(78, 'Crowded', 42, None)
        db.session.commit()
        links, review = decided()
        assert links == {} and set(review.values()) == {'ambiguous'}

    def test_the_foil_pair_of_a_common_stays_ambiguous_with_an_unpriced_product(self, catalog):
        """CM-h decision A is unchanged: a common has a normal and a foil product."""
        card('OGN', '063', 'Plain Twin', 'Common')
        product(79, 'Plain Twin', 43, None)
        product(80, 'Plain Twin (Foil)', 43, 0.9)
        db.session.commit()
        links, review = decided()
        assert links == {} and review == {79: 'ambiguous', 80: 'ambiguous'}

    def test_equal_priced_products_still_stay_ambiguous(self, catalog):
        card('OGN', '064', 'Even', 'Rare')
        card('OGN', '064a', 'Even', 'Rare')
        card('OGN', '064s', 'Even', 'Rare')
        product(81, 'Even', 44, 2.0)
        product(82, 'Even', 44, 2.0)
        product(83, 'Even', 44, None)
        db.session.commit()
        links, review = decided()
        assert links == {} and set(review.values()) == {'ambiguous'}

    def test_the_slot_owner_rule_is_unchanged(self, catalog):
        """#162: the product of the card's own set owns a slot a promo fallback also wants."""
        card('OGN', '090', 'Vi, Destructive', 'Rare')
        product(84, 'Vi, Destructive', 50, None, expansion=6286)
        product(85, 'Vi, Destructive', 50, 50.0, expansion=6322)
        db.session.commit()
        links, review = decided()
        assert links == {84: ('OGN', '090', None)} and review == {85: 'conflict'}


class TestPromoPlan:
    """CM-h `_Plans._pair`: the unpriced product of a group takes the highest-rank promo card."""

    def test_the_unpriced_product_becomes_the_higher_promo_card(self, catalog):
        card('OGN', '050', 'Echo', 'Epic')
        card('OGN', '050a', 'Echo', 'Showcase')
        product(1005, 'Echo', 32, None, expansion=6322)
        product(1006, 'Echo', 32, 1.0, expansion=6322)
        db.session.commit()
        items = {item['product_id']: item for item in promo_cards.plan('OGNX')['items']}
        # promo ranks: OGNX/050a (showcase variant) below OGNX/050 (epic in a promo set)
        assert items[1006]['proposed'] == {'set_id': 'OGNX', 'card_id': '050a'}
        assert items[1005]['proposed'] == {'set_id': 'OGNX', 'card_id': '050'}
        assert items[1005]['price'] is None

    def test_a_common_promo_card_lists_the_priced_product_first(self, catalog):
        card('OGN', '010', 'Little Spark', 'Common')
        product(1002, 'Little Spark', 31, None, expansion=6322)
        product(1003, 'Little Spark (Foil)', 31, 2.0, expansion=6322)
        db.session.commit()
        item = promo_cards.plan('OGNX')['items'][0]
        assert item['product_ids'] == [1003, 1002]
        assert [(one['id'], one['foil']) for one in item['products']] == [(1003, 'N'),
                                                                         (1002, 'S')]

    def test_after_creation_the_matcher_pairs_as_the_plan_said(self, catalog):
        card('OGN', '050', 'Echo', 'Epic')
        card('OGN', '050a', 'Echo', 'Showcase')
        product(1005, 'Echo', 32, None, expansion=6322)
        product(1006, 'Echo', 32, 1.0, expansion=6322)
        db.session.commit()
        promo_cards.create('OGNX', [1005, 1006])
        db.session.commit()
        links, review = decided()
        assert links == {1006: ('OGNX', '050a', None), 1005: ('OGNX', '050', None)}
        assert review == {}


def test_a_linked_product_keeps_its_card(catalog):
    card('OGN', '141', 'Hexplosives Expert', 'Rare', 'Legend', rbcar_tags='Ziggs')
    card('OGN', '169', 'Hexplosives Expert', 'Showcase', 'Legend', rbcar_tags='Ziggs')
    product(10, 'Ziggs, Hexplosives Expert', 70, None)
    product(11, 'Ziggs, Hexplosives Expert', 70, 0.02)
    db.session.add(RbcmProductCardMap(rbpcm_id_product=11, rbpcm_rbset_id='OGN',
                                      rbpcm_rbcar_id='141', rbpcm_foil=None,
                                      rbpcm_match_type='manual'))
    db.session.commit()
    links, review = decided()
    assert links == {10: ('OGN', '169', None)} and review == {}
