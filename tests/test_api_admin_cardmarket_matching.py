"""CM-b: the Cardmarket matching API under /riftbound/api/v1/admin/cardmarket (A).

Unmatched products with suggestions, candidates, link / unlink / relink, the links
browser with conflicts, ignored products, auto-match preview / apply and the review
list. Behaviour follows the legacy `price_bp` endpoints pinned in
`tests/test_legacy_price_characterization.py`; data from `tests/cardmarket_matching_data.py`."""
import pytest
import sqlalchemy as sa
from sqlalchemy import event

from app import db
from app.models.audit import RbAdminAudit
from app.models.cardmarket import RbcmIgnored, RbcmProductCardMap
from app.services import cardmarket_log, daily_prices
from tests import cardmarket_matching_data as cm
from tests.test_authz_matrix import classify

BASE = '/riftbound/api/v1/admin/cardmarket'
UNMATCHED = f'{BASE}/unmatched'
LINKS = f'{BASE}/links'
IGNORED = f'{BASE}/ignored'
PREVIEW = f'{BASE}/auto-match/preview'
APPLY = f'{BASE}/auto-match/apply'
REVIEW = f'{BASE}/review'


@pytest.fixture
def data(app):
    cm.build()
    return app


def links():
    db.session.expire_all()
    return [(m.rbpcm_id_product, m.rbpcm_rbset_id, m.rbpcm_rbcar_id, m.rbpcm_foil,
             m.rbpcm_match_type, float(m.rbpcm_confidence))
            for m in db.session.execute(sa.select(RbcmProductCardMap)
                                        .order_by(RbcmProductCardMap.rbpcm_id_product)).scalars()]


def audits():
    db.session.expire_all()
    return [(a.rbaud_action, a.rbaud_target_type, a.rbaud_target_id, a.rbaud_details)
            for a in RbAdminAudit.query.order_by(RbAdminAudit.rbaud_id).all()]


def ok(resp, status=200):
    assert resp.status_code == status, resp.get_json()
    body = resp.get_json()
    assert body['success'] is True
    return body['data']


def err(resp, status, code=None):
    assert resp.status_code == status, resp.get_json()
    body = resp.get_json()
    assert body['success'] is False
    if code:
        assert body.get('code') == code, body
    return body


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


ROUTES = [
    ('get', UNMATCHED), ('get', f'{UNMATCHED}/100/candidates'), ('get', LINKS),
    ('post', LINKS), ('put', f'{LINKS}/100'), ('delete', f'{LINKS}/100'),
    ('get', IGNORED), ('post', IGNORED), ('delete', f'{IGNORED}/500'),
    ('post', PREVIEW), ('post', APPLY), ('get', REVIEW),
]


class TestAuthorization:
    @pytest.mark.parametrize('method,url', ROUTES)
    def test_anonymous_401_user_403(self, app, authenticated_client, data, method, url):
        assert getattr(app.test_client(), method)(url, json={}).status_code == 401
        assert getattr(authenticated_client, method)(url, json={}).status_code == 403
        assert links() == [] and RbcmIgnored.query.count() == 2

    def test_every_rule_is_admin(self, app):
        rules = [rule for rule in app.url_map.iter_rules() if rule.rule.startswith(BASE)]
        assert {classify(rule) for rule in rules} == {'A'}
        found = {(rule.rule, method) for rule in rules for method in rule.methods
                 if method not in ('HEAD', 'OPTIONS')}
        assert {(f'{BASE}/unmatched', 'GET'),
                (f'{BASE}/unmatched/<int:id_product>/candidates', 'GET'),
                (f'{BASE}/links', 'GET'), (f'{BASE}/links', 'POST'),
                (f'{BASE}/links/<int:id_product>', 'PUT'),
                (f'{BASE}/links/<int:id_product>', 'DELETE'),
                (f'{BASE}/ignored', 'GET'), (f'{BASE}/ignored', 'POST'),
                (f'{BASE}/ignored/<int:id_product>', 'DELETE'),
                (f'{BASE}/auto-match/preview', 'POST'), (f'{BASE}/auto-match/apply', 'POST'),
                (f'{BASE}/review', 'GET')} <= found


# ---------------------------------------------------------------------------
# GET /unmatched
# ---------------------------------------------------------------------------

class TestUnmatched:
    def test_same_rows_and_order_as_the_legacy_list(self, admin_client, data):
        cm.link(250, 'OGN', '003')
        db.session.commit()
        got = ok(admin_client.get(UNMATCHED))
        assert [(i['id_product'], i['name'], i['type'], i['low_price'])
                for i in got['items']] == [
            (100, 'Jinx', 'single', 0.1),
            (101, 'Jinx (Foil)', 'single', 1.0),
            (400, 'Mystery Card', 'single', 0.5),
            (300, 'Origins Booster Box', 'nonsingle', 100.0),
            (301, 'Origins Playmat', 'nonsingle', None),
            (501, 'Renamed Thing', 'single', None),
            (200, 'Vi', 'single', 2.0),
            (201, 'Vi (Promo)', 'single', 5.0),
        ]
        assert got['meta'] == {'page': 1, 'per_page': 50, 'total': 8, 'pages': 1,
                               'date': '2030-10-02'}

    def test_item_shape(self, admin_client, data):
        items = {i['id_product']: i for i in ok(admin_client.get(UNMATCHED))['items']}
        assert items[100] == {
            'id_product': 100, 'name': 'Jinx', 'type': 'single',
            'category': 'Riftbound Single',
            'expansion': {'id': 10, 'name': 'Origins', 'set_id': 'OGN'},
            'low_price': 0.1, 'first_seen_date': '2030-10-01',
            'suggestions': [{'kind': 'card', 'id': 'OGN-001', 'name': 'Jinx', 'set': 'OGN',
                             'number': '001', 'score': 1.0, 'free_foils': ['N', 'S']}]}
        assert items[101]['first_seen_date'] == '2030-10-02'
        assert items[301]['expansion'] == {'id': 12, 'name': 'Accessories', 'set_id': None}

    def test_type_single_total_is_the_load_log_unmatched_count(self, admin_client, data):
        cm.link(100, 'OGN', '001', 'N')
        db.session.commit()
        total = ok(admin_client.get(f'{UNMATCHED}?type=single'))['meta']['total']
        assert total == cardmarket_log.unmatched_count() == 6
        assert ok(admin_client.get(f'{BASE}/status'))['unmatched'] == total
        assert ok(admin_client.get(f'{UNMATCHED}?type=nonsingle'))['meta']['total'] == 2

    def test_filters(self, admin_client, data):
        def ids(query):
            return [i['id_product'] for i in ok(admin_client.get(f'{UNMATCHED}{query}'))['items']]
        assert ids('?q=jinx') == [100, 101]
        assert ids('?q=201') == [201]
        assert ids('?category=playmat') == [301]
        assert ids('?type=nonsingle&q=box') == [300]

    def test_pagination(self, admin_client, data):
        got = ok(admin_client.get(f'{UNMATCHED}?per_page=25&page=1'))
        assert got['meta']['pages'] == 1 and len(got['items']) == 9
        assert ok(admin_client.get(f'{UNMATCHED}?page=2'))['items'] == []

    @pytest.mark.parametrize('query', ['?type=foo', '?per_page=7', '?page=0', '?nope=1',
                                       f'?q={"x" * 101}'])
    def test_bad_query_is_400(self, admin_client, data, query):
        err(admin_client.get(f'{UNMATCHED}{query}'), 400, 'validation_error')

    def test_no_load_is_empty(self, admin_client):
        got = ok(admin_client.get(UNMATCHED))
        assert got['items'] == [] and got['meta']['total'] == 0 and got['meta']['date'] is None

    def test_suggestions(self, admin_client, data):
        cm.link(200, 'OGN', '002')
        db.session.commit()
        items = {i['id_product']: i for i in ok(admin_client.get(UNMATCHED))['items']}
        # the promo expansion prefers the promo set; the taken slot shows no free foil
        assert items[201]['suggestions'] == [
            {'kind': 'card', 'id': 'OGNX-002', 'name': 'Vi', 'set': 'OGNX', 'number': '002',
             'score': 1.0, 'free_foils': [None]},
            {'kind': 'card', 'id': 'OGN-002', 'name': 'Vi', 'set': 'OGN', 'number': '002',
             'score': 0.9, 'free_foils': []}]
        assert [s['id'] for s in items[250]['suggestions']] == ['OGN-003']   # legend tags
        assert items[400]['suggestions'] == []
        # a non-single is linked by its Cardmarket id to the product of the same id
        assert items[300]['suggestions'] == [
            {'kind': 'product', 'id': 300, 'name': 'Origins Booster Box', 'set': 'OGN',
             'number': None, 'score': 1.0, 'free_foils': []}]
        assert items[301]['suggestions'] == []

    def test_close_names_are_suggested_with_a_lower_score(self, admin_client, data):
        cm.product(600, 'Jinxx', metacard=60)
        db.session.commit()
        item = next(i for i in ok(admin_client.get(f'{UNMATCHED}?q=jinxx'))['items'])
        assert [(s['id'], s['score'] < 1.0) for s in item['suggestions']] == [('OGN-001', True)]

    def test_at_most_three_suggestions(self, admin_client, data):
        for n in range(5):
            cm.card('OGN', f'1{n}', 'Echo', 'Rare')
        cm.product(601, 'Echo', metacard=61)
        db.session.commit()
        item = ok(admin_client.get(f'{UNMATCHED}?q=echo'))['items'][0]
        assert len(item['suggestions']) == 3

    def test_bounded_statements_whatever_the_page_size(self, admin_client, data):
        few = statements(admin_client, 'get', f'{UNMATCHED}?per_page=25')
        for n in range(40):
            cm.product(1000 + n, f'Extra {n}', metacard=2000 + n)
            cm.price(1000 + n, 1)
        db.session.commit()
        many = statements(admin_client, 'get', f'{UNMATCHED}?per_page=50')
        assert len(many) == len(few) and len(many) <= 9, many


# ---------------------------------------------------------------------------
# GET /unmatched/<id>/candidates
# ---------------------------------------------------------------------------

class TestCandidates:
    def test_without_q_the_suggested_cards(self, admin_client, data):
        got = ok(admin_client.get(f'{UNMATCHED}/201/candidates'))
        assert got['product'] == {
            'id_product': 201, 'name': 'Vi (Promo)', 'type': 'single',
            'category': 'Riftbound Single',
            'expansion': {'id': 11, 'name': 'Origins Promos', 'set_id': 'OGNX'},
            'date': '2030-10-02', 'link': None}
        assert [(c['set_id'], c['card_id']) for c in got['cards']] == [('OGNX', '002'),
                                                                       ('OGN', '002')]
        assert got['products'] == []

    def test_free_text_search_with_card_details_and_links(self, admin_client, data):
        cm.link(100, 'OGN', '001', 'N')
        db.session.commit()
        got = ok(admin_client.get(f'{UNMATCHED}/101/candidates?q=jin'))
        assert got['cards'] == [{
            'set_id': 'OGN', 'card_id': '001', 'name': 'Jinx', 'rarity': 'Common',
            'type': 'Unit', 'image_src': '/riftbound/media/cards/ogn/ogn_001.png',
            'links': [{'id_product': 100, 'foil': 'N'}]}]
        by_number = ok(admin_client.get(f'{UNMATCHED}/101/candidates?q=OGNX-002'))['cards']
        assert [(c['set_id'], c['card_id']) for c in by_number] == [('OGNX', '002')]

    def test_a_linked_product_shows_its_link(self, admin_client, data):
        cm.link(100, 'OGN', '001', 'N')
        db.session.commit()
        assert ok(admin_client.get(f'{UNMATCHED}/100/candidates'))['product']['link'] == {
            'set_id': 'OGN', 'card_id': '001', 'foil': 'N', 'match_type': 'manual'}

    def test_non_single_lists_products(self, admin_client, data):
        got = ok(admin_client.get(f'{UNMATCHED}/300/candidates'))
        assert [p['id'] for p in got['products']] == [300]
        assert ok(admin_client.get(f'{UNMATCHED}/301/candidates?q=booster'))['products'][0] \
            == {'id': 300, 'name': 'Origins Booster Box', 'set_id': 'OGN', 'kind': 'box',
                'category': None}

    def test_unknown_product_is_404(self, admin_client, data):
        err(admin_client.get(f'{UNMATCHED}/999999/candidates'), 404)

    def test_q_too_short_is_400(self, admin_client, data):
        err(admin_client.get(f'{UNMATCHED}/100/candidates?q=a'), 400, 'validation_error')


# ---------------------------------------------------------------------------
# POST /links, DELETE /links/<id>, PUT /links/<id>
# ---------------------------------------------------------------------------

def link_body(id_product, set_id, card_id, foil=None, **extra):
    return {'id_product': id_product, 'card': {'set_id': set_id, 'card_id': card_id},
            'foil': foil, **extra}


class TestLink:
    def test_creates_a_manual_link_and_audits(self, admin_client, data):
        got = ok(admin_client.post(LINKS, json=link_body(100, 'OGN', '001', 'N')), 201)
        assert got == {
            'id_product': 100, 'product_name': 'Jinx', 'product_type': 'single',
            'in_latest_load': True, 'set_id': 'OGN', 'card_id': '001', 'card_name': 'Jinx',
            'foil': 'N', 'match_type': 'manual', 'confidence': 1.0, 'low_price': 0.1,
            'price_date': '2030-10-02'}
        assert links() == [(100, 'OGN', '001', 'N', 'manual', 1.0)]
        assert audits() == [('cardmarket.link', 'cardmarket_product', '100',
                             {'set_id': 'OGN', 'card_id': '001', 'foil': 'N'})]
        assert cardmarket_log.unmatched_count() == 6

    def test_null_foil_and_a_non_single(self, admin_client, data):
        ok(admin_client.post(LINKS, json=link_body(200, 'OGN', '002')), 201)
        ok(admin_client.post(LINKS, json=link_body(301, 'OGN', '004')), 201)  # like legacy
        assert [row[:4] for row in links()] == [(200, 'OGN', '002', None),
                                                (301, 'OGN', '004', None)]

    def test_an_already_linked_product_is_409_unlink_first(self, admin_client, data):
        cm.link(100, 'OGN', '001', 'N')
        db.session.commit()
        body = err(admin_client.post(LINKS, json=link_body(100, 'OGN', '004')), 409,
                   'already_exists')
        assert body['params'] == {'field': 'id_product', 'set_id': 'OGN', 'card_id': '001',
                                  'foil': 'N'}
        assert 'Unlink it first' in body['message']
        assert links() == [(100, 'OGN', '001', 'N', 'manual', 1.0)] and audits() == []

    def test_a_taken_card_slot_is_409(self, admin_client, data):
        cm.link(100, 'OGN', '001', 'N')
        cm.link(200, 'OGN', '002')
        db.session.commit()
        body = err(admin_client.post(LINKS, json=link_body(101, 'OGN', '001', 'N')), 409,
                   'already_exists')
        assert body['params'] == {'field': 'card', 'linked_id_product': 100}
        # two null foils are the same slot; null and N are not (legacy)
        err(admin_client.post(LINKS, json=link_body(201, 'OGN', '002')), 409, 'already_exists')
        ok(admin_client.post(LINKS, json=link_body(201, 'OGN', '002', 'N')), 201)
        ok(admin_client.post(LINKS, json=link_body(101, 'OGN', '001', 'S')), 201)
        assert len(links()) == 4

    def test_unknown_cardmarket_product_is_404(self, admin_client, data):
        err(admin_client.post(LINKS, json=link_body(999999, 'OGN', '001')), 404)
        assert links() == []

    def test_unknown_card_is_400(self, admin_client, data):
        body = err(admin_client.post(LINKS, json=link_body(100, 'OGN', '999')), 400,
                   'validation_error')
        assert body['details'][0]['field'] == 'card'
        assert links() == []

    def test_product_links_are_by_cardmarket_id(self, admin_client, data):
        body = err(admin_client.post(LINKS, json={'id_product': 300, 'kind': 'product',
                                                  'product_id': 300}), 400, 'validation_error')
        assert body['details'][0]['field'] == 'kind'
        assert 'Cardmarket id' in body['details'][0]['message']
        assert links() == []

    @pytest.mark.parametrize('payload', [
        {'card': {'set_id': 'OGN', 'card_id': '001'}},
        {'id_product': 0, 'card': {'set_id': 'OGN', 'card_id': '001'}},
        {'id_product': 100, 'card': {'set_id': 'OGN', 'card_id': '001'}, 'foil': 'X'},
        {'id_product': 100},
        {'id_product': 100, 'card': {'set_id': 'OGN'}},
        {'id_product': 100, 'card': {'set_id': 'OGN', 'card_id': '001'}, 'extra': 1},
    ])
    def test_invalid_body_is_400(self, admin_client, data, payload):
        err(admin_client.post(LINKS, json=payload), 400, 'validation_error')
        assert links() == []


class TestUnlink:
    def test_removes_and_returns_the_link_for_undo(self, admin_client, data):
        cm.link(100, 'OGN', '001', 'N', match_type='auto', confidence=0.7)
        db.session.commit()
        got = ok(admin_client.delete(f'{LINKS}/100'))
        assert got['link']['set_id'] == 'OGN' and got['link']['match_type'] == 'auto'
        assert got['link']['confidence'] == 0.7
        assert links() == []
        assert audits() == [('cardmarket.unlink', 'cardmarket_product', '100',
                             {'set_id': 'OGN', 'card_id': '001', 'foil': 'N',
                              'match_type': 'auto'})]
        undo = {'id_product': 100, 'card': {'set_id': got['link']['set_id'],
                                            'card_id': got['link']['card_id']},
                'foil': got['link']['foil']}
        ok(admin_client.post(LINKS, json=undo), 201)

    def test_no_link_is_404(self, admin_client, data):
        err(admin_client.delete(f'{LINKS}/100'), 404)
        assert audits() == []


class TestRelink:
    @pytest.fixture
    def linked(self, data):
        cm.link(100, 'OGN', '001', 'N')
        cm.link(101, 'OGN', '001', 'S')
        db.session.commit()

    def test_moves_the_link_in_one_step(self, admin_client, linked):
        got = ok(admin_client.put(f'{LINKS}/100', json={
            'card': {'set_id': 'OGN', 'card_id': '004'}, 'foil': None}))
        assert got['previous']['card_id'] == '001'
        assert (got['link']['card_id'], got['link']['foil']) == ('004', None)
        assert links()[0] == (100, 'OGN', '004', None, 'manual', 1.0)
        assert audits() == [('cardmarket.relink', 'cardmarket_product', '100', {
            'from': {'set_id': 'OGN', 'card_id': '001', 'foil': 'N'},
            'to': {'set_id': 'OGN', 'card_id': '004', 'foil': None}})]

    def test_its_own_slot_is_not_a_conflict(self, admin_client, linked):
        ok(admin_client.put(f'{LINKS}/100', json={
            'card': {'set_id': 'OGN', 'card_id': '001'}, 'foil': 'N'}))
        assert links()[0] == (100, 'OGN', '001', 'N', 'manual', 1.0)

    def test_a_slot_of_another_product_is_409_and_nothing_changes(self, admin_client, linked):
        body = err(admin_client.put(f'{LINKS}/100', json={
            'card': {'set_id': 'OGN', 'card_id': '001'}, 'foil': 'S'}), 409, 'already_exists')
        assert body['params'] == {'field': 'card', 'linked_id_product': 101}
        assert links()[0] == (100, 'OGN', '001', 'N', 'manual', 1.0) and audits() == []

    def test_no_link_is_404_unknown_card_400(self, admin_client, linked):
        err(admin_client.put(f'{LINKS}/200', json={
            'card': {'set_id': 'OGN', 'card_id': '002'}}), 404)
        err(admin_client.put(f'{LINKS}/100', json={
            'card': {'set_id': 'OGN', 'card_id': '999'}}), 400, 'validation_error')
        err(admin_client.put(f'{LINKS}/100', json={'kind': 'product', 'product_id': 300}),
            400, 'validation_error')
        assert links()[0] == (100, 'OGN', '001', 'N', 'manual', 1.0)

    def test_a_failure_halfway_keeps_the_old_link(self, admin_client, linked, monkeypatch):
        from app.services import audit

        def boom(*args, **kwargs):
            raise RuntimeError('audit down')

        monkeypatch.setattr(audit, 'record', boom)
        resp = admin_client.put(f'{LINKS}/100', json={
            'card': {'set_id': 'OGN', 'card_id': '004'}})
        assert resp.status_code == 500
        assert links()[0] == (100, 'OGN', '001', 'N', 'manual', 1.0)


# ---------------------------------------------------------------------------
# GET /links
# ---------------------------------------------------------------------------

class TestLinksBrowser:
    @pytest.fixture
    def linked(self, data):
        cm.link(100, 'OGN', '001', 'N')
        cm.link(101, 'OGN', '001', 'S', match_type='auto', confidence=0.7)
        cm.link(200, 'OGN', '002')
        cm.link(201, 'OGN', '002')                 # same null slot: a conflict
        cm.link(900, 'OGN', '004')                 # product gone from the latest load
        db.session.commit()

    def ids(self, client, query=''):
        return [i['id_product'] for i in ok(client.get(f'{LINKS}{query}'))['items']]

    def test_every_link_by_product_name(self, admin_client, linked):
        got = ok(admin_client.get(LINKS))
        assert [i['id_product'] for i in got['items']] == [900, 100, 101, 200, 201]
        gone = got['items'][0]
        assert (gone['product_name'], gone['in_latest_load'], gone['low_price'],
                gone['price_date']) == ('Gone Card', False, 0.01, '2030-10-01')
        assert got['meta'] == {'page': 1, 'per_page': 50, 'total': 5, 'pages': 1,
                               'conflict_slots': 1}

    def test_filters(self, admin_client, linked):
        assert self.ids(admin_client, '?q=jinx') == [100, 101]
        assert self.ids(admin_client, '?q=201') == [201]
        assert self.ids(admin_client, '?q=fury') == [900]
        assert self.ids(admin_client, '?set=ogn') == [900, 100, 101, 200, 201]
        assert self.ids(admin_client, '?set=ognx') == []
        assert self.ids(admin_client, '?foil=S') == [101]
        assert self.ids(admin_client, '?foil=none') == [900, 200, 201]
        assert self.ids(admin_client, '?match_type=auto') == [101]

    def test_conflicts_lists_slots_with_more_than_one_product(self, admin_client, linked):
        assert self.ids(admin_client, '?conflicts=true') == [200, 201]

    def test_pagination_and_bad_query(self, admin_client, linked):
        got = ok(admin_client.get(f'{LINKS}?per_page=25&page=2'))
        assert got['items'] == [] and got['meta']['total'] == 5
        err(admin_client.get(f'{LINKS}?foil=X'), 400, 'validation_error')
        err(admin_client.get(f'{LINKS}?conflicts=maybe'), 400, 'validation_error')

    def test_bounded_statements(self, admin_client, linked):
        few = statements(admin_client, 'get', LINKS)
        for n in range(30):
            cm.product(1000 + n, f'Extra {n}', metacard=3000 + n)
            cm.card('OGN', f'5{n:02d}', f'Extra {n}', 'Rare')
            cm.link(1000 + n, 'OGN', f'5{n:02d}')
            cm.price(1000 + n, 1)
        db.session.commit()
        many = statements(admin_client, 'get', LINKS)
        assert len(many) == len(few) and len(many) <= 5, many


# ---------------------------------------------------------------------------
# Ignored
# ---------------------------------------------------------------------------

class TestIgnored:
    def test_list_newest_first_with_price(self, admin_client, data):
        assert ok(admin_client.get(IGNORED))['items'] == [
            {'id_product': 500, 'name': 'Ignored Thing', 'low_price': None,
             'ignored_at': '2030-10-02T08:00:00'},
            {'id_product': 501, 'name': 'Old Name', 'low_price': None,
             'ignored_at': '2030-10-01T08:00:00'}]

    def test_add_is_idempotent_and_audited_once(self, admin_client, data):
        got = ok(admin_client.post(IGNORED, json={'id_product': 400, 'name': 'Mystery Card'}),
                 201)
        assert got['created'] is True and got['item']['low_price'] == 0.5
        again = ok(admin_client.post(IGNORED, json={'id_product': 400,
                                                    'name': 'Mystery Card'}))
        assert again['created'] is False
        assert audits() == [('cardmarket.ignore', 'cardmarket_product', '400',
                             {'name': 'Mystery Card'})]
        ids = [i['id_product'] for i in ok(admin_client.get(UNMATCHED))['items']]
        assert 400 not in ids and cardmarket_log.unmatched_count() == 6

    def test_restore(self, admin_client, data):
        got = ok(admin_client.delete(f'{IGNORED}/500'))
        assert got['removed'] == [{'id_product': 500, 'name': 'Ignored Thing'}]
        assert audits() == [('cardmarket.unignore', 'cardmarket_product', '500',
                             {'names': ['Ignored Thing']})]
        assert 500 in [i['id_product'] for i in ok(admin_client.get(UNMATCHED))['items']]

    def test_restore_one_name(self, admin_client, data):
        cm.ignore(500, 'Other Name')
        db.session.commit()
        ok(admin_client.delete(f'{IGNORED}/500?name=Other%20Name'))
        assert [(r.rbig_id_product, r.rbig_name) for r in
                RbcmIgnored.query.order_by(RbcmIgnored.rbig_id_product).all()] == [
            (500, 'Ignored Thing'), (501, 'Old Name')]

    def test_restore_nothing_is_404(self, admin_client, data):
        err(admin_client.delete(f'{IGNORED}/400'), 404)
        err(admin_client.delete(f'{IGNORED}/500?name=Nope'), 404)
        assert audits() == []

    @pytest.mark.parametrize('payload', [{'id_product': 0, 'name': 'x'},
                                         {'id_product': 1, 'name': ' '},
                                         {'id_product': 1}, {'id_product': 1, 'name': 'x',
                                                             'more': 1}])
    def test_add_validation(self, admin_client, data, payload):
        err(admin_client.post(IGNORED, json=payload), 400, 'validation_error')


# ---------------------------------------------------------------------------
# Auto-match preview / apply, review
# ---------------------------------------------------------------------------

class TestAutoMatch:
    def test_preview_writes_nothing(self, admin_client, data):
        got = ok(admin_client.post(PREVIEW))
        decided = daily_prices.classify_unmapped(cm.D2)
        assert got['date'] == '2030-10-02'
        assert got['proposed'] == decided['proposed'] == 5
        assert got['clear'] == len(decided['links']) == 1
        assert got['doubtful'] == len(decided['review'])
        assert got['links'] == [{
            'id_product': 250, 'product_name': 'Ahri, Nine-Tailed Fox', 'low_price': 9.0,
            'set_id': 'OGN', 'card_id': '003', 'card_name': 'Ahri', 'foil': None}]
        assert {(i['product_id'], i['reason']) for i in got['review']} >= {
            (100, 'ambiguous'), (400, 'no_candidates'), (501, 'no_candidates')}
        assert got['review_total'] == len(got['review'])
        assert links() == [] and audits() == []

    def test_preview_matches_what_the_daily_job_links(self, admin_client, data):
        preview = ok(admin_client.post(PREVIEW))
        daily_prices.match_clear_cases(cm.D2)
        assert [(row[0], row[1], row[2], row[3]) for row in links()] == [
            (link['id_product'], link['set_id'], link['card_id'], link['foil'])
            for link in preview['links']]

    def test_apply_links_the_clear_cases_and_audits_counts(self, admin_client, data):
        got = ok(admin_client.post(APPLY, json={}))
        assert (got['linked'], got['clear'], got['remaining_clear']) == (1, 1, 0)
        assert links() == [(250, 'OGN', '003', None, 'auto', 0.7)]
        assert audits() == [('cardmarket.auto_match', 'cardmarket', '2030-10-02',
                             {'linked': 1, 'clear': 1, 'doubtful': got['doubtful'],
                              'max_groups': 200})]
        again = ok(admin_client.post(APPLY, json={}))
        assert again['linked'] == 0 and len(audits()) == 2

    def test_apply_is_bounded_by_max_groups(self, admin_client, data):
        for n, word in enumerate(('Alpha', 'Beta', 'Gamma')):   # numbers are normalised away
            cm.card('OGN', f'7{n}', f'Solo {word}', 'Rare')
            cm.product(700 + n, f'Solo {word}', metacard=700 + n)
        db.session.commit()
        got = ok(admin_client.post(APPLY, json={'max_groups': 2}))
        assert (got['linked'], got['clear'], got['remaining_clear']) == (2, 4, 2)
        assert [row[0] for row in links()] == [250, 700]

    @pytest.mark.parametrize('payload', [{'max_groups': 0}, {'max_groups': 201},
                                         {'other': 1}])
    def test_apply_validation(self, admin_client, data, payload):
        err(admin_client.post(APPLY, json=payload), 400, 'validation_error')
        assert links() == []

    def test_nothing_loaded(self, admin_client):
        assert ok(admin_client.post(PREVIEW))['date'] is None
        assert ok(admin_client.post(APPLY, json={}))['linked'] == 0


class TestReview:
    def test_the_doubtful_cases_of_the_latest_load(self, admin_client, data):
        got = ok(admin_client.get(REVIEW))
        decided = daily_prices.classify_unmapped(cm.D2)
        assert got['items'] == decided['review']
        assert got['meta']['total'] == len(decided['review'])
        assert got['meta']['date'] == '2030-10-02'
        assert got['meta']['reasons'] == {'ambiguous': 4, 'no_candidates': 2,
                                          'ignored_pair': 1}

    def test_reason_filter_and_paging(self, admin_client, data):
        got = ok(admin_client.get(f'{REVIEW}?reason=no_candidates'))
        assert [i['product_id'] for i in got['items']] == [400, 501]
        assert ok(admin_client.get(f'{REVIEW}?page=2'))['items'] == []
        err(admin_client.get(f'{REVIEW}?reason=bogus'), 400, 'validation_error')

    def test_a_manual_link_leaves_the_review_list(self, admin_client, data):
        ok(admin_client.post(LINKS, json=link_body(400, 'OGN', '004')), 201)
        ids = [i['product_id'] for i in ok(admin_client.get(REVIEW))['items']]
        assert 400 not in ids
