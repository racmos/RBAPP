"""CM-k: missing plated cards (owner decision 2026-11-24, option A). Set PLAT holds the metal
copies of cards of other sets; Cardmarket expansion 'Plated Legends - Metal Cards' is mapped to
it and its product names do not carry the origin set. A plated card is coded
`PLAT-<origin set>-<number>` and stored as set PLAT, card id = lower-case origin set + number
(`PLAT/sfd189` for SFD/189). `GET /admin/cardmarket/promo-cards` lists PLAT with the promo
sets, `?set=PLAT` finds the one origin card of each unmatched PLAT single by name (plain
printings of every set but PLAT and the promo sets) and `POST` creates the plated cards as
copies of their origin cards (service `app/services/promo_cards.py`).

Data, latest product date D2:

  Sets: OGN, SFD, OGNX (promo of OGN), PLAT, PROK (not a promo id), LONGSET.
  Expansions: 6286 -> OGN, 6400 -> SFD, 6322 -> OGNX, 6947 -> PLAT, 7001 -> PROK.
  Cards: SFD/189 Ornn (epic, every field and an image), SFD/189a Ornn (showcase variant),
  OGN/200 Heart of the Tempest (legend, tags 'Yordle, Kennen'), OGN/010 Little Spark (common)
  and OGNX/010 Little Spark (its promo), OGN/r01 Fury Rune (rune), OGN/077 Already There and
  PLAT/ogn077 Already There, OGN/090 Twice Wanted, OGN/058 + SFD/020 Jinx (one name, two
  sets), LONGSET/1234 Long Name (longsetx1234 would be 12 characters).

  PLAT singles (expansion 6947) on D2:
    4001 Ornn, Fire Below the Mountain  mc 50  8.00 -> create sfd189
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
  SFD singles: 3001 Ornn mc 50 0.50, 3002 Ornn mc 50 20.00 (expansion 6400).
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
CREATE_IDS = [4001, 4002, 4003, 4006]


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
    card('SFD', '189a', 'Ornn, Fire Below the Mountain', 'Showcase', 'Champion Unit')
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
    product(3001, 'Ornn, Fire Below the Mountain', 50, 0.5, expansion=6400)
    product(3002, 'Ornn, Fire Below the Mountain', 50, 20.0, expansion=6400)
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
                                  'products_missing': 4, 'cards_to_create': 4}

    def test_bounded_statements_whatever_the_number_of_products(self, admin_client, data):
        few = len(statements(admin_client, 'get', URL))
        for n in range(30):
            name = f'Filler {chr(65 + n % 26)}{n // 26}'
            card('SFD', f'{300 + n}', name)
            product(5000 + n, name, 600 + n, 1.0)
        db.session.commit()
        many = len(statements(admin_client, 'get', URL))
        assert few == many <= 9
        assert ok(admin_client.get(URL))['sets'][1]['cards_to_create'] == 34


class TestPlan:
    def test_set_header_and_summary(self, admin_client, data):
        got = ok(admin_client.get(f'{URL}?set=PLAT'))
        assert got['set'] == {'id': 'PLAT', 'name': 'Plated Legends', 'base': None,
                              'base_name': None, 'expansions': [6947]}
        assert got['date'] == '2030-11-02'
        assert got['summary'] == {'cards_to_create': 4, 'products_to_create': 4,
                                  'exists': 1, 'manual': 5, 'products': 10}

    def test_each_product_proposes_its_one_origin_card(self, admin_client, data):
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
            'candidates': [],
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

    def test_variants_runes_promo_and_plated_cards_are_never_origins(self, admin_client, data):
        items = plat_items(admin_client)
        # SFD/189a (variant) and OGNX/010 (promo) leave one origin; OGN/r01 is a rune
        assert items[4001]['base']['card_id'] == '189'
        assert items[4003]['base'] == brief('OGN', '010', 'Little Spark', 'Common')
        assert items[4004]['reason'] == 'no_base_card'

    def test_a_plated_card_made_by_hand_settles_an_ambiguous_name(self, admin_client, data):
        card('PLAT', 'ogn058', 'Jinx, Loose Cannon')
        db.session.commit()
        item = plat_items(admin_client)[4009]
        assert (item['status'], item['reason'], item['proposed']) == (
            'exists', 'in_catalog', {'set_id': 'PLAT', 'card_id': 'ogn058'})

    def test_linked_ignored_sealed_and_other_set_products_are_left_out(self, admin_client,
                                                                      data):
        items = plat_items(admin_client)
        assert not {4010, 4011, 4013, 3001, 3002} & set(items)

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
            ('PLAT', 'ogn090', {'set_id': 'OGN', 'card_id': '090'}, [4006])]
        assert got['skipped'] == []
        assert cards_of('PLAT') == ['ogn010', 'ogn077', 'ogn090', 'ogn200', 'sfd189']
        assert audits() == [('cardmarket.promo_cards.create', 'set', 'PLAT', {
            'set_id': 'PLAT', 'base': None, 'created': 4, 'skipped': 0, 'products': 4,
            'cards': ['sfd189', 'ogn200', 'ogn010', 'ogn090']})]
        listed = ok(admin_client.get(URL))['sets'][1]
        assert (listed['products_missing'], listed['cards_to_create']) == (0, 0)

    def test_a_plated_card_copies_every_card_field_but_the_image(self, admin_client, data):
        ok(admin_client.post(URL, json={'set_id': 'PLAT', 'product_ids': [4001, 4002]}), 201)
        db.session.expire_all()
        plated = db.session.get(RbCard, ('PLAT', 'sfd189'))
        fields = ('rbcar_name', 'rbcar_rarity', 'rbcar_type', 'rbcar_domain', 'rbcar_tags',
                  'rbcar_energy', 'rbcar_power', 'rbcar_might', 'rbcar_ability',
                  'rbcar_artist')
        assert {f: getattr(plated, f) for f in fields} == {f: ORNN[f] for f in fields}
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
                               json={'set_id': 'PLAT', 'product_ids': CREATE_IDS[1:]}))
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
    def test_the_plat_product_becomes_clear_and_the_sfd_products_keep_their_cards(
            self, admin_client, data):
        links, review = decided(daily_prices.classify_unmapped(D2))
        # without PLAT/sfd189 the PLAT product reaches the SFD cards: not clear
        assert 4001 not in links and review[4001] in {'ambiguous', 'conflict'}
        assert links[3001] == ('SFD', '189', None) and links[3002] == ('SFD', '189a', None)

        ok(admin_client.post(URL, json={'set_id': 'PLAT', 'product_ids': [4001]}), 201)
        links, review = decided(daily_prices.classify_unmapped(D2))
        assert links[4001] == ('PLAT', 'sfd189', None)
        assert links[3001] == ('SFD', '189', None) and links[3002] == ('SFD', '189a', None)

        daily_prices.match_clear_cases(D2)
        db.session.expire_all()
        link = db.session.get(RbcmProductCardMap, 4001)
        assert (link.rbpcm_rbset_id, link.rbpcm_rbcar_id, link.rbpcm_match_type) == (
            'PLAT', 'sfd189', 'auto')
