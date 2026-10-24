"""F4-b S4/S5: clear-case linking and the review list
(`app.services.daily_prices.match_clear_cases`), on rows written directly.

Clear case = a metacard group with exactly one unmapped product and exactly one
free candidate card; everything else is listed for review and never linked."""
import pytest
import sqlalchemy as sa

from app import db
from app.models import (RbCard, RbSet, RbcmExpansion, RbcmIgnored, RbcmPrice, RbcmProduct,
                        RbcmProductCardMap)
from app.services import daily_prices

DATE = '20300101'


@pytest.fixture
def catalog(app):
    db.session.add(RbSet(rbset_id='OGN', rbset_name='Origins', rbset_ncard=300))
    db.session.add(RbSet(rbset_id='SFD', rbset_name='Spiritforged', rbset_ncard=300))
    db.session.commit()

    def card(car_id, name, rarity='rare', set_id='OGN', card_type='Unit'):
        db.session.add(RbCard(rbcar_rbset_id=set_id, rbcar_id=car_id, rbcar_name=name,
                              rbcar_type=card_type, rbcar_rarity=rarity))
        db.session.commit()

    return card


def product(id_product, name, metacard, date=DATE, kind='single', expansion=6286, price=1.0):
    db.session.add(RbcmProduct(rbprd_date=date, rbprd_id_product=id_product, rbprd_name=name,
                               rbprd_id_metacard=metacard, rbprd_id_expansion=expansion,
                               rbprd_type=kind))
    db.session.add(RbcmPrice(rbprc_date=date, rbprc_id_product=id_product, rbprc_low=price))
    db.session.commit()


def mapped(id_product, set_id, car_id, foil=None):
    db.session.add(RbcmProductCardMap(rbpcm_id_product=id_product, rbpcm_rbset_id=set_id,
                                      rbpcm_rbcar_id=car_id, rbpcm_foil=foil,
                                      rbpcm_match_type='manual'))
    db.session.commit()


def mappings():
    db.session.expire_all()
    return [(m.rbpcm_id_product, m.rbpcm_rbset_id, m.rbpcm_rbcar_id, m.rbpcm_foil,
             m.rbpcm_match_type, float(m.rbpcm_confidence) if m.rbpcm_confidence else None)
            for m in db.session.execute(sa.select(RbcmProductCardMap)
                                        .order_by(RbcmProductCardMap.rbpcm_id_product)).scalars()]


def reasons(result):
    return [(item['product_id'], item['reason']) for item in result['review']]


def test_one_product_and_one_card_is_linked(catalog):
    catalog('010', 'Lone Wolf')
    product(1, 'Lone Wolf (Showcase)', metacard=10)
    result = daily_prices.match_clear_cases(DATE)
    assert result == {'auto_match': {'linked': 1, 'proposed': 1, 'review': 0},
                      'review': [], 'review_total': 0}
    assert mappings() == [(1, 'OGN', '010', None, 'auto', 0.7)]


def test_a_common_card_gets_the_slot_the_matcher_proposes(catalog):
    catalog('011', 'Little Spark', rarity='common')
    mapped(50, 'OGN', '011', 'N')              # the normal version is already linked
    product(2, 'Little Spark (Foil)', metacard=11)
    result = daily_prices.match_clear_cases(DATE)
    assert result['auto_match'] == {'linked': 1, 'proposed': 1, 'review': 0}
    assert mappings() == [(2, 'OGN', '011', 'S', 'auto', 0.7),
                          (50, 'OGN', '011', 'N', 'manual', None)]


def test_several_products_in_a_group_are_ambiguous(catalog):
    catalog('012', 'Twin Blade', rarity='common')
    product(3, 'Twin Blade V.1', metacard=12, price=0.1)
    product(4, 'Twin Blade V.2', metacard=12, price=2.0)
    result = daily_prices.match_clear_cases(DATE)
    # the matcher pairs them by price order; that is not a clear case
    assert result['auto_match'] == {'linked': 0, 'proposed': 2, 'review': 2}
    assert reasons(result) == [(3, 'ambiguous'), (4, 'ambiguous')]
    assert result['review'][0]['candidates'] == [{'set': 'OGN', 'id': '012',
                                                  'name': 'Twin Blade'}]
    assert mappings() == []


def test_several_candidate_cards_are_ambiguous(catalog):
    catalog('013', 'Echo')
    catalog('013a', 'Echo', rarity='epic')
    product(5, 'Echo (Showcase)', metacard=13)
    result = daily_prices.match_clear_cases(DATE)
    assert result['auto_match'] == {'linked': 0, 'proposed': 1, 'review': 1}
    assert result['review'] == [{
        'product_id': 5, 'name': 'Echo (Showcase)', 'expansion_id': 6286,
        'reason': 'ambiguous',
        'candidates': [{'set': 'OGN', 'id': '013', 'name': 'Echo'},
                       {'set': 'OGN', 'id': '013a', 'name': 'Echo'}]}]
    assert mappings() == []


def test_no_candidates(catalog):
    product(6, 'Nobody Known', metacard=14)
    product(7, 'No Metacard', metacard=None)
    result = daily_prices.match_clear_cases(DATE)
    assert result['auto_match'] == {'linked': 0, 'proposed': 0, 'review': 2}
    assert result['review'] == [
        {'product_id': 6, 'name': 'Nobody Known', 'expansion_id': 6286,
         'reason': 'no_candidates', 'candidates': []},
        {'product_id': 7, 'name': 'No Metacard', 'expansion_id': 6286,
         'reason': 'no_candidates', 'candidates': []}]


def test_an_ignored_pair_is_listed_and_never_linked(catalog):
    catalog('015', 'Quiet One')
    product(8, 'Quiet One (Promo)', metacard=15)
    db.session.add(RbcmIgnored(rbig_id_product=8, rbig_name='Quiet One (Promo)'))
    db.session.commit()
    result = daily_prices.match_clear_cases(DATE)
    assert result['auto_match'] == {'linked': 0, 'proposed': 0, 'review': 1}
    assert result['review'] == [{
        'product_id': 8, 'name': 'Quiet One (Promo)', 'expansion_id': 6286,
        'reason': 'ignored_pair', 'candidates': [{'set': 'OGN', 'id': '015',
                                                  'name': 'Quiet One'}]}]
    assert mappings() == []


def test_a_taken_slot_is_a_conflict(catalog):
    catalog('016', 'Taken Spot')
    mapped(51, 'OGN', '016')
    product(9, 'Taken Spot (Showcase)', metacard=16)
    result = daily_prices.match_clear_cases(DATE)
    assert result['auto_match'] == {'linked': 0, 'proposed': 0, 'review': 1}
    assert reasons(result) == [(9, 'conflict')]
    assert mappings() == [(51, 'OGN', '016', None, 'manual', None)]


def test_a_slot_proposed_twice_is_a_conflict_for_both(catalog):
    catalog('017', 'Mirror Image')
    product(10, 'Mirror Image (Showcase)', metacard=17)
    product(11, 'Mirror Image (Promo)', metacard=18)
    result = daily_prices.match_clear_cases(DATE)
    assert result['auto_match'] == {'linked': 0, 'proposed': 2, 'review': 2}
    assert reasons(result) == [(10, 'conflict'), (11, 'conflict')]
    assert mappings() == []


def test_the_expansion_set_narrows_the_candidates(catalog):
    catalog('020', 'Sky Herald', set_id='OGN')
    catalog('020', 'Sky Herald', set_id='SFD')
    db.session.add(RbcmExpansion(rbexp_id=7000, rbexp_rbset_id='SFD'))
    db.session.commit()
    product(12, 'Sky Herald (Showcase)', metacard=20, expansion=7000)
    result = daily_prices.match_clear_cases(DATE)
    assert result['auto_match'] == {'linked': 1, 'proposed': 1, 'review': 0}
    assert mappings() == [(12, 'SFD', '020', None, 'auto', 0.7)]


def test_only_unmapped_singles_of_the_date_are_considered(catalog):
    catalog('021', 'Old Friend')
    product(13, 'Booster Box', metacard=None, kind='nonsingle')
    product(14, 'Yesterday Only', metacard=21, date='20291231')
    product(15, 'Already Linked', metacard=22)
    mapped(15, 'OGN', '021')
    result = daily_prices.match_clear_cases(DATE)
    assert result == {'auto_match': {'linked': 0, 'proposed': 0, 'review': 0},
                      'review': [], 'review_total': 0}


def test_the_review_list_holds_at_most_200_items(catalog):
    for id_product in range(1, 206):
        product(id_product, f'Unknown {id_product}', metacard=1000 + id_product)
    result = daily_prices.match_clear_cases(DATE)
    assert result['auto_match'] == {'linked': 0, 'proposed': 0, 'review': 205}
    assert result['review_total'] == 205
    assert len(result['review']) == 200
    assert [item['product_id'] for item in result['review']] == list(range(1, 201))
