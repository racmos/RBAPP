"""CM-h: missing promo cards. A promo set has the id of its base set followed by `X`
(owner rule 2026-11-23: OGN/35 Vayne, Hunter -> OGNX/35). `GET /admin/cardmarket/promo-cards`
lists the promo sets with a mapped Cardmarket expansion, or (`?set=`) the unmatched singles of
the latest load of that set's expansions with the base card each one clones;
`POST /admin/cardmarket/promo-cards` creates the missing promo cards as copies of their base
cards in one transaction (service `app/services/promo_cards.py`).

Data, latest product date D2 (D1 holds an older snapshot):

  Sets: OGN (base), OGNX (promo), PLAT (the plated cards, CM-k: listed, no product here; its
  plans are in tests/test_promo_cards_plated.py), SFDX (no SFD base), UNL + UNLX (no expansion
  mapped to UNLX).
  Expansions: 6286 -> OGN, 6322 -> OGNX, 7001 -> PLAT, 7002 -> SFDX, 7003 unmapped.
  OGN cards: 035 Vayne, Hunter (rare), 010 Little Spark (common), 050 Echo (epic),
  050a Echo (showcase), r01 Fury Rune (common rune), r01a Fury Rune (showcase rune),
  200 Heart of the Tempest (Legend, tags 'Yordle, Kennen'), 077 Already There (rare).
  OGNX cards: 077 Already There (rare).

  OGNX singles (expansion 6322) on D2:
    1001 Vayne, Hunter           mc 30  12.00 -> create OGNX/035
    1002 Little Spark            mc 31   0.50 \\ one card OGNX/010 (its N and S slots)
    1003 Little Spark (Foil)     mc 31   2.00 /
    1004 Little Spark            mc 31   3.00 -> manual: no slot left
    1005 Echo                    mc 32   1.00 -> OGNX/050a (the lower promo rank)
    1006 Echo                    mc 32   9.00 -> OGNX/050
    1007 Fury Rune               mc 33   0.30 -> OGNX/r01
    1008 Fury Rune               mc 33   4.00 -> OGNX/r01a
    1009 Kennen, Heart of the Tempest mc 34 6.00 -> OGNX/200 (legend by its tag)
    1010 Nobody Known            mc 35   0.10 -> manual: no base card
    1011 Already There           mc 36   1.50 -> exists OGNX/077
    1012 Linked One              mc 37  (linked to OGN/077: left out)
    1013 Ignored One             mc 38  (ignored: left out)
    1016 Little Spark            no metacard -> manual: no metacard
  Left out too: 1014 (D1 only), 1015 (a sealed product), 2001 (an OGN product).
"""
import pytest
from sqlalchemy import event

from app import db
from app.models import RbCard, RbSet
from app.models.audit import RbAdminAudit
from app.models.cardmarket import (RbcmExpansion, RbcmIgnored, RbcmPrice, RbcmProduct,
                                   RbcmProductCardMap)
from app.schemas.admin import AdminCardCreate
from app.services import catalog_admin, daily_prices, promo_cards
from app.services import cardmarket_matcher as matcher
from tests.test_authz_matrix import classify

URL = '/riftbound/api/v1/admin/cardmarket/promo-cards'
D1, D2 = '20301101', '20301102'

VAYNE = dict(rbcar_name='Vayne, Hunter', rbcar_rarity='Rare', rbcar_type='Unit',
             rbcar_domain='Body', rbcar_tags='Vayne', rbcar_energy=3, rbcar_power=1,
             rbcar_might=3, rbcar_ability='Deflect 1.', rbcar_artist='Some Artist',
             image='ogn_035.png', image_url='https://example.invalid/ogn_035.png')


def card(set_id, car_id, name, rarity, card_type='Unit', **extra):
    db.session.add(RbCard(rbcar_rbset_id=set_id, rbcar_id=car_id, rbcar_name=name,
                          rbcar_rarity=rarity, rbcar_type=card_type, **extra))


def product(id_product, name, metacard, low, expansion=6322, date=D2, type_='single'):
    db.session.add(RbcmProduct(rbprd_date=date, rbprd_id_product=id_product, rbprd_name=name,
                               rbprd_id_metacard=metacard, rbprd_id_expansion=expansion,
                               rbprd_type=type_, rbprd_category_name='Riftbound Single'))
    if low is not None:
        db.session.add(RbcmPrice(rbprc_date=date, rbprc_id_product=id_product, rbprc_low=low))


def build():
    for set_id, name in (('OGN', 'Origins'), ('OGNX', 'Origins Promos'), ('PLAT', 'Metal'),
                         ('SFDX', 'Spiritforged Promos'), ('UNL', 'Unleashed'),
                         ('UNLX', 'Unleashed Promos')):
        db.session.add(RbSet(rbset_id=set_id, rbset_name=name))
    db.session.flush()
    db.session.add(RbCard(rbcar_rbset_id='OGN', rbcar_id='035', **VAYNE))
    card('OGN', '010', 'Little Spark', 'Common', rbcar_domain='Fury')
    card('OGN', '050', 'Echo', 'Epic')
    card('OGN', '050a', 'Echo', 'Showcase')
    card('OGN', 'r01', 'Fury Rune', 'Common', card_type='Basic Rune')
    card('OGN', 'r01a', 'Fury Rune', 'Showcase', card_type='Basic Rune')
    card('OGN', '200', 'Heart of the Tempest', 'Epic', card_type='Legend',
         rbcar_tags='Yordle, Kennen')
    card('OGN', '077', 'Already There', 'Rare')
    card('OGNX', '077', 'Already There', 'Rare')
    for exp, set_id in ((6286, 'OGN'), (6322, 'OGNX'), (7001, 'PLAT'), (7002, 'SFDX'),
                        (7003, None)):
        db.session.add(RbcmExpansion(rbexp_id=exp, rbexp_name=f'Expansion {exp}',
                                     rbexp_rbset_id=set_id))
    product(1001, 'Vayne, Hunter', 30, 12.0)
    product(1002, 'Little Spark', 31, 0.5)
    product(1003, 'Little Spark (Foil)', 31, 2.0)
    product(1004, 'Little Spark', 31, 3.0)
    product(1005, 'Echo', 32, 1.0)
    product(1006, 'Echo', 32, 9.0)
    product(1007, 'Fury Rune', 33, 0.3)
    product(1008, 'Fury Rune', 33, 4.0)
    product(1009, 'Kennen, Heart of the Tempest', 34, 6.0)
    product(1010, 'Nobody Known', 35, 0.1)
    product(1011, 'Already There', 36, 1.5)
    product(1012, 'Linked One', 37, 1.0)
    product(1013, 'Ignored One', 38, 1.0)
    product(1014, 'Yesterday Only', 39, 1.0, date=D1)
    product(1015, 'Promo Pack', None, 5.0, type_='nonsingle')
    product(1016, 'Little Spark', None, 0.7)
    product(2001, 'Vayne, Hunter', 30, 0.02, expansion=6286)
    db.session.add(RbcmProductCardMap(rbpcm_id_product=1012, rbpcm_rbset_id='OGN',
                                      rbpcm_rbcar_id='077', rbpcm_foil=None,
                                      rbpcm_match_type='manual'))
    db.session.add(RbcmIgnored(rbig_id_product=1013, rbig_name='Ignored One'))
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
    return sorted(card.rbcar_id for card in RbCard.query.filter_by(rbcar_rbset_id=set_id))


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


def by_status(items):
    return {(item['status'], (item['proposed'] or {}).get('card_id'),
             tuple(item['product_ids'])) for item in items}


CREATE_IDS = [1001, 1002, 1003, 1005, 1006, 1007, 1008, 1009]


# ---------------------------------------------------------------------------
# Routes and authorization
# ---------------------------------------------------------------------------

class TestAuthorization:
    def test_anonymous_401_user_403_and_nothing_written(self, app, authenticated_client, data):
        anonymous = app.test_client()
        assert anonymous.get(f'{URL}?set=OGNX').status_code == 401
        assert anonymous.post(URL, json={'set_id': 'OGNX', 'product_ids': [1001]}).status_code \
            == 401
        assert authenticated_client.get(URL).status_code == 403
        assert authenticated_client.post(
            URL, json={'set_id': 'OGNX', 'product_ids': [1001]}).status_code == 403
        assert cards_of('OGNX') == ['077'] and audits() == []

    def test_both_rules_are_admin(self, app):
        rules = [rule for rule in app.url_map.iter_rules() if rule.rule == URL]
        assert {classify(rule) for rule in rules} == {'A'}
        assert {method for rule in rules for method in rule.methods} >= {'GET', 'POST'}

    def test_post_needs_the_csrf_token(self, csrf_app, admin_client, data):
        resp = admin_client.post(URL, json={'set_id': 'OGNX', 'product_ids': [1001]})
        assert resp.status_code == 400 and resp.get_json()['code'] == 'csrf_invalid'
        assert cards_of('OGNX') == ['077']


# ---------------------------------------------------------------------------
# GET without a set: the promo sets
# ---------------------------------------------------------------------------

class TestSets:
    def test_only_promo_sets_with_a_base_set_and_a_mapped_expansion_and_plat(
            self, admin_client, data):
        got = ok(admin_client.get(URL))
        assert got == {
            'date': '2030-11-02',
            'sets': [{'id': 'OGNX', 'name': 'Origins Promos', 'base': 'OGN',
                      'base_name': 'Origins', 'expansions': [6322],
                      'products_missing': 8, 'cards_to_create': 7},
                     # CM-k: PLAT (the plated cards) is listed too, without a base set
                     {'id': 'PLAT', 'name': 'Metal', 'base': None, 'base_name': None,
                      'expansions': [7001], 'products_missing': 0, 'cards_to_create': 0}],
        }

    def test_counts_drop_once_the_cards_exist(self, admin_client, data):
        ok(admin_client.post(URL, json={'set_id': 'OGNX', 'product_ids': CREATE_IDS}), 201)
        got = ok(admin_client.get(URL))
        assert got['sets'][0]['products_missing'] == 0
        assert got['sets'][0]['cards_to_create'] == 0

    def test_no_load_no_sets(self, admin_client):
        assert ok(admin_client.get(URL)) == {'date': None, 'sets': []}

    def test_bounded_statements_whatever_the_number_of_products(self, admin_client, data):
        few = len(statements(admin_client, 'get', URL))
        for n in range(30):
            card('OGN', f'{300 + n}', f'Filler {chr(65 + n % 26)}{n // 26}', 'Rare')
            product(3000 + n, f'Filler {chr(65 + n % 26)}{n // 26}', 400 + n, 1.0)
        db.session.commit()
        many = len(statements(admin_client, 'get', URL))
        assert few == many <= 9


# ---------------------------------------------------------------------------
# GET ?set=: the plan of one promo set
# ---------------------------------------------------------------------------

class TestPlan:
    def test_set_header_and_summary(self, admin_client, data):
        got = ok(admin_client.get(f'{URL}?set=OGNX'))
        assert got['set'] == {'id': 'OGNX', 'name': 'Origins Promos', 'base': 'OGN',
                              'base_name': 'Origins', 'expansions': [6322]}
        assert got['date'] == '2030-11-02'
        assert got['summary'] == {'cards_to_create': 7, 'products_to_create': 8,
                                  'exists': 1, 'manual': 3, 'products': 12}

    def test_each_product_proposes_the_base_card_it_clones(self, admin_client, data):
        items = ok(admin_client.get(f'{URL}?set=OGNX'))['items']
        assert by_status(items) == {
            ('create', '035', (1001,)),
            ('create', '010', (1002, 1003)),
            ('manual', None, (1004,)),
            ('create', '050a', (1005,)),
            ('create', '050', (1006,)),
            ('create', 'r01', (1007,)),
            ('create', 'r01a', (1008,)),
            ('create', '200', (1009,)),
            ('manual', None, (1010,)),
            ('exists', '077', (1011,)),
            ('manual', None, (1016,)),
        }

    def test_item_shape(self, admin_client, data):
        items = {item['product_id']: item
                 for item in ok(admin_client.get(f'{URL}?set=OGNX'))['items']}
        assert items[1002] == {
            'product_id': 1002, 'product_ids': [1002, 1003],
            'product_name': 'Little Spark', 'price': 0.5, 'expansion_id': 6322,
            'products': [
                {'id': 1002, 'name': 'Little Spark', 'price': 0.5, 'foil': 'N'},
                {'id': 1003, 'name': 'Little Spark (Foil)', 'price': 2.0, 'foil': 'S'}],
            'base': {'set_id': 'OGN', 'card_id': '010', 'name': 'Little Spark',
                     'rarity': 'Common', 'type': 'Unit'},
            'proposed': {'set_id': 'OGNX', 'card_id': '010'},
            'status': 'create', 'reason': 'clone'}
        assert items[1001]['products'] == [
            {'id': 1001, 'name': 'Vayne, Hunter', 'price': 12.0, 'foil': None}]
        assert (items[1004]['status'], items[1004]['reason'], items[1004]['proposed']) == (
            'manual', 'no_slot', None)
        assert items[1004]['base']['card_id'] == '010'
        assert (items[1010]['reason'], items[1010]['base']) == ('no_base_card', None)
        assert items[1016]['reason'] == 'no_metacard'
        assert (items[1011]['status'], items[1011]['reason']) == ('exists', 'in_catalog')
        assert items[1011]['proposed'] == {'set_id': 'OGNX', 'card_id': '077'}

    def test_items_are_sorted_by_name_then_price(self, admin_client, data):
        items = ok(admin_client.get(f'{URL}?set=OGNX'))['items']
        assert [item['product_id'] for item in items] == [
            1011, 1005, 1006, 1007, 1008, 1009, 1002, 1016, 1004, 1010, 1001]

    def test_the_set_id_ignores_case(self, admin_client, data):
        assert ok(admin_client.get(f'{URL}?set=ognx'))['set']['id'] == 'OGNX'

    @pytest.mark.parametrize('set_id,message', [
        ('OGN', "OGN is not a promo set: a promo set id is its base set id followed by X "
                "(OGN -> OGNX)."),
        ('SFDX', 'The base set SFD of SFDX does not exist.'),
        ('UNLX', 'No Cardmarket expansion is mapped to UNLX: map it in the Expansions tab '
                 'first.'),
        ('NOPEX', "Set 'NOPEX' does not exist."),
    ])
    def test_a_set_that_is_not_a_usable_promo_set_is_a_400(self, admin_client, data, set_id,
                                                          message):
        body = refused(admin_client.get(f'{URL}?set={set_id}'))
        assert body['code'] == 'validation_error'
        assert body['message'] == message
        assert body['details'][0]['field'] == 'set'

    def test_unknown_query_key_is_a_400(self, admin_client, data):
        assert refused(admin_client.get(f'{URL}?set=OGNX&other=1'))['code'] == 'validation_error'

    def test_writes_nothing(self, admin_client, data):
        ok(admin_client.get(f'{URL}?set=OGNX'))
        assert cards_of('OGNX') == ['077'] and audits() == []

    def test_bounded_statements_whatever_the_number_of_products(self, admin_client, data):
        few = len(statements(admin_client, 'get', f'{URL}?set=OGNX'))
        for n in range(30):
            card('OGN', f'{300 + n}', f'Filler {chr(65 + n % 26)}{n // 26}', 'Rare')
            product(3000 + n, f'Filler {chr(65 + n % 26)}{n // 26}', 400 + n, 1.0)
        db.session.commit()
        many = len(statements(admin_client, 'get', f'{URL}?set=OGNX'))
        assert few == many <= 9


# ---------------------------------------------------------------------------
# POST: create the missing promo cards
# ---------------------------------------------------------------------------

class TestCreate:
    def test_creates_the_clones_in_one_call_with_one_audit_row(self, admin_client, data):
        got = ok(admin_client.post(URL, json={'set_id': 'OGNX', 'product_ids': CREATE_IDS}),
                 201)
        assert [(c['set_id'], c['card_id'], c['product_ids']) for c in got['created']] == [
            ('OGNX', '035', [1001]), ('OGNX', '010', [1002, 1003]),
            ('OGNX', '050a', [1005]), ('OGNX', '050', [1006]), ('OGNX', 'r01', [1007]),
            ('OGNX', 'r01a', [1008]), ('OGNX', '200', [1009])]
        assert got['skipped'] == []
        assert cards_of('OGNX') == ['010', '035', '050', '050a', '077', '200', 'r01', 'r01a']
        assert audits() == [('cardmarket.promo_cards.create', 'set', 'OGNX', {
            'set_id': 'OGNX', 'base': 'OGN', 'created': 7, 'skipped': 0, 'products': 8,
            'cards': ['035', '010', '050a', '050', 'r01', 'r01a', '200']})]

    def test_a_clone_copies_every_card_field_but_the_image(self, admin_client, data):
        ok(admin_client.post(URL, json={'set_id': 'OGNX', 'product_ids': [1001, 1009]}), 201)
        db.session.expire_all()
        clone = db.session.get(RbCard, ('OGNX', '035'))
        fields = ('rbcar_name', 'rbcar_rarity', 'rbcar_type', 'rbcar_domain', 'rbcar_tags',
                  'rbcar_energy', 'rbcar_power', 'rbcar_might', 'rbcar_ability',
                  'rbcar_artist')
        assert {f: getattr(clone, f) for f in fields} == {f: VAYNE[f] for f in fields}
        assert clone.image is None and clone.image_url is None
        legend = db.session.get(RbCard, ('OGNX', '200'))
        assert (legend.rbcar_name, legend.rbcar_type, legend.rbcar_tags) == (
            'Heart of the Tempest', 'Legend', 'Yordle, Kennen')

    def test_the_answer_lists_each_created_card(self, admin_client, data):
        got = ok(admin_client.post(URL, json={'set_id': 'OGNX', 'product_ids': [1001]}), 201)
        assert got == {'created': [{'set_id': 'OGNX', 'card_id': '035', 'name': 'Vayne, Hunter',
                                    'base': {'set_id': 'OGN', 'card_id': '035'},
                                    'product_ids': [1001]}],
                       'skipped': []}

    def test_one_product_of_a_shared_card_creates_it(self, admin_client, data):
        got = ok(admin_client.post(URL, json={'set_id': 'OGNX', 'product_ids': [1003]}), 201)
        assert [c['card_id'] for c in got['created']] == ['010']
        assert cards_of('OGNX') == ['010', '077']

    def test_an_existing_promo_card_is_skipped_never_overwritten(self, admin_client, data):
        got = ok(admin_client.post(URL, json={'set_id': 'OGNX', 'product_ids': [1011]}), 200)
        assert got == {'created': [], 'skipped': [
            {'set_id': 'OGNX', 'card_id': '077', 'reason': 'in_catalog',
             'product_ids': [1011]}]}
        assert audits()[0][3]['created'] == 0 and audits()[0][3]['skipped'] == 1

    def test_a_second_call_skips_what_the_first_created(self, admin_client, data):
        ok(admin_client.post(URL, json={'set_id': 'OGNX', 'product_ids': [1001]}), 201)
        db.session.get(RbCard, ('OGNX', '035')).rbcar_ability = 'Edited by hand.'
        db.session.commit()
        got = ok(admin_client.post(URL, json={'set_id': 'OGNX', 'product_ids': [1001]}), 200)
        assert got['created'] == [] and got['skipped'][0]['card_id'] == '035'
        db.session.expire_all()
        assert db.session.get(RbCard, ('OGNX', '035')).rbcar_ability == 'Edited by hand.'

    @pytest.mark.parametrize('ids,message', [
        ([1001, 1004], 'These products get no promo card: 1004 (no card slot left: link it '
                       'by hand).'),
        ([1001, 1010, 1016], 'These products get no promo card: 1010 (no card of this name '
                             'in OGN), 1016 (Cardmarket gives it no card group).'),
        ([1001, 9999, 2001], 'These products are not unmatched products of OGNX: 2001, 9999.'),
    ])
    def test_manual_or_unknown_products_are_refused_and_nothing_is_written(
            self, admin_client, data, ids, message):
        body = refused(admin_client.post(URL, json={'set_id': 'OGNX', 'product_ids': ids}))
        assert body['code'] == 'validation_error'
        assert body['message'] == message
        assert body['details'][0]['field'] == 'product_ids'
        assert cards_of('OGNX') == ['077'] and audits() == []

    @pytest.mark.parametrize('set_id', ['OGN', 'SFDX', 'UNLX', 'NOPEX'])
    def test_a_set_that_is_not_a_usable_promo_set_is_a_400(self, admin_client, data, set_id):
        body = refused(admin_client.post(URL, json={'set_id': set_id, 'product_ids': [1001]}))
        assert body['code'] == 'validation_error'
        assert body['details'][0]['field'] == 'set_id'
        assert audits() == [] and RbCard.query.count() == 9

    @pytest.mark.parametrize('payload', [
        {}, {'set_id': 'OGNX'}, {'set_id': 'OGNX', 'product_ids': []},
        {'set_id': 'OGNX', 'product_ids': [0]}, {'set_id': 'OGNX', 'product_ids': 'x'},
        {'set_id': 'OGNX', 'product_ids': [1001], 'other': 1},
        {'set_id': 'OGNX', 'product_ids': list(range(1, 502))},
    ])
    def test_body_validation(self, admin_client, data, payload):
        assert refused(admin_client.post(URL, json=payload))['code'] == 'validation_error'
        assert cards_of('OGNX') == ['077'] and audits() == []

    def test_bounded_statements_whatever_the_number_of_cards(self, admin_client, data):
        one = len(statements(admin_client, 'post', URL,
                             json={'set_id': 'OGNX', 'product_ids': [1001]}))
        seven = len(statements(admin_client, 'post', URL,
                               json={'set_id': 'OGNX', 'product_ids': CREATE_IDS[1:]}))
        assert one == seven <= 13


# ---------------------------------------------------------------------------
# The shared card creation (catalog_admin.create_cards) refuses duplicates
# ---------------------------------------------------------------------------

class TestCreateCards:
    def test_refuses_an_existing_card_and_adds_nothing(self, data):
        payload = AdminCardCreate(set_id='OGNX', card_id='077', name='Already There')
        with pytest.raises(catalog_admin.CardExists) as raised:
            catalog_admin.create_cards([AdminCardCreate(set_id='OGNX', card_id='999', name='N'),
                                        payload])
        assert str(raised.value) == 'OGNX-077'
        db.session.rollback()
        assert cards_of('OGNX') == ['077']

    def test_refuses_an_unknown_set(self, data):
        with pytest.raises(catalog_admin.UnknownSet):
            catalog_admin.create_cards([AdminCardCreate(set_id='NOPE', card_id='1', name='N')])

    def test_refuses_the_same_card_twice(self, data):
        twice = [AdminCardCreate(set_id='OGNX', card_id='500', name='N')] * 2
        with pytest.raises(catalog_admin.CardExists):
            catalog_admin.create_cards(twice)

    def test_the_cards_admin_still_refuses_a_duplicate(self, admin_client, data):
        resp = admin_client.post('/riftbound/api/v1/admin/cards',
                                 json={'set_id': 'OGNX', 'card_id': '077', 'name': 'Again'})
        assert resp.status_code == 409 and resp.get_json()['code'] == 'already_exists'
        resp = admin_client.post('/riftbound/api/v1/admin/cards',
                                 json={'set_id': 'NOPE', 'card_id': '1', 'name': 'N'})
        assert resp.status_code == 400
        assert resp.get_json()['details'][0]['field'] == 'set_id'


# ---------------------------------------------------------------------------
# After the creation the existing Auto-match links them
# ---------------------------------------------------------------------------

def decided_reasons(decided):
    return {item['product_id']: item['reason'] for item in decided['review']}


class TestAutoMatchAfterwards:
    def test_vayne_shape_promo_product_becomes_clear_and_links_to_ognx_035(
            self, admin_client, data):
        before = daily_prices.classify_unmapped(D2)
        # without OGNX/035 the promo product falls back to OGN/035, held by the OGN product
        assert decided_reasons(before)[1001] == 'conflict'
        ok(admin_client.post(URL, json={'set_id': 'OGNX', 'product_ids': [1001]}), 201)
        after = daily_prices.classify_unmapped(D2)
        assert (1001, ('OGNX', '035', None)) in after['links']
        assert (2001, ('OGN', '035', None)) in after['links']
        daily_prices.match_clear_cases(D2)
        db.session.expire_all()
        link = db.session.get(RbcmProductCardMap, 1001)
        assert (link.rbpcm_rbset_id, link.rbpcm_rbcar_id, link.rbpcm_foil,
                link.rbpcm_match_type) == ('OGNX', '035', None, 'auto')

    def test_the_two_products_of_a_common_promo_card_pair_n_s_but_stay_ambiguous(
            self, admin_client, data):
        """Owner decision 2026-11-23 (option A): the preview puts both products under one
        card; the matcher proposes the cheaper one as N and the dearer one as S, but the daily
        rule keeps a foil-twin pair ambiguous, so the admin links them by hand."""
        ok(admin_client.post(URL, json={'set_id': 'OGNX', 'product_ids': [1002, 1003]}), 201)
        proposed = {s['id_product']: (s['rbset_id'], s['rbcar_id'], s['rbpcm_foil'])
                    for s in matcher.auto_match(dry_run=True)['samples']}
        assert proposed[1002] == ('OGNX', '010', 'N')
        assert proposed[1003] == ('OGNX', '010', 'S')
        after = daily_prices.classify_unmapped(D2)
        assert decided_reasons(after)[1002] == 'ambiguous'
        assert decided_reasons(after)[1003] == 'ambiguous'

    def test_the_preview_pairs_like_the_matcher_after_the_creation(self, admin_client, data):
        plan = ok(admin_client.get(f'{URL}?set=OGNX'))['items']
        ok(admin_client.post(URL, json={'set_id': 'OGNX', 'product_ids': CREATE_IDS}), 201)
        proposed = {s['id_product']: (s['rbset_id'], s['rbcar_id'], s['rbpcm_foil'])
                    for s in matcher.auto_match(dry_run=True)['samples']}
        for item in plan:
            if item['status'] != 'create':
                continue
            for one in item['products']:
                assert proposed[one['id']] == ('OGNX', item['proposed']['card_id'],
                                               one['foil'])


def test_service_has_no_flask_request_objects():
    import inspect
    source = inspect.getsource(promo_cards)
    assert 'from flask' not in source and 'import flask' not in source


class TestMatcherHelpers:
    """CM-h narrows two matcher helpers; called without arguments they read everything as
    before (the auto-match and the daily job)."""

    def test_latest_prices_of_some_products_equal_the_full_read(self, data):
        everything = matcher._get_latest_prices()
        assert everything[1001] == 12.0 and everything[2001] == 0.02 and 1014 in everything
        assert matcher._get_latest_prices([1001, 1014]) == {1001: 12.0, 1014: 1.0}
        assert matcher._get_latest_prices([]) == {}

    def test_card_index_of_some_cards_equals_the_full_index_for_them(self, data):
        full = matcher._build_card_index()
        some = matcher._build_card_index(RbCard.query.filter_by(rbcar_rbset_id='OGNX').all())
        assert set(some) == {'already there'}
        assert {(c.rbcar_rbset_id, c.rbcar_id) for c in full['already there']} == {
            ('OGN', '077'), ('OGNX', '077')}
        assert [c.rbcar_id for c in full['kennen heart of the tempest']] == ['200']
