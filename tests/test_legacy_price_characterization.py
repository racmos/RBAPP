"""CM-b step 0: pin what the legacy Jinja admin endpoints of `price_bp` do today, so the
`/admin/cardmarket` matching API can be checked against the same behaviour.

The legacy file (`app/routes/domains/price.py`) is not changed by CM-b; these tests only
observe it. Data: `tests/cardmarket_matching_data.py`."""
import pytest
import sqlalchemy as sa

from app import db
from app.models.cardmarket import RbcmIgnored, RbcmProductCardMap
from tests import cardmarket_matching_data as cm

PRICE = '/riftbound/price'


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


def body(resp, status=200):
    assert resp.status_code == status, resp.get_json()
    return resp.get_json()


def test_legacy_routes_are_admin_only(app, authenticated_client, data):
    assert app.test_client().get(f'{PRICE}/cardmarket-unmatched').status_code in (302, 401)
    assert authenticated_client.get(f'{PRICE}/cardmarket-unmatched').status_code == 403


class TestUnmatched:
    def test_latest_date_not_mapped_not_ignored_by_name_then_id(self, admin_client, data):
        cm.link(250, 'OGN', '003')
        db.session.commit()
        got = body(admin_client.get(f'{PRICE}/cardmarket-unmatched'))
        assert got['count'] == 8
        assert [(u['id_product'], u['name'], u['type'], u['low_price'])
                for u in got['unmatched']] == [
            (100, 'Jinx', 'single', 0.1),
            (101, 'Jinx (Foil)', 'single', 1.0),
            (400, 'Mystery Card', 'single', 0.5),
            (300, 'Origins Booster Box', 'nonsingle', 100.0),
            (301, 'Origins Playmat', 'nonsingle', None),
            (501, 'Renamed Thing', 'single', None),      # ignored under another name
            (200, 'Vi', 'single', 2.0),
            (201, 'Vi (Promo)', 'single', 5.0),
        ]
        assert got['unmatched'][3]['category'] == 'Riftbound Booster Box'

    def test_no_products_is_empty(self, admin_client, app):
        assert body(admin_client.get(f'{PRICE}/cardmarket-unmatched')) == {
            'success': True, 'unmatched': [], 'count': 0}


class TestSearchCards:
    def test_under_three_characters_is_empty(self, admin_client, data):
        assert body(admin_client.get(f'{PRICE}/cardmarket-search-cards?q=Vi'))['cards'] == []

    def test_substring_case_insensitive_by_name(self, admin_client, data):
        assert body(admin_client.get(f'{PRICE}/cardmarket-search-cards?q=jin'))['cards'] == [
            {'rbset_id': 'OGN', 'rbcar_id': '001', 'name': 'Jinx'}]


class TestMap:
    def map(self, client, id_product, set_id, car_id, foil=None, status=200):
        return body(client.post(f'{PRICE}/cardmarket-map', json={
            'id_product': id_product, 'rbset_id': set_id, 'rbcar_id': car_id,
            'rbpcm_foil': foil}), status)

    def test_manual_link_with_foil(self, admin_client, data):
        assert self.map(admin_client, 100, 'OGN', '001', 'N') == {
            'success': True, 'message': 'Mapping saved'}
        assert links() == [(100, 'OGN', '001', 'N', 'manual', 1.0)]

    def test_same_card_and_foil_on_another_product_is_a_conflict(self, admin_client, data):
        self.map(admin_client, 100, 'OGN', '001', 'N')
        got = self.map(admin_client, 101, 'OGN', '001', 'N', status=409)
        assert got['success'] is False and got['conflict_id_product'] == 100
        self.map(admin_client, 101, 'OGN', '001', 'S')
        assert links() == [(100, 'OGN', '001', 'N', 'manual', 1.0),
                           (101, 'OGN', '001', 'S', 'manual', 1.0)]

    def test_two_null_foils_conflict_but_null_and_n_do_not(self, admin_client, data):
        self.map(admin_client, 200, 'OGN', '002')
        assert self.map(admin_client, 201, 'OGN', '002', '',
                        status=409)['conflict_id_product'] == 200
        self.map(admin_client, 201, 'OGN', '002', 'N')
        assert links() == [(200, 'OGN', '002', None, 'manual', 1.0),
                           (201, 'OGN', '002', 'N', 'manual', 1.0)]

    def test_mapping_a_linked_product_again_moves_it(self, admin_client, data):
        cm.link(100, 'OGN', '001', 'N', match_type='auto', confidence=0.7)
        db.session.commit()
        self.map(admin_client, 100, 'OGN', '004')
        assert links() == [(100, 'OGN', '004', None, 'manual', 1.0)]

    def test_bad_foil_and_missing_fields_are_400(self, admin_client, data):
        self.map(admin_client, 100, 'OGN', '001', 'X', status=400)
        assert body(admin_client.post(f'{PRICE}/cardmarket-map',
                                      json={'id_product': 100}), 400)['success'] is False
        assert links() == []


class TestUnmap:
    @pytest.fixture
    def linked(self, data):
        cm.link(100, 'OGN', '001', 'N')
        cm.link(101, 'OGN', '001', 'S')
        cm.link(200, 'OGN', '002')
        db.session.commit()

    def test_by_product_id(self, admin_client, linked):
        assert body(admin_client.post(f'{PRICE}/cardmarket-unmap', json={'id_product': 100})) \
            == {'success': True, 'deleted': 1}
        assert [row[0] for row in links()] == [101, 200]

    def test_by_card_and_by_card_and_foil(self, admin_client, linked):
        assert body(admin_client.post(f'{PRICE}/cardmarket-unmap', json={
            'rbset_id': 'OGN', 'rbcar_id': '001', 'rbpcm_foil': 'S'}))['deleted'] == 1
        assert body(admin_client.post(f'{PRICE}/cardmarket-unmap', json={
            'rbset_id': 'OGN', 'rbcar_id': '002'}))['deleted'] == 1
        assert [row[0] for row in links()] == [100]

    def test_nothing_named_is_400(self, admin_client, linked):
        body(admin_client.post(f'{PRICE}/cardmarket-unmap', json={}), 400)


class TestMappings:
    @pytest.fixture
    def linked(self, data):
        cm.link(100, 'OGN', '001', 'N')
        cm.link(101, 'OGN', '001', 'S', match_type='auto', confidence=0.7)
        db.session.commit()

    def rows(self, client, query=''):
        return body(client.get(f'{PRICE}/cardmarket-mappings{query}'))

    def test_singles_of_the_latest_date_mapped_and_unmapped(self, admin_client, linked):
        got = self.rows(admin_client)
        assert got['stats'] == {'total_in_snapshot': 8, 'mapped': 2, 'unmapped': 6,
                                'snapshot_date': cm.D2}
        assert [r['id_product'] for r in got['rows']] == [250, 500, 100, 101, 400, 501, 200, 201]
        assert got['rows'][2] == {
            'id_product': 100, 'product_name': 'Jinx', 'product_type': 'single',
            'low_price': 0.1, 'rbset_id': 'OGN', 'rbcar_id': '001', 'rbcar_name': 'Jinx',
            'rbpcm_foil': 'N', 'match_type': 'manual', 'mapped': True}

    def test_only_and_card_filters(self, admin_client, linked):
        assert [r['id_product'] for r in self.rows(admin_client, '?only=mapped')['rows']] \
            == [100, 101]
        # q_card filters the mapped rows only; unmapped rows stay
        assert [r['id_product'] for r in self.rows(admin_client, '?q_card=zzz')['rows']] \
            == [250, 500, 400, 501, 200, 201]
        assert [r['id_product'] for r in self.rows(admin_client, '?q_set=ognx')['rows']] \
            == [250, 500, 400, 501, 200, 201]
        assert [r['id_product'] for r in self.rows(admin_client, '?q_product=jinx')['rows']] \
            == [100, 101]
        assert self.rows(admin_client, '?include_nonsingles=1')['stats']['total_in_snapshot'] \
            == 10


class TestIgnored:
    def test_add_is_idempotent_list_newest_first_restore(self, admin_client, data):
        for _ in range(2):
            assert body(admin_client.post(f'{PRICE}/ignored/add', json={
                'id_product': 400, 'name': 'Mystery Card'})) == {'success': True}
        listed = body(admin_client.get(f'{PRICE}/ignored'))['ignored']
        # newest first; the row added now is older than the 2030 fixtures
        assert [(i['id_product'], i['name']) for i in listed] == [
            (500, 'Ignored Thing'), (501, 'Old Name'), (400, 'Mystery Card')]
        assert {(i['id_product'], i['low_price']) for i in listed} == {
            (400, 0.5), (500, None), (501, None)}
        assert body(admin_client.post(f'{PRICE}/ignored/restore', json={
            'id_product': 400, 'name': 'Mystery Card'})) == {'success': True}
        assert RbcmIgnored.query.count() == 2

    def test_add_validates(self, admin_client, data):
        body(admin_client.post(f'{PRICE}/ignored/add', json={'id_product': 0, 'name': 'x'}),
             400)


class TestAutoMatch:
    def test_dry_run_proposes_without_writing(self, admin_client, data):
        got = body(admin_client.post(f'{PRICE}/cardmarket-auto-match', json={'dry_run': True}))
        assert set(got) == {'success', 'assigned', 'unmatched', 'skipped', 'no_candidates',
                            'review', 'ignored_count', 'samples'}
        assert links() == []
        proposals = {s['id_product']: (s['rbset_id'], s['rbcar_id'], s['rbpcm_foil'])
                     for s in got['samples']}
        assert proposals == {100: ('OGN', '001', 'N'), 101: ('OGN', '001', 'S'),
                             200: ('OGN', '002', None), 201: ('OGNX', '002', None),
                             250: ('OGN', '003', None)}
        assert (got['assigned'], got['no_candidates'], got['ignored_count']) == (5, 2, 1)
        assert set(got['samples'][0]) == {'id_product', 'product_name', 'price', 'rbset_id',
                                          'rbcar_id', 'rbcar_name', 'rbpcm_foil',
                                          'rbcar_rarity'}

    def test_apply_links_every_proposal_auto(self, admin_client, data):
        got = body(admin_client.post(f'{PRICE}/cardmarket-auto-match', json={}))
        assert got['assigned'] == 5
        assert links() == [(100, 'OGN', '001', 'N', 'auto', 0.7),
                           (101, 'OGN', '001', 'S', 'auto', 0.7),
                           (200, 'OGN', '002', None, 'auto', 0.7),
                           (201, 'OGNX', '002', None, 'auto', 0.7),
                           (250, 'OGN', '003', None, 'auto', 0.7)]
