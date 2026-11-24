"""CM-k: missing plated cards (owner decision 2026-11-24, option A). Set PLAT holds the metal
copies of cards of other sets; Cardmarket expansion 'Plated Legends - Metal Cards' is mapped to
it and its product names do not carry the origin set. A plated card is coded
`PLAT-<origin set>-<number>` and stored as set PLAT, card id = lower-case origin set + number
(`PLAT/sfd189` for SFD/189). `GET /admin/cardmarket/promo-cards` lists PLAT with the promo
sets, `?set=PLAT` finds the origin cards of each name of the unmatched PLAT singles (plain
printings of every set but PLAT and the promo sets) and `POST` creates the plated cards as
copies of their origin cards (service `app/services/promo_cards.py`).

CM-k2 (owner decision A, 2026-11-24): Cardmarket has one PLAT product per printing of a legend
(the normal one and the Showcase). When the origin printings of a name are all in one set, the
products of that name (by price ascending, unpriced last: CM-m S5) are paired with those
printings (by the rank of the plated card, `matcher.card_rank_key`): the cheapest product gets
the lowest rarity. Extra products are `no_slot`; origins in several sets stay
`ambiguous_base`. A PLAT card of the name whose id is not `<origin set><number>` (the old
format, `PLAT/189`) settles nothing and is reported in `stray_cards`.

Data, latest product date D2:

  Sets: OGN, SFD, OGNX (promo of OGN), PLAT, PROK (not a promo id), LONGSET.
  Expansions: 6286 -> OGN, 6400 -> SFD, 6322 -> OGNX, 6947 -> PLAT, 7001 -> PROK.
  Cards: SFD/189 Ornn (epic, every field and an image), SFD/244 Ornn (showcase, every field),
  SFD/244s Ornn (signed showcase variant: a letter id, never an origin),
  OGN/200 Heart of the Tempest (legend, tags 'Yordle, Kennen'), OGN/010 Little Spark (common)
  and OGNX/010 Little Spark (its promo), OGN/r01 Fury Rune (rune), OGN/077 Already There and
  PLAT/ogn077 Already There, OGN/090 Twice Wanted, OGN/058 + SFD/020 Jinx (one name, two
  sets), LONGSET/1234 Long Name (longsetx1234 would be 12 characters).

  PLAT singles (expansion 6947) on D2:
    4001 Ornn, Fire Below the Mountain  mc 50  8.00 -> create sfd189 (the cheaper: the epic)
    4014 Ornn, Fire Below the Mountain  mc 50 30.00 -> create sfd244 (the dearer: the showcase)
    4002 Kennen, Heart of the Tempest   mc 51  6.00 -> create ogn200 (legend by its tag)
    4003 Little Spark                   none   0.40 -> create ogn010 (no card group needed)
    4004 Fury Rune                      mc 53  0.30 -> manual: a rune is no origin
    4005 Already There                  mc 54  1.50 -> exists ogn077
    4006 Twice Wanted                   mc 55  1.00 -> create ogn090
    4007 Twice Wanted                   mc 55  5.00 -> manual: no slot (4006 is cheaper)
    4008 Nobody Known                   mc 56  0.10 -> manual: no card of this name
    4009 Jinx, Loose Cannon             mc 57  2.00 -> manual: several origin cards
    4012 Long Name                      mc 58  3.00 -> manual: the id would be too long
    4010 Linked One (linked), 4011 Ignored One (ignored), 4013 a sealed product: left out.
  SFD singles: 3001 Ornn mc 50 0.50, 3002 Ornn mc 50 20.00, 3003 Ornn mc 50 60.00
  (expansion 6400: SFD/189, SFD/244 and SFD/244s by rank).
"""
import pytest
from sqlalchemy import event

from app import db
from app.models import RbCard, RbSet
from app.models.audit import RbAdminAudit
from app.models.cardmarket import (RbcmExpansion, RbcmIgnored, RbcmPrice, RbcmProduct,
                                   RbcmProductCardMap)
from app.services import daily_prices
from tests.test_authz_matrix import classify

URL = '/riftbound/api/v1/admin/cardmarket/promo-cards'
D2 = '20301102'

ORNN = dict(rbcar_name='Ornn, Fire Below the Mountain', rbcar_rarity='Epic',
            rbcar_type='Champion Unit', rbcar_domain='Order', rbcar_tags='Ornn',
            rbcar_energy=7, rbcar_power=2, rbcar_might=7, rbcar_ability='Forge something.',
            rbcar_artist='Metal Artist', image='sfd_189.png',
            image_url='https://example.invalid/sfd_189.png')
ORNN_SHOWCASE = {**ORNN, 'rbcar_rarity': 'Showcase', 'rbcar_artist': 'Showcase Artist',
                 'image': 'sfd_244.png', 'image_url': 'https://example.invalid/sfd_244.png'}
CREATE_IDS = [4001, 4002, 4003, 4006, 4014]


def card(set_id, car_id, name, rarity='Rare', card_type='Unit', **extra):
    db.session.add(RbCard(rbcar_rbset_id=set_id, rbcar_id=car_id, rbcar_name=name,
                          rbcar_rarity=rarity, rbcar_type=card_type, **extra))


def product(id_product, name, metacard, low, expansion=6947, type_='single'):
    db.session.add(RbcmProduct(rbprd_date=D2, rbprd_id_product=id_product, rbprd_name=name,
                               rbprd_id_metacard=metacard, rbprd_id_expansion=expansion,
                               rbprd_type=type_, rbprd_category_name='Riftbound Single'))
    if low is not None:
        db.session.add(RbcmPrice(rbprc_date=D2, rbprc_id_product=id_product, rbprc_low=low))


def build():
    for set_id, name in (('OGN', 'Origins'), ('SFD', 'Spiritforged'),
                         ('OGNX', 'Origins Promos'), ('PLAT', 'Plated Legends'),
                         ('PROK', 'Promo Kit'), ('LONGSET', 'Long Set')):
        db.session.add(RbSet(rbset_id=set_id, rbset_name=name))
    db.session.flush()
    db.session.add(RbCard(rbcar_rbset_id='SFD', rbcar_id='189', **ORNN))
    db.session.add(RbCard(rbcar_rbset_id='SFD', rbcar_id='244', **ORNN_SHOWCASE))
    card('SFD', '244s', 'Ornn, Fire Below the Mountain', 'Showcase', 'Champion Unit')
    card('OGN', '200', 'Heart of the Tempest', 'Epic', 'Legend', rbcar_tags='Yordle, Kennen')
    card('OGN', '010', 'Little Spark', 'Common')
    card('OGNX', '010', 'Little Spark', 'Common')
    card('OGN', 'r01', 'Fury Rune', 'Common', 'Basic Rune')
    card('OGN', '077', 'Already There')
    card('PLAT', 'ogn077', 'Already There')
    card('OGN', '090', 'Twice Wanted')
    card('OGN', '058', 'Jinx, Loose Cannon')
    card('SFD', '020', 'Jinx, Loose Cannon')
    card('LONGSET', '1234', 'Long Name')
    for exp, set_id in ((6286, 'OGN'), (6400, 'SFD'), (6322, 'OGNX'), (6947, 'PLAT'),
                        (7001, 'PROK')):
        db.session.add(RbcmExpansion(rbexp_id=exp, rbexp_name=f'Expansion {exp}',
                                     rbexp_rbset_id=set_id))
    product(4001, 'Ornn, Fire Below the Mountain', 50, 8.0)
    product(4002, 'Kennen, Heart of the Tempest', 51, 6.0)
    product(4003, 'Little Spark', None, 0.4)
    product(4004, 'Fury Rune', 53, 0.3)
    product(4005, 'Already There', 54, 1.5)
    product(4006, 'Twice Wanted', 55, 1.0)
    product(4007, 'Twice Wanted', 55, 5.0)
    product(4008, 'Nobody Known', 56, 0.1)
    product(4009, 'Jinx, Loose Cannon', 57, 2.0)
    product(4010, 'Linked One', 59, 1.0)
    product(4011, 'Ignored One', 60, 1.0)
    product(4012, 'Long Name', 58, 3.0)
    product(4013, 'Plated Legends Display', None, 90.0, type_='nonsingle')
    product(4014, 'Ornn, Fire Below the Mountain', 50, 30.0)
    product(3001, 'Ornn, Fire Below the Mountain', 50, 0.5, expansion=6400)
    product(3002, 'Ornn, Fire Below the Mountain', 50, 20.0, expansion=6400)
    product(3003, 'Ornn, Fire Below the Mountain', 50, 60.0, expansion=6400)
    db.session.add(RbcmProductCardMap(rbpcm_id_product=4010, rbpcm_rbset_id='OGN',
                                      rbpcm_rbcar_id='077', rbpcm_foil=None,
                                      rbpcm_match_type='manual'))
    db.session.add(RbcmIgnored(rbig_id_product=4011, rbig_name='Ignored One'))
    db.session.commit()


@pytest.fixture
def data(app):
    build()
    return app


def ok(resp, status=200):
    assert resp.status_code == status, resp.get_json()
    body = resp.get_json()
    assert body['success'] is True
    return body['data']


def refused(resp, status=400):
    assert resp.status_code == status, resp.get_json()
    body = resp.get_json()
    assert body['success'] is False
    return body


def cards_of(set_id):
    db.session.expire_all()
    return sorted(c.rbcar_id for c in RbCard.query.filter_by(rbcar_rbset_id=set_id))


def audits():
    db.session.expire_all()
    return [(a.rbaud_action, a.rbaud_target_type, a.rbaud_target_id, a.rbaud_details)
            for a in RbAdminAudit.query.order_by(RbAdminAudit.rbaud_id).all()]


def statements(client, method, url, **kwargs):
    counted = []

    def before(conn, cursor, statement, params, context, executemany):
        counted.append(statement)

    event.listen(db.engine, 'before_cursor_execute', before)
    try:
        resp = getattr(client, method)(url, **kwargs)
        assert resp.status_code < 300, resp.get_json()
    finally:
        event.remove(db.engine, 'before_cursor_execute', before)
    return counted


def brief(set_id, card_id, name, rarity='Rare', card_type='Unit'):
    return {'set_id': set_id, 'card_id': card_id, 'name': name, 'rarity': rarity,
            'type': card_type}


def plat_items(client):
    return {item['product_id']: item for item in ok(client.get(f'{URL}?set=PLAT'))['items']}


# ---------------------------------------------------------------------------
# The list of sets and the plan of PLAT
# ---------------------------------------------------------------------------

class TestSets:
    def test_plat_is_listed_with_the_promo_sets_without_a_base(self, admin_client, data):
        got = ok(admin_client.get(URL))
        assert got['date'] == '2030-11-02'
        assert [one['id'] for one in got['sets']] == ['OGNX', 'PLAT']
        assert got['sets'][1] == {'id': 'PLAT', 'name': 'Plated Legends', 'base': None,
                                  'base_name': None, 'expansions': [6947],
                                  'products_missing': 5, 'cards_to_create': 5}

    def test_bounded_statements_whatever_the_number_of_products(self, admin_client, data):
        few = len(statements(admin_client, 'get', URL))
        for n in range(30):
            name = f'Filler {chr(65 + n % 26)}{n // 26}'
            card('SFD', f'{300 + n}', name)
            product(5000 + n, name, 600 + n, 1.0)
        db.session.commit()
        many = len(statements(admin_client, 'get', URL))
        assert few == many <= 9
        assert ok(admin_client.get(URL))['sets'][1]['cards_to_create'] == 35


class TestPlan:
    def test_set_header_and_summary(self, admin_client, data):
        got = ok(admin_client.get(f'{URL}?set=PLAT'))
        assert got['set'] == {'id': 'PLAT', 'name': 'Plated Legends', 'base': None,
                              'base_name': None, 'expansions': [6947]}
        assert got['date'] == '2030-11-02'
        assert got['summary'] == {'cards_to_create': 5, 'products_to_create': 5,
                                  'exists': 1, 'manual': 5, 'products': 11}

    def test_each_product_proposes_its_origin_card(self, admin_client, data):
        items = plat_items(admin_client)
        assert {pid: (item['status'], item['reason'], item['proposed'])
                for pid, item in items.items()} == {
            4001: ('create', 'clone', {'set_id': 'PLAT', 'card_id': 'sfd189'}),
            4002: ('create', 'clone', {'set_id': 'PLAT', 'card_id': 'ogn200'}),
            4003: ('create', 'clone', {'set_id': 'PLAT', 'card_id': 'ogn010'}),
            4004: ('manual', 'no_base_card', None),
            4005: ('exists', 'in_catalog', {'set_id': 'PLAT', 'card_id': 'ogn077'}),
            4006: ('create', 'clone', {'set_id': 'PLAT', 'card_id': 'ogn090'}),
            4007: ('manual', 'no_slot', None),
            4008: ('manual', 'no_base_card', None),
            4009: ('manual', 'ambiguous_base', None),
            4012: ('manual', 'invalid_base', None),
            4014: ('create', 'clone', {'set_id': 'PLAT', 'card_id': 'sfd244'}),
        }

    def test_item_shape(self, admin_client, data):
        items = plat_items(admin_client)
        assert items[4001] == {
            'product_id': 4001, 'product_ids': [4001],
            'product_name': 'Ornn, Fire Below the Mountain', 'price': 8.0,
            'expansion_id': 6947,
            'products': [{'id': 4001, 'name': 'Ornn, Fire Below the Mountain', 'price': 8.0,
                          'foil': None}],
            'base': brief('SFD', '189', 'Ornn, Fire Below the Mountain', 'Epic',
                          'Champion Unit'),
            'candidates': [], 'stray_cards': [],
            'proposed': {'set_id': 'PLAT', 'card_id': 'sfd189'},
            'status': 'create', 'reason': 'clone'}
        # a common origin: one product, its first slot as the matcher pairs it
        assert items[4003]['products'][0]['foil'] == 'N'
        assert items[4002]['base'] == brief('OGN', '200', 'Heart of the Tempest', 'Epic',
                                            'Legend')
        assert items[4005]['base'] == brief('OGN', '077', 'Already There')
        assert items[4007]['base'] == brief('OGN', '090', 'Twice Wanted')
        assert (items[4008]['base'], items[4008]['candidates']) == (None, [])
        assert items[4012]['base'] == brief('LONGSET', '1234', 'Long Name')

    def test_a_name_in_several_sets_lists_the_origin_candidates(self, admin_client, data):
        item = plat_items(admin_client)[4009]
        assert item['base'] is None and item['proposed'] is None
        assert item['candidates'] == [brief('OGN', '058', 'Jinx, Loose Cannon'),
                                      brief('SFD', '020', 'Jinx, Loose Cannon')]
        assert item['stray_cards'] == []

    def test_variants_runes_promo_and_plated_cards_are_never_origins(self, admin_client, data):
        items = plat_items(admin_client)
        # SFD/244s (a letter id) and OGNX/010 (promo) are no origins; OGN/r01 is a rune
        assert items[4001]['base']['card_id'] == '189'
        assert items[4014]['base']['card_id'] == '244'
        assert not [item for item in items.values()
                    if (item['proposed'] or {}).get('card_id') == 'sfd244s']
        assert items[4003]['base'] == brief('OGN', '010', 'Little Spark', 'Common')
        assert items[4004]['reason'] == 'no_base_card'

    def test_a_plated_card_made_by_hand_settles_an_ambiguous_name(self, admin_client, data):
        card('PLAT', 'ogn058', 'Jinx, Loose Cannon')
        db.session.commit()
        item = plat_items(admin_client)[4009]
        assert (item['status'], item['reason'], item['proposed']) == (
            'exists', 'in_catalog', {'set_id': 'PLAT', 'card_id': 'ogn058'})

    # -- CM-k2: one plated card per origin printing (owner decision A, 2026-11-24) --------

    def test_two_products_pair_with_the_two_printings_cheap_to_the_lower_rarity(
            self, admin_client, data):
        items = plat_items(admin_client)
        cheap, dear = items[4001], items[4014]
        assert (cheap['base'], cheap['proposed'], cheap['products'][0]['foil']) == (
            brief('SFD', '189', 'Ornn, Fire Below the Mountain', 'Epic', 'Champion Unit'),
            {'set_id': 'PLAT', 'card_id': 'sfd189'}, None)
        assert (dear['base'], dear['proposed'], dear['product_ids']) == (
            brief('SFD', '244', 'Ornn, Fire Below the Mountain', 'Showcase',
                  'Champion Unit'),
            {'set_id': 'PLAT', 'card_id': 'sfd244'}, [4014])
        assert (dear['status'], dear['reason'], dear['candidates'], dear['stray_cards']) == (
            'create', 'clone', [], [])

    def test_the_rarity_decides_not_the_card_number(self, admin_client, data):
        # Ahri: the Showcase has the LOWER number, the cheaper product still gets the Rare
        card('OGN', '303', 'Ahri, Nine-Tailed Fox', 'Rare', 'Legend')
        card('OGN', '255', 'Ahri, Nine-Tailed Fox', 'Showcase', 'Legend')
        product(4020, 'Ahri, Nine-Tailed Fox', 70, 2.0)
        product(4021, 'Ahri, Nine-Tailed Fox', 70, 9.0)
        db.session.commit()
        items = plat_items(admin_client)
        assert items[4020]['proposed'] == {'set_id': 'PLAT', 'card_id': 'ogn303'}
        assert items[4021]['proposed'] == {'set_id': 'PLAT', 'card_id': 'ogn255'}

    def test_an_unpriced_product_gets_the_highest_rarity(self, admin_client, data):
        """CM-m S5 (owner decision 2026-11-24): before, an unpriced product counted as 0 and
        took the Rare; now it sorts after every priced product and takes the Showcase."""
        card('OGN', '255', 'Ahri, Nine-Tailed Fox', 'Rare', 'Legend')
        card('OGN', '303', 'Ahri, Nine-Tailed Fox', 'Showcase', 'Legend')
        card('OGN', '303s', 'Ahri, Nine-Tailed Fox', 'Showcase', 'Legend')
        product(4020, 'Ahri, Nine-Tailed Fox', 70, 5.0)
        product(4021, 'Ahri, Nine-Tailed Fox', 70, None)
        db.session.commit()
        items = plat_items(admin_client)
        assert (items[4021]['price'], items[4021]['proposed'], items[4021]['status']) == (
            None, {'set_id': 'PLAT', 'card_id': 'ogn303'}, 'create')
        assert (items[4020]['proposed'], items[4020]['status']) == (
            {'set_id': 'PLAT', 'card_id': 'ogn255'}, 'create')

    def test_more_products_than_printings_leave_the_dearest_by_hand(self, admin_client,
                                                                   data):
        product(4015, 'Ornn, Fire Below the Mountain', 50, 50.0)
        db.session.commit()
        items = plat_items(admin_client)
        assert [items[pid]['proposed']['card_id'] for pid in (4001, 4014)] == [
            'sfd189', 'sfd244']
        extra = items[4015]
        assert (extra['status'], extra['reason'], extra['proposed'], extra['base']) == (
            'manual', 'no_slot', None,
            brief('SFD', '244', 'Ornn, Fire Below the Mountain', 'Showcase',
                  'Champion Unit'))
        assert (extra['candidates'], extra['stray_cards']) == ([], [])

    def test_more_printings_than_products_leave_the_higher_printings_unused(
            self, admin_client, data):
        card('OGN', '255', 'Ahri, Nine-Tailed Fox', 'Rare', 'Legend')
        card('OGN', '303', 'Ahri, Nine-Tailed Fox', 'Showcase', 'Legend')
        product(4021, 'Ahri, Nine-Tailed Fox', 70, 40.0)
        db.session.commit()
        items = plat_items(admin_client)
        assert (items[4021]['status'], items[4021]['proposed']) == (
            'create', {'set_id': 'PLAT', 'card_id': 'ogn255'})
        assert ok(admin_client.get(f'{URL}?set=PLAT'))['summary']['cards_to_create'] == 6

    def test_one_printing_and_two_products_leave_the_dearer_by_hand(self, admin_client,
                                                                    data):
        items = plat_items(admin_client)
        assert (items[4006]['status'], items[4006]['proposed']) == (
            'create', {'set_id': 'PLAT', 'card_id': 'ogn090'})
        assert (items[4007]['status'], items[4007]['reason'], items[4007]['base']) == (
            'manual', 'no_slot', brief('OGN', '090', 'Twice Wanted'))

    def test_a_printing_whose_plated_card_exists_is_in_the_catalog(self, admin_client, data):
        card('PLAT', 'sfd189', 'Ornn, Fire Below the Mountain', 'Epic', 'Champion Unit')
        db.session.commit()
        items = plat_items(admin_client)
        assert (items[4001]['status'], items[4001]['proposed']) == (
            'exists', {'set_id': 'PLAT', 'card_id': 'sfd189'})
        assert (items[4014]['status'], items[4014]['proposed']) == (
            'create', {'set_id': 'PLAT', 'card_id': 'sfd244'})

    def test_a_linked_plated_card_leaves_the_other_product_its_own_printing(
            self, admin_client, data):
        # the cheap product is linked to PLAT/sfd189 already: the dear one is the showcase
        card('PLAT', 'sfd189', 'Ornn, Fire Below the Mountain', 'Epic', 'Champion Unit')
        db.session.add(RbcmProductCardMap(rbpcm_id_product=4001, rbpcm_rbset_id='PLAT',
                                          rbpcm_rbcar_id='sfd189', rbpcm_foil=None,
                                          rbpcm_match_type='manual'))
        db.session.commit()
        items = plat_items(admin_client)
        assert 4001 not in items
        assert (items[4014]['status'], items[4014]['proposed']) == (
            'create', {'set_id': 'PLAT', 'card_id': 'sfd244'})

    def test_a_plated_card_with_the_old_id_is_a_stray_and_hides_nothing(self, admin_client,
                                                                       data):
        card('PLAT', '189', 'Ornn, Fire Below the Mountain', 'Epic', 'Champion Unit')
        # a plated variant made by hand (`PLAT-SFD-189a`) has the new form: no stray
        card('PLAT', 'sfd189a', 'Ornn, Fire Below the Mountain', 'Showcase', 'Champion Unit')
        card('PLAT', '58', 'Jinx, Loose Cannon')
        db.session.commit()
        items = plat_items(admin_client)
        for pid, proposed in ((4001, 'sfd189'), (4014, 'sfd244')):
            assert (items[pid]['status'], items[pid]['proposed'], items[pid]['stray_cards']) == (
                'create', {'set_id': 'PLAT', 'card_id': proposed}, ['189'])
        # an ambiguous name stays ambiguous: the stray card settles nothing
        assert (items[4009]['status'], items[4009]['reason'], items[4009]['stray_cards']) == (
            'manual', 'ambiguous_base', ['58'])
        assert len(items[4009]['candidates']) == 2
        assert {pid: item['stray_cards'] for pid, item in items.items()
                if pid not in {4001, 4014, 4009}} == {
            pid: [] for pid in items if pid not in {4001, 4014, 4009}}
        assert ok(admin_client.get(f'{URL}?set=PLAT'))['summary']['cards_to_create'] == 5

    def test_linked_ignored_sealed_and_other_set_products_are_left_out(self, admin_client,
                                                                      data):
        items = plat_items(admin_client)
        assert not {4010, 4011, 4013, 3001, 3002, 3003} & set(items)

    def test_the_set_id_ignores_case_and_writes_nothing(self, admin_client, data):
        assert ok(admin_client.get(f'{URL}?set=plat'))['set']['id'] == 'PLAT'
        assert cards_of('PLAT') == ['ogn077'] and audits() == []

    @pytest.mark.parametrize('set_id,message', [
        ('OGN', "OGN is not a promo set: a promo set id is its base set id followed by X "
                "(OGN -> OGNX)."),
        ('PROK', "PROK is not a promo set: a promo set id is its base set id followed by X "
                 "(OGN -> OGNX)."),
    ])
    def test_other_sets_that_are_no_promo_set_are_still_a_400(self, admin_client, data,
                                                              set_id, message):
        body = refused(admin_client.get(f'{URL}?set={set_id}'))
        assert (body['code'], body['message']) == ('validation_error', message)
        assert body['details'][0]['field'] == 'set'
        body = refused(admin_client.post(URL, json={'set_id': set_id,
                                                     'product_ids': [4001]}))
        assert body['details'][0]['field'] == 'set_id'
        assert cards_of('PLAT') == ['ogn077'] and audits() == []

    def test_plat_without_a_mapped_expansion_is_a_400(self, admin_client, data):
        db.session.get(RbcmExpansion, 6947).rbexp_rbset_id = None
        db.session.commit()
        body = refused(admin_client.get(f'{URL}?set=PLAT'))
        assert body['message'] == ('No Cardmarket expansion is mapped to PLAT: map it in the '
                                   'Expansions tab first.')
        assert [one['id'] for one in ok(admin_client.get(URL))['sets']] == ['OGNX']

    def test_bounded_statements_whatever_the_number_of_products(self, admin_client, data):
        few = len(statements(admin_client, 'get', f'{URL}?set=PLAT'))
        for n in range(30):
            name = f'Filler {chr(65 + n % 26)}{n // 26}'
            card('SFD', f'{300 + n}', name)
            product(5000 + n, name, 600 + n, 1.0)
        db.session.commit()
        many = len(statements(admin_client, 'get', f'{URL}?set=PLAT'))
        assert few == many <= 9


# ---------------------------------------------------------------------------
# POST: create the missing plated cards
# ---------------------------------------------------------------------------

class TestCreate:
    def test_creates_the_plated_cards_with_one_audit_row(self, admin_client, data):
        got = ok(admin_client.post(URL, json={'set_id': 'PLAT', 'product_ids': CREATE_IDS}),
                 201)
        assert [(c['set_id'], c['card_id'], c['base'], c['product_ids'])
                for c in got['created']] == [
            ('PLAT', 'sfd189', {'set_id': 'SFD', 'card_id': '189'}, [4001]),
            ('PLAT', 'ogn200', {'set_id': 'OGN', 'card_id': '200'}, [4002]),
            ('PLAT', 'ogn010', {'set_id': 'OGN', 'card_id': '010'}, [4003]),
            ('PLAT', 'ogn090', {'set_id': 'OGN', 'card_id': '090'}, [4006]),
            ('PLAT', 'sfd244', {'set_id': 'SFD', 'card_id': '244'}, [4014])]
        assert got['skipped'] == []
        assert cards_of('PLAT') == ['ogn010', 'ogn077', 'ogn090', 'ogn200', 'sfd189',
                                    'sfd244']
        assert audits() == [('cardmarket.promo_cards.create', 'set', 'PLAT', {
            'set_id': 'PLAT', 'base': None, 'created': 5, 'skipped': 0, 'products': 5,
            'cards': ['sfd189', 'ogn200', 'ogn010', 'ogn090', 'sfd244']})]
        listed = ok(admin_client.get(URL))['sets'][1]
        assert (listed['products_missing'], listed['cards_to_create']) == (0, 0)

    def test_a_plated_card_copies_every_card_field_but_the_image(self, admin_client, data):
        ok(admin_client.post(URL, json={'set_id': 'PLAT', 'product_ids': [4001, 4002, 4014]}),
           201)
        db.session.expire_all()
        fields = ('rbcar_name', 'rbcar_rarity', 'rbcar_type', 'rbcar_domain', 'rbcar_tags',
                  'rbcar_energy', 'rbcar_power', 'rbcar_might', 'rbcar_ability',
                  'rbcar_artist')
        for card_id, origin in (('sfd189', ORNN), ('sfd244', ORNN_SHOWCASE)):
            plated = db.session.get(RbCard, ('PLAT', card_id))
            assert {f: getattr(plated, f) for f in fields} == {f: origin[f] for f in fields}
            assert plated.image is None and plated.image_url is None
        legend = db.session.get(RbCard, ('PLAT', 'ogn200'))
        assert (legend.rbcar_type, legend.rbcar_tags) == ('Legend', 'Yordle, Kennen')

    def test_an_existing_plated_card_is_skipped_never_overwritten(self, admin_client, data):
        got = ok(admin_client.post(URL, json={'set_id': 'PLAT', 'product_ids': [4005]}), 200)
        assert got == {'created': [], 'skipped': [
            {'set_id': 'PLAT', 'card_id': 'ogn077', 'reason': 'in_catalog',
             'product_ids': [4005]}]}
        assert audits()[0][3]['base'] is None and audits()[0][3]['skipped'] == 1

    @pytest.mark.parametrize('ids,message', [
        ([4001, 4007], 'These products get no plated card: 4007 (no card slot left: link it '
                       'by hand).'),
        ([4001, 4008], 'These products get no plated card: 4008 (no card of this name in '
                       'any set).'),
        ([4009], 'These products get no plated card: 4009 (several cards of this name: '
                 'OGN-058, SFD-020).'),
        ([4012], 'These products get no plated card: 4012 (its origin card cannot be '
                 'copied).'),
        ([4001, 4010, 3001], 'These products are not unmatched products of PLAT: 3001, '
                             '4010.'),
    ])
    def test_manual_or_unknown_products_are_refused_and_nothing_is_written(
            self, admin_client, data, ids, message):
        body = refused(admin_client.post(URL, json={'set_id': 'PLAT', 'product_ids': ids}))
        assert body['code'] == 'validation_error'
        assert body['message'] == message
        assert body['details'][0]['field'] == 'product_ids'
        assert cards_of('PLAT') == ['ogn077'] and audits() == []

    def test_bounded_statements_whatever_the_number_of_cards(self, admin_client, data):
        one = len(statements(admin_client, 'post', URL,
                             json={'set_id': 'PLAT', 'product_ids': [4001]}))
        three = len(statements(admin_client, 'post', URL,
                               json={'set_id': 'PLAT', 'product_ids': CREATE_IDS[1:4]}))
        assert one == three <= 13


class TestRoutes:
    def test_authorization_is_unchanged(self, app, authenticated_client, data):
        rules = [rule for rule in app.url_map.iter_rules() if rule.rule == URL]
        assert {classify(rule) for rule in rules} == {'A'}
        assert authenticated_client.get(f'{URL}?set=PLAT').status_code == 403
        assert authenticated_client.post(
            URL, json={'set_id': 'PLAT', 'product_ids': [4001]}).status_code == 403
        assert app.test_client().get(f'{URL}?set=PLAT').status_code == 401
        assert cards_of('PLAT') == ['ogn077'] and audits() == []


# ---------------------------------------------------------------------------
# After the creation the existing Auto-match links the PLAT product
# ---------------------------------------------------------------------------

def decided(result):
    return dict(result['links']), {item['product_id']: item['reason']
                                   for item in result['review']}


class TestAutoMatchAfterwards:
    def test_the_real_radiance_pair_with_one_unpriced_product_is_clear(self, admin_client,
                                                                       data):
        """CM-m S5 on the real shape (2026-11-24): PLAT products 922477 (1080 EUR) and 922511
        (no price) of Ziggs; origins RAD-141 Rare and RAD-169 Showcase. The priced one is the
        Rare, the unpriced one the Showcase, and after the creation both are clear cases."""
        db.session.add(RbSet(rbset_id='RAD', rbset_name='Radiance'))
        db.session.flush()
        card('RAD', '141', 'Hexplosives Expert', 'Rare', 'Legend', rbcar_tags='Ziggs')
        card('RAD', '169', 'Hexplosives Expert', 'Showcase', 'Legend', rbcar_tags='Ziggs')
        product(922477, 'Ziggs, Hexplosives Expert', 80, 1080.0)
        product(922511, 'Ziggs, Hexplosives Expert', 80, None)
        db.session.commit()
        items = plat_items(admin_client)
        assert items[922477]['proposed'] == {'set_id': 'PLAT', 'card_id': 'rad141'}
        assert items[922511]['proposed'] == {'set_id': 'PLAT', 'card_id': 'rad169'}
        ok(admin_client.post(URL, json={'set_id': 'PLAT', 'product_ids': [922477, 922511]}),
           201)
        links, review = decided(daily_prices.classify_unmapped(D2))
        assert (links[922477], links[922511]) == (('PLAT', 'rad141', None),
                                                  ('PLAT', 'rad169', None))
        assert 922477 not in review and 922511 not in review

    def test_both_plat_products_become_clear_and_the_sfd_products_keep_their_cards(
            self, admin_client, data):
        sfd = {3001: ('SFD', '189', None), 3002: ('SFD', '244', None),
               3003: ('SFD', '244s', None)}
        links, review = decided(daily_prices.classify_unmapped(D2))
        # without the PLAT cards the PLAT products reach the SFD cards: not clear
        for pid in (4001, 4014):
            assert pid not in links and review[pid] in {'ambiguous', 'conflict'}
        assert {pid: links[pid] for pid in sfd} == sfd

        ok(admin_client.post(URL, json={'set_id': 'PLAT', 'product_ids': [4001, 4014]}), 201)
        links, review = decided(daily_prices.classify_unmapped(D2))
        assert (links[4001], links[4014]) == (('PLAT', 'sfd189', None),
                                              ('PLAT', 'sfd244', None))
        assert {pid: links[pid] for pid in sfd} == sfd

        daily_prices.match_clear_cases(D2)
        db.session.expire_all()
        for pid, card_id in ((4001, 'sfd189'), (4014, 'sfd244')):
            link = db.session.get(RbcmProductCardMap, pid)
            assert (link.rbpcm_rbset_id, link.rbpcm_rbcar_id, link.rbpcm_match_type) == (
                'PLAT', card_id, 'auto')
