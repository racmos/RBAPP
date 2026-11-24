"""CM-m: legends with more Cardmarket printings than catalog cards (owner feedback 2026-11-24).

Cardmarket lists three printings of each Radiance legend (Rare, Showcase and the signed card)
while Riot's gallery, so the catalog, has two (`RAD-141`, `RAD-169`): two unlinked products
for one free card is ambiguous by design. Owner answer 2026-11-24: the third printing is the
SIGNED card, id `<id>s`.

- S1: an `ambiguous` review item whose card group has more products than free cards of its own
  set says so: `reason_detail: more_printings_than_cards`, `detail {products, cards, set_id}`.
- S2: `GET /admin/cardmarket/missing-printings` lists, per set, those groups with the products
  by price, the cards they take and the proposed signed card (copy of the highest-rank plain
  printing, rarity Showcase), or `manual` with the reason.
- S3: `POST /admin/cardmarket/missing-printings {items: [{set_id, card_id}]}` creates them in
  one transaction with one audit row; an existing one is skipped; anything else is a 400.
- S6: after creating `RAD-169s`, Auto-match decides 917370 -> RAD-169 and 917487 -> RAD-169s as
  clear cases and 917343 keeps RAD-141.

Data, latest product date D2 (D1 holds an older snapshot):

  Sets: RAD, OGN, OGNX (promo of OGN), PLAT.
  Expansions: 6659 -> RAD, 6286 -> OGN, 6322 -> OGNX, 6947 -> PLAT, 7000 unmapped.
  RAD singles (expansion 6659):
    Ziggs (mc 100): 917343 0.02 (linked RAD-141), 917370 45.00, 917487 450.00
        cards RAD-141 Rare, RAD-169 Showcase (legends, tag Ziggs) -> create RAD-169s
    Bright Twin (mc 101): 5001 1, 5002 2, 5003 3, 5004 4; cards RAD-151 Rare, RAD-174 Showcase
        -> manual several_extra_products (two extra products)
    Even Pair (mc 102): 5010 1, 5011 2; cards RAD-160 Rare, RAD-161 Showcase -> not listed
    Long Number (mc 103): 5020 1, 5021 2; card RAD-1234567890 Showcase -> manual invalid_base
  OGN singles (expansion 6286):
    Ahri, Alluring (mc 200): 6001 1, 6002 2, 6003 3; cards OGN-066, OGN-066a (rare)
        -> manual letter_variant
    Little Spark (mc 201): 6010 0.1, 6011 0.5, 6012 3; card OGN-010 common -> manual foil_pair
    Taken Name (mc 202): 6020 1, 6021 2; card OGN-120 Epic, OGN-120s is 'Other Card'
        -> manual id_taken
    Fury Rune (mc 203): 6030 1, 6031 2; card OGN-r01 rune -> manual no_plain_printing
    Nobody (mc 204): 6040 1, 6041 2; no card -> not listed
    Ignored Twin (mc 205): 6050 1, 6051 2 (ignored); card OGN-130 Rare -> not listed
    6060 'Loose One' (no metacard) -> not listed
  OGNX singles: Vayne, Hunter (mc 300): 7001 1, 7002 2; card OGNX-035 -> not listed (promo set)
  PLAT singles: Ziggs (mc 400): 8001 1, 8002 2, 8003 3; card PLAT-rad141 -> not listed (PLAT)
"""
import pytest
from sqlalchemy import event

from app import db
from app.models import RbCard, RbSet
from app.models.audit import RbAdminAudit
from app.models.cardmarket import (RbcmExpansion, RbcmIgnored, RbcmPrice, RbcmProduct,
                                   RbcmProductCardMap)
from app.services import daily_prices, missing_printings
from tests.test_authz_matrix import classify

URL = '/riftbound/api/v1/admin/cardmarket/missing-printings'
REVIEW = '/riftbound/api/v1/admin/cardmarket/review'
D1, D2 = '20301101', '20301102'

ZIGGS_RARE = dict(rbcar_name='Hexplosives Expert', rbcar_rarity='Rare', rbcar_type='Legend',
                  rbcar_domain='Mind', rbcar_tags='Ziggs', rbcar_energy=None, rbcar_power=None,
                  rbcar_might=None, rbcar_ability='Legend ability.', rbcar_artist='Rare Artist',
                  image='rad_141.png', image_url='https://example.invalid/rad_141.png')
ZIGGS_SHOWCASE = {**ZIGGS_RARE, 'rbcar_rarity': 'Showcase', 'rbcar_artist': 'Showcase Artist',
                  'image': 'rad_169.png', 'image_url': 'https://example.invalid/rad_169.png'}
ZIGGS = 'Ziggs, Hexplosives Expert'


def card(set_id, car_id, name, rarity='Rare', card_type='Unit', **extra):
    db.session.add(RbCard(rbcar_rbset_id=set_id, rbcar_id=car_id, rbcar_name=name,
                          rbcar_rarity=rarity, rbcar_type=card_type, **extra))


def product(id_product, name, metacard, low, expansion=6659, date=D2):
    db.session.add(RbcmProduct(rbprd_date=date, rbprd_id_product=id_product, rbprd_name=name,
                               rbprd_id_metacard=metacard, rbprd_id_expansion=expansion,
                               rbprd_type='single', rbprd_category_name='Riftbound Single'))
    if low is not None:
        db.session.add(RbcmPrice(rbprc_date=date, rbprc_id_product=id_product, rbprc_low=low))


def linked(id_product, set_id, card_id, foil=None):
    db.session.add(RbcmProductCardMap(rbpcm_id_product=id_product, rbpcm_rbset_id=set_id,
                                      rbpcm_rbcar_id=card_id, rbpcm_foil=foil,
                                      rbpcm_match_type='manual'))


def build():
    for set_id, name in (('RAD', 'Radiance'), ('OGN', 'Origins'), ('OGNX', 'Origins Promos'),
                         ('PLAT', 'Plated Legends')):
        db.session.add(RbSet(rbset_id=set_id, rbset_name=name))
    db.session.flush()
    for exp, set_id in ((6659, 'RAD'), (6286, 'OGN'), (6322, 'OGNX'), (6947, 'PLAT'),
                        (7000, None)):
        db.session.add(RbcmExpansion(rbexp_id=exp, rbexp_name=f'Expansion {exp}',
                                     rbexp_rbset_id=set_id))
    db.session.add(RbCard(rbcar_rbset_id='RAD', rbcar_id='141', **ZIGGS_RARE))
    db.session.add(RbCard(rbcar_rbset_id='RAD', rbcar_id='169', **ZIGGS_SHOWCASE))
    card('RAD', '151', 'Bright Twin')
    card('RAD', '174', 'Bright Twin', 'Showcase')
    card('RAD', '160', 'Even Pair')
    card('RAD', '161', 'Even Pair', 'Showcase')
    card('RAD', '1234567890', 'Long Number', 'Showcase')
    card('OGN', '066', 'Ahri, Alluring')
    card('OGN', '066a', 'Ahri, Alluring')
    card('OGN', '010', 'Little Spark', 'Common')
    card('OGN', '120', 'Taken Name', 'Epic')
    card('OGN', '120s', 'Other Card', 'Epic')
    card('OGN', 'r01', 'Fury Rune', 'Common', 'Basic Rune')
    card('OGN', '130', 'Ignored Twin')
    card('OGNX', '035', 'Vayne, Hunter')
    card('PLAT', 'rad141', 'Hexplosives Expert', 'Rare', 'Legend', rbcar_tags='Ziggs')

    product(917343, ZIGGS, 100, 0.02)
    product(917370, ZIGGS, 100, 45.0)
    product(917487, ZIGGS, 100, 450.0)
    product(917370, ZIGGS, 100, 40.0, date=D1)
    for pid, price in ((5001, 1.0), (5002, 2.0), (5003, 3.0), (5004, 4.0)):
        product(pid, 'Bright Twin', 101, price)
    product(5010, 'Even Pair', 102, 1.0)
    product(5011, 'Even Pair', 102, 2.0)
    product(5020, 'Long Number', 103, 1.0)
    product(5021, 'Long Number', 103, 2.0)
    for pid, name, mc, price in (
            (6001, 'Ahri, Alluring', 200, 1.0), (6002, 'Ahri, Alluring', 200, 2.0),
            (6003, 'Ahri, Alluring', 200, 3.0), (6010, 'Little Spark', 201, 0.1),
            (6011, 'Little Spark (Foil)', 201, 0.5), (6012, 'Little Spark', 201, 3.0),
            (6020, 'Taken Name', 202, 1.0), (6021, 'Taken Name', 202, 2.0),
            (6030, 'Fury Rune', 203, 1.0), (6031, 'Fury Rune', 203, 2.0),
            (6040, 'Nobody', 204, 1.0), (6041, 'Nobody', 204, 2.0),
            (6050, 'Ignored Twin', 205, 1.0), (6051, 'Ignored Twin', 205, 2.0),
            (6060, 'Loose One', None, 1.0)):
        product(pid, name, mc, price, expansion=6286)
    product(7001, 'Vayne, Hunter', 300, 1.0, expansion=6322)
    product(7002, 'Vayne, Hunter', 300, 2.0, expansion=6322)
    for pid, price in ((8001, 1.0), (8002, 2.0), (8003, 3.0)):
        product(pid, ZIGGS, 400, price, expansion=6947)
    linked(917343, 'RAD', '141')
    db.session.add(RbcmIgnored(rbig_id_product=6051, rbig_name='Ignored Twin'))
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


def groups(got):
    return {(one['set_id'], group['metacard']): group
            for one in got['sets'] for group in one['groups']}


def decided():
    result = daily_prices.classify_unmapped(D2)
    return dict(result['links']), {item['product_id']: item for item in result['review']}


CREATE = {'items': [{'set_id': 'RAD', 'card_id': '169s'}]}


# ---------------------------------------------------------------------------
# Routes and authorization
# ---------------------------------------------------------------------------

class TestAuthorization:
    def test_anonymous_401_user_403_and_nothing_written(self, app, authenticated_client, data):
        anonymous = app.test_client()
        assert anonymous.get(URL).status_code == 401
        assert anonymous.post(URL, json=CREATE).status_code == 401
        assert authenticated_client.get(URL).status_code == 403
        assert authenticated_client.post(URL, json=CREATE).status_code == 403
        assert cards_of('RAD') == ['1234567890', '141', '151', '160', '161', '169', '174']
        assert audits() == []

    def test_both_rules_are_admin(self, app):
        rules = [rule for rule in app.url_map.iter_rules() if rule.rule == URL]
        assert {classify(rule) for rule in rules} == {'A'}
        assert {method for rule in rules for method in rule.methods} >= {'GET', 'POST'}

    def test_post_needs_the_csrf_token(self, csrf_app, admin_client, data):
        resp = admin_client.post(URL, json=CREATE)
        assert resp.status_code == 400 and resp.get_json()['code'] == 'csrf_invalid'
        assert '169s' not in cards_of('RAD')


# ---------------------------------------------------------------------------
# S2: the list
# ---------------------------------------------------------------------------

class TestList:
    def test_the_radiance_legend_proposes_its_signed_printing(self, admin_client, data):
        got = ok(admin_client.get(URL))
        assert got['date'] == '2030-11-02'
        assert groups(got)[('RAD', 100)] == {
            'metacard': 100, 'name': ZIGGS,
            'products': [
                {'id': 917343, 'name': ZIGGS, 'price': 0.02,
                 'linked': {'set_id': 'RAD', 'card_id': '141', 'foil': None}},
                {'id': 917370, 'name': ZIGGS, 'price': 45.0, 'linked': None},
                {'id': 917487, 'name': ZIGGS, 'price': 450.0, 'linked': None}],
            'cards': [
                {'set_id': 'RAD', 'card_id': '141', 'name': 'Hexplosives Expert',
                 'rarity': 'Rare'},
                {'set_id': 'RAD', 'card_id': '169', 'name': 'Hexplosives Expert',
                 'rarity': 'Showcase'}],
            'base': {'set_id': 'RAD', 'card_id': '169', 'name': 'Hexplosives Expert',
                     'rarity': 'Showcase'},
            'proposed': {'set_id': 'RAD', 'card_id': '169s', 'rarity': 'Showcase'},
            'status': 'create', 'reason': 'clone'}

    def test_every_listed_group_and_why(self, admin_client, data):
        got = ok(admin_client.get(URL))
        assert {key: (group['status'], group['reason'],
                      (group['proposed'] or {}).get('card_id'))
                for key, group in groups(got).items()} == {
            ('RAD', 100): ('create', 'clone', '169s'),
            ('RAD', 101): ('manual', 'several_extra_products', None),
            ('RAD', 103): ('manual', 'invalid_base', None),
            ('OGN', 200): ('manual', 'letter_variant', None),
            ('OGN', 201): ('manual', 'foil_pair', None),
            ('OGN', 202): ('manual', 'id_taken', None),
            ('OGN', 203): ('manual', 'no_plain_printing', None),
        }

    def test_sets_by_id_groups_by_name_and_the_summary(self, admin_client, data):
        got = ok(admin_client.get(URL))
        assert [(one['set_id'], one['set_name'], [g['name'] for g in one['groups']])
                for one in got['sets']] == [
            ('OGN', 'Origins', ['Ahri, Alluring', 'Fury Rune', 'Little Spark', 'Taken Name']),
            ('RAD', 'Radiance', ['Bright Twin', 'Long Number', ZIGGS])]
        assert got['summary'] == {'groups': 7, 'cards_to_create': 1, 'exists': 0, 'manual': 6}

    def test_products_by_price_with_unpriced_last(self, admin_client, data):
        product(5005, 'Bright Twin', 101, None)
        db.session.commit()
        group = groups(ok(admin_client.get(URL)))[('RAD', 101)]
        assert [one['id'] for one in group['products']] == [5001, 5002, 5003, 5004, 5005]
        assert group['products'][-1]['price'] is None

    def test_the_cards_are_by_rank(self, admin_client, data):
        group = groups(ok(admin_client.get(URL)))[('OGN', 200)]
        assert [one['card_id'] for one in group['cards']] == ['066', '066a']
        assert group['base'] == {'set_id': 'OGN', 'card_id': '066', 'name': 'Ahri, Alluring',
                                 'rarity': 'Rare'}

    def test_a_group_with_as_many_products_as_free_cards_is_not_listed(self, admin_client,
                                                                       data):
        listed = groups(ok(admin_client.get(URL)))
        for key in (('RAD', 102), ('OGN', 204), ('OGN', 205)):
            assert key not in listed

    def test_promo_sets_and_plat_are_left_to_the_missing_promo_cards(self, admin_client, data):
        assert {one['set_id'] for one in ok(admin_client.get(URL))['sets']} == {'OGN', 'RAD'}

    def test_a_product_linked_by_hand_frees_nothing(self, admin_client, data):
        linked(917370, 'RAD', '169')
        db.session.commit()
        group = groups(ok(admin_client.get(URL)))[('RAD', 100)]
        assert (group['status'], group['proposed']['card_id']) == ('create', '169s')
        assert [one['linked'] for one in group['products']][1] == {
            'set_id': 'RAD', 'card_id': '169', 'foil': None}

    def test_once_every_product_is_linked_the_group_leaves(self, admin_client, data):
        linked(917370, 'RAD', '169')
        db.session.commit()
        listed = groups(ok(admin_client.get(URL)))
        assert ('RAD', 100) in listed
        db.session.query(RbcmProductCardMap).filter_by(rbpcm_id_product=917370).delete()
        card('RAD', '169s', 'Hexplosives Expert', 'Showcase', 'Legend', rbcar_tags='Ziggs')
        linked(917370, 'RAD', '169')
        linked(917487, 'RAD', '169s')
        db.session.commit()
        assert ('RAD', 100) not in groups(ok(admin_client.get(URL)))

    def test_no_load_no_sets(self, admin_client):
        assert ok(admin_client.get(URL)) == {
            'date': None, 'sets': [],
            'summary': {'groups': 0, 'cards_to_create': 0, 'exists': 0, 'manual': 0}}

    def test_unknown_query_key_is_a_400(self, admin_client, data):
        assert refused(admin_client.get(f'{URL}?other=1'))['code'] == 'validation_error'

    def test_writes_nothing(self, admin_client, data):
        ok(admin_client.get(URL))
        assert '169s' not in cards_of('RAD') and audits() == []

    def test_bounded_statements_whatever_the_number_of_groups(self, admin_client, data):
        few = len(statements(admin_client, 'get', URL))
        for n in range(30):
            name = f'Filler {chr(65 + n % 26)}{n // 26}'
            card('RAD', f'{300 + n}', name, 'Rare', 'Legend')
            card('RAD', f'{400 + n}', name, 'Showcase', 'Legend')
            for k in range(3):
                product(9000 + 3 * n + k, name, 600 + n, 1.0 + k)
        db.session.commit()
        many = len(statements(admin_client, 'get', URL))
        assert few == many <= 9
        assert ok(admin_client.get(URL))['summary']['cards_to_create'] == 31


# ---------------------------------------------------------------------------
# S3: create
# ---------------------------------------------------------------------------

class TestCreate:
    def test_creates_the_signed_printing_with_one_audit_row(self, admin_client, data):
        got = ok(admin_client.post(URL, json=CREATE), 201)
        assert got == {
            'created': [{'set_id': 'RAD', 'card_id': '169s', 'name': 'Hexplosives Expert',
                         'rarity': 'Showcase', 'copy_of': {'set_id': 'RAD', 'card_id': '169'},
                         'product_ids': [917370, 917487]}],
            'skipped': []}
        assert '169s' in cards_of('RAD')
        assert audits() == [('cardmarket.missing_printings.create', 'cardmarket',
                             'missing_printings',
                             {'created': 1, 'skipped': 0, 'cards': ['RAD-169s']})]

    def test_the_copy_has_every_field_of_the_showcase_but_the_image(self, admin_client, data):
        ok(admin_client.post(URL, json=CREATE), 201)
        db.session.expire_all()
        signed = db.session.get(RbCard, ('RAD', '169s'))
        fields = ('rbcar_name', 'rbcar_rarity', 'rbcar_type', 'rbcar_domain', 'rbcar_tags',
                  'rbcar_energy', 'rbcar_power', 'rbcar_might', 'rbcar_ability',
                  'rbcar_artist')
        assert {f: getattr(signed, f) for f in fields} == {f: ZIGGS_SHOWCASE[f]
                                                           for f in fields}
        assert signed.image is None and signed.image_url is None

    def test_the_card_id_ignores_case_and_repeats(self, admin_client, data):
        got = ok(admin_client.post(URL, json={'items': [
            {'set_id': 'rad', 'card_id': '169S'}, {'set_id': 'RAD', 'card_id': '169s'}]}), 201)
        assert [one['card_id'] for one in got['created']] == ['169s']

    def test_a_second_call_skips_the_card_and_never_overwrites_it(self, admin_client, data):
        ok(admin_client.post(URL, json=CREATE), 201)
        db.session.get(RbCard, ('RAD', '169s')).rbcar_ability = 'Edited by hand.'
        db.session.commit()
        listed = groups(ok(admin_client.get(URL)))[('RAD', 100)]
        assert (listed['status'], listed['reason'], listed['proposed']) == (
            'exists', 'in_catalog', {'set_id': 'RAD', 'card_id': '169s', 'rarity': 'Showcase'})
        got = ok(admin_client.post(URL, json=CREATE), 200)
        assert got == {'created': [], 'skipped': [
            {'set_id': 'RAD', 'card_id': '169s', 'reason': 'in_catalog'}]}
        db.session.expire_all()
        assert db.session.get(RbCard, ('RAD', '169s')).rbcar_ability == 'Edited by hand.'
        assert audits()[-1][3] == {'created': 0, 'skipped': 1, 'cards': []}

    @pytest.mark.parametrize('items,message,unknown', [
        ([{'set_id': 'RAD', 'card_id': '169s'}, {'set_id': 'RAD', 'card_id': '174s'}],
         'These cards are not proposed by the missing printings list: RAD-174s.',
         ['RAD-174s']),
        ([{'set_id': 'OGN', 'card_id': '066s'}, {'set_id': 'NOPE', 'card_id': '1s'}],
         'These cards are not proposed by the missing printings list: NOPE-1s, OGN-066s.',
         ['NOPE-1s', 'OGN-066s']),
    ])
    def test_cards_not_proposed_are_refused_and_nothing_is_written(
            self, admin_client, data, items, message, unknown):
        body = refused(admin_client.post(URL, json={'items': items}))
        assert body['code'] == 'validation_error'
        assert body['message'] == message
        assert body['details'][0]['field'] == 'items'
        assert body['details'][0]['params'] == {'unknown': unknown}
        assert '169s' not in cards_of('RAD') and audits() == []

    @pytest.mark.parametrize('payload', [
        {}, {'items': []}, {'items': 'x'}, {'items': [{'set_id': 'RAD'}]},
        {'items': [{'set_id': 'RAD', 'card_id': '169s', 'other': 1}]},
        {'items': [{'set_id': 'RAD', 'card_id': '169s'}], 'other': 1},
        {'items': [{'set_id': 'RAD', 'card_id': f'{n}s'} for n in range(201)]},
    ])
    def test_body_validation(self, admin_client, data, payload):
        assert refused(admin_client.post(URL, json=payload))['code'] == 'validation_error'
        assert '169s' not in cards_of('RAD') and audits() == []

    def test_bounded_statements_whatever_the_number_of_cards(self, admin_client, data):
        for n in range(5):
            name = f'Filler {chr(65 + n)}'
            card('RAD', f'{300 + n}', name, 'Rare', 'Legend')
            card('RAD', f'{400 + n}', name, 'Showcase', 'Legend')
            for k in range(3):
                product(9000 + 3 * n + k, name, 600 + n, 1.0 + k)
        db.session.commit()
        one = len(statements(admin_client, 'post', URL, json=CREATE))
        five = len(statements(admin_client, 'post', URL, json={'items': [
            {'set_id': 'RAD', 'card_id': f'{400 + n}s'} for n in range(5)]}))
        assert one == five <= 13


def test_service_has_no_flask_request_objects():
    import inspect
    source = inspect.getsource(missing_printings)
    assert 'from flask' not in source and 'import flask' not in source


# ---------------------------------------------------------------------------
# S1: the review says why the group is ambiguous
# ---------------------------------------------------------------------------

class TestReviewDetail:
    def test_the_ambiguous_legend_says_more_printings_than_cards(self, data):
        _links, review = decided()
        for pid in (917370, 917487):
            item = review[pid]
            assert item['reason'] == 'ambiguous'
            assert item['reason_detail'] == 'more_printings_than_cards'
            assert item['detail'] == {'products': 3, 'cards': 2, 'set_id': 'RAD'}
            assert [(one['set'], one['id']) for one in item['candidates']] == [
                ('RAD', '141'), ('RAD', '169')]

    def test_four_products_for_two_free_cards(self, data):
        _links, review = decided()
        assert review[5001]['detail'] == {'products': 4, 'cards': 2, 'set_id': 'RAD'}

    def test_other_review_items_are_unchanged(self, data):
        _links, review = decided()
        # ambiguous for another reason (one product, two free cards) carries no detail
        product(5030, 'Lonely Pair', 104, 1.0)
        card('RAD', '170', 'Lonely Pair')
        card('RAD', '171', 'Lonely Pair', 'Showcase')
        db.session.commit()
        _links, review = decided()
        assert review[5030]['reason'] == 'ambiguous'
        assert set(review[5030]) == {'product_id', 'name', 'expansion_id', 'reason',
                                     'candidates'}
        assert set(review[6040]) == {'product_id', 'name', 'expansion_id', 'reason',
                                     'candidates'}
        assert review[6040]['reason'] == 'no_candidates'

    def test_the_review_endpoint_carries_the_detail(self, admin_client, data):
        got = ok(admin_client.get(f'{REVIEW}?reason=ambiguous&per_page=200'))
        item = next(one for one in got['items'] if one['product_id'] == 917487)
        assert (item['reason_detail'], item['detail']) == (
            'more_printings_than_cards', {'products': 3, 'cards': 2, 'set_id': 'RAD'})


# ---------------------------------------------------------------------------
# S6: the Radiance acceptance
# ---------------------------------------------------------------------------

class TestRadianceAcceptance:
    def test_after_creating_rad_169s_both_products_are_clear(self, admin_client, data):
        links, review = decided()
        assert 917370 not in links and 917487 not in links
        ok(admin_client.post(URL, json=CREATE), 201)
        links, review = decided()
        assert links[917370] == ('RAD', '169', None)
        assert links[917487] == ('RAD', '169s', None)
        assert 917343 not in links and 917343 not in review
        daily_prices.match_clear_cases(D2)
        db.session.expire_all()
        got = {pid: (m.rbpcm_rbset_id, m.rbpcm_rbcar_id, m.rbpcm_match_type)
               for pid in (917343, 917370, 917487)
               for m in [db.session.get(RbcmProductCardMap, pid)]}
        assert got == {917343: ('RAD', '141', 'manual'), 917370: ('RAD', '169', 'auto'),
                       917487: ('RAD', '169s', 'auto')}
        assert ('RAD', 100) not in groups(ok(admin_client.get(URL)))

    def test_an_unpriced_signed_product_is_clear_too(self, admin_client, data):
        """S5 with S6: the third printing often has no price yet; it is the highest."""
        db.session.query(RbcmPrice).filter_by(rbprc_id_product=917487).delete()
        db.session.commit()
        ok(admin_client.post(URL, json=CREATE), 201)
        links, _review = decided()
        assert (links[917370], links[917487]) == (('RAD', '169', None), ('RAD', '169s', None))
