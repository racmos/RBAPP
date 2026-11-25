"""F14-d S2-S4 (AC2): products admin API (list, kind/set locks, hidden, image)."""
import io
from datetime import datetime

import pytest
from sqlalchemy import event

from app import db
from app.models import RbcmExpansion, RbcmProduct, RbProducts
from app.models.audit import RbAdminAudit
from app.services.products import refresh_products
from tests.image_helpers import jpeg, noise_png, opened, png, webp
from tests.product_helpers import add_price, add_product, add_sets
from tests.test_authz_matrix import classify

URL = '/riftbound/api/v1/admin/products'
DAY = '20300101'
NEXT = '20300102'
NOON = datetime(2030, 1, 1, 12, 0, 0)
PNG = png((1280, 640))
JPG = jpeg((1280, 640))
WEBP = webp((1280, 640))
MAX_BYTES = 10 * 1024 * 1024


def cm(day, product_id, name, category, expansion=None, type_='nonsingle'):
    db.session.add(RbcmProduct(rbprd_date=day, rbprd_id_product=product_id, rbprd_name=name,
                               rbprd_category_name=category, rbprd_id_expansion=expansion,
                               rbprd_type=type_))


@pytest.fixture
def catalog(app):
    """Four non-singles (one hidden, one unlisted without set, one with image) and a single,
    with the Cardmarket rows of DAY so `refresh_products(DAY)` can run."""
    add_sets()
    db.session.add_all([RbcmExpansion(rbexp_id=1, rbexp_rbset_id='OGN'),
                        RbcmExpansion(rbexp_id=3, rbexp_rbset_id=None),
                        RbcmExpansion(rbexp_id=4, rbexp_rbset_id='ARC')])
    add_product(100, 'Origins Booster', kind='booster', set_id='OGN',
                category='Riftbound Booster', updated_at=datetime(2030, 1, 1, 10, 0))
    add_product(101, 'Origins Display', kind='booster_box', set_id='OGN',
                category='Riftbound Display', hidden=True, updated_at=datetime(2030, 1, 3, 10, 0))
    add_product(102, 'Mystery Bundle', kind='sealed_box_set', set_id=None,
                category='Riftbound Gift Bundle', listed=False)
    add_product(103, 'Arcane Starter', kind='champion_deck', set_id='ARC',
                category='Riftbound Starter Deck', image='103.png',
                updated_at=datetime(2030, 1, 2, 10, 0))
    add_product(900, 'Some Card', kind='other', set_id='OGN', type_='single')
    cm(DAY, 100, 'Origins Booster', 'Riftbound Booster', expansion=1)
    cm(DAY, 101, 'Origins Display', 'Riftbound Display', expansion=1)
    cm(DAY, 102, 'Mystery Bundle', 'Riftbound Gift Bundle', expansion=3)
    cm(DAY, 103, 'Arcane Starter', 'Riftbound Starter Deck', expansion=4)
    cm(DAY, 900, 'Some Card', 'Riftbound Single', expansion=1, type_='single')
    add_price(100, DAY, avg7=4.5)
    db.session.commit()
    return app


def payload(resp):
    return resp.get_json()


def ids(resp):
    assert resp.status_code == 200, resp.get_json()
    return [item['id'] for item in payload(resp)['data']['items']]


def product(product_id):
    db.session.expire_all()
    return db.session.get(RbProducts, product_id)


def audits():
    return RbAdminAudit.query.order_by(RbAdminAudit.rbaud_id).all()


def patch(client, product_id, body):
    return client.patch(f'{URL}/{product_id}', json=body)


def upload(client, product_id, data, filename='scan.png'):
    return client.post(f'{URL}/{product_id}/image',
                       data={'file': (io.BytesIO(data), filename)},
                       content_type='multipart/form-data')


# ---------------------------------------------------------------------------
# S2: GET /admin/products
# ---------------------------------------------------------------------------

class TestList:
    def test_all_non_singles_by_name_hidden_and_unlisted_included(self, admin_client, catalog):
        resp = admin_client.get(URL)
        assert ids(resp) == [103, 102, 100, 101]
        assert payload(resp)['data']['meta'] == {'page': 1, 'per_page': 50, 'total': 4,
                                                 'pages': 1}

    def test_item_is_a_product_summary_plus_the_admin_fields(self, admin_client, catalog):
        items = payload(admin_client.get(URL))['data']['items']
        booster = next(item for item in items if item['id'] == 100)
        assert booster == {
            'id': 100, 'name': 'Origins Booster', 'kind': 'booster',
            'category': 'Riftbound Booster', 'set_id': 'OGN', 'image_src': None,
            'listed': True,
            'price': {'value': 4.5, 'source': 'avg7', 'change_7d_pct': None,
                      'change_30d_pct': None, 'as_of': '2030-01-01'},
            'owned_qty': 0,
            'hidden': False, 'kind_locked': False, 'set_locked': False,
            'rbpdt_type': 'nonsingle', 'updated_at': '2030-01-01T10:00:00Z',
            'image': None, 'has_image': False,
        }
        starter = next(item for item in items if item['id'] == 103)
        assert starter['image_src'] == '/riftbound/media/products/103.png'
        bundle = next(item for item in items if item['id'] == 102)
        assert (bundle['set_id'], bundle['listed'], bundle['price'], bundle['updated_at']) == (
            None, False, None, None)

    def test_the_user_catalog_still_hides_the_hidden_product(self, authenticated_client,
                                                            catalog):
        resp = authenticated_client.get('/riftbound/api/v1/products?listed=any')
        assert ids(resp) == [103, 102, 100]

    @pytest.mark.parametrize('query, expected', [
        ('q=origins', [100, 101]),
        ('q=  ORIGINS  ', [100, 101]),
        ('q=102', [102]),
        ('q=nothing', []),
        ('kind=booster_box&kind=sealed_box_set', [102, 101]),
        ('kind=champion_deck', [103]),
        ('hidden=yes', [101]),
        ('hidden=no', [103, 102, 100]),
        ('hidden=any', [103, 102, 100, 101]),
        ('listed=yes', [103, 100, 101]),
        ('listed=no', [102]),
        ('no_set=true', [102]),
        ('no_set=false', [103, 102, 100, 101]),
        ('no_image=true', [103, 102, 100, 101]),   # 103.png is not on disk (F13-h S2)
        ('kind=booster_box&hidden=no', []),
        ('q=origins&kind=booster', [100]),
    ])
    def test_filters(self, admin_client, catalog, query, expected):
        assert ids(admin_client.get(f'{URL}?{query}')) == expected

    def test_an_empty_image_counts_as_no_image(self, admin_client, catalog):
        product(100).rbpdt_image = ''
        db.session.commit()
        assert ids(admin_client.get(f'{URL}?no_image=true')) == [103, 102, 100, 101]

    @pytest.mark.parametrize('query, expected', [
        ('sort=name&dir=desc', [101, 100, 102, 103]),
        ('sort=updated', [100, 103, 101, 102]),
        ('sort=updated&dir=desc', [101, 103, 100, 102]),
    ])
    def test_sorts_with_nulls_last(self, admin_client, catalog, query, expected):
        assert ids(admin_client.get(f'{URL}?{query}')) == expected

    def test_equal_updated_times_tie_by_name(self, admin_client, catalog):
        product(100).rbpdt_updated_at = datetime(2030, 1, 2, 10, 0)
        db.session.commit()
        assert ids(admin_client.get(f'{URL}?sort=updated')) == [103, 100, 101, 102]

    def test_pagination(self, admin_client, catalog):
        for n in range(55):
            add_product(1000 + n, f'Zz Extra {n:02d}', set_id=None)
        db.session.commit()
        first = admin_client.get(URL)
        assert len(ids(first)) == 50
        second = admin_client.get(f'{URL}?page=2')
        assert payload(second)['data']['meta'] == {'page': 2, 'per_page': 50, 'total': 59,
                                                   'pages': 2}
        assert ids(second) == [1000 + n for n in range(46, 55)]
        assert len(ids(admin_client.get(f'{URL}?per_page=100'))) == 59
        assert len(ids(admin_client.get(f'{URL}?per_page=200'))) == 59
        beyond = admin_client.get(f'{URL}?page=9')
        assert ids(beyond) == []
        assert payload(beyond)['data']['meta']['pages'] == 2

    def test_an_empty_catalog_has_one_page(self, admin_client, app):
        assert payload(admin_client.get(URL))['data']['meta'] == {
            'page': 1, 'per_page': 50, 'total': 0, 'pages': 1}

    @pytest.mark.parametrize('query', [
        'sort=price', 'dir=sideways', 'page=0', 'per_page=7', 'per_page=48',
        'hidden=maybe', 'hidden=true', 'listed=true', 'listed=maybe', 'kind=nope',
        'no_set=maybe', 'no_image=1x', 'unknown_param=1',
        # taxonomy 2026-11-20: the old kinds and the virtual ones are not kinds any more
        'kind=box', 'kind=case', 'kind=bundle', 'kind=starter', 'kind=sleeves', 'kind=card',
        'kind=unused',
    ])
    def test_bad_params_are_400(self, admin_client, catalog, query):
        resp = admin_client.get(f'{URL}?{query}')
        assert resp.status_code == 400, query
        body = payload(resp)
        assert body['code'] == 'validation_error'
        assert body['message'] == 'Invalid query parameters'

    def _selects(self, client, url):
        counted = []

        def before(conn, cursor, statement, params, context, executemany):
            if statement.lstrip().upper().startswith('SELECT'):
                counted.append(statement)

        event.listen(db.engine, 'before_cursor_execute', before)
        try:
            assert client.get(url).status_code == 200
        finally:
            event.remove(db.engine, 'before_cursor_execute', before)
        return counted

    def test_bounded_queries_whatever_the_catalog_size(self, admin_client, catalog):
        small = self._selects(admin_client, URL)
        for n in range(55):
            add_product(1000 + n, f'Zz Extra {n:02d}')
            add_price(1000 + n, DAY, trend=1.0)
        db.session.commit()
        large = self._selects(admin_client, f'{URL}?per_page=200')
        assert len(small) <= 5, small
        assert len(large) == len(small), large


# ---------------------------------------------------------------------------
# S3: PATCH /admin/products/<id>
# ---------------------------------------------------------------------------

class TestPatchHidden:
    def test_hide_and_audit(self, admin_client, catalog, frozen_clock):
        resp = patch(admin_client, 100, {'hidden': True})
        assert resp.status_code == 200
        item = payload(resp)['data']
        assert (item['id'], item['hidden'], item['updated_at']) == (100, True,
                                                                     '2030-01-01T12:00:00Z')
        assert set(item) >= {'kind_locked', 'set_locked', 'rbpdt_type', 'price', 'owned_qty'}
        row = product(100)
        assert (row.rbpdt_hidden, row.rbpdt_updated_at) == (True, NOON)
        (audit,) = audits()
        assert (audit.rbaud_action, audit.rbaud_target_type, audit.rbaud_target_id,
                audit.rbaud_details, audit.rbaud_actor_username) == (
            'product.update', 'product', '100', {'hidden': [False, True]}, 'admin')

    def test_unhide(self, admin_client, catalog):
        assert payload(patch(admin_client, 101, {'hidden': False}))['data']['hidden'] is False
        assert audits()[0].rbaud_details == {'hidden': [True, False]}

    def test_hidden_survives_a_refresh(self, admin_client, catalog):
        patch(admin_client, 100, {'hidden': True})
        refresh_products(DAY)
        assert product(100).rbpdt_hidden is True

    def test_no_change_writes_nothing(self, admin_client, catalog, frozen_clock):
        resp = patch(admin_client, 100, {'hidden': False})
        assert resp.status_code == 200
        assert audits() == []
        assert product(100).rbpdt_updated_at == datetime(2030, 1, 1, 10, 0)

    def test_an_empty_body_changes_nothing(self, admin_client, catalog):
        assert patch(admin_client, 100, {}).status_code == 200
        assert audits() == []


class TestPatchKind:
    def test_a_kind_locks_it_and_the_refresh_respects_the_lock(self, admin_client, catalog,
                                                              frozen_clock):
        item = payload(patch(admin_client, 100, {'kind': 'booster_box'}))['data']
        assert (item['kind'], item['kind_locked']) == ('booster_box', True)
        (audit,) = audits()
        assert audit.rbaud_action == 'product.update'
        assert audit.rbaud_details == {'kind': ['booster', 'booster_box'],
                                       'kind_locked': [False, True]}
        assert product(100).rbpdt_updated_at == NOON

        refresh_products(DAY)
        row = product(100)
        assert (row.rbpdt_kind, row.rbpdt_kind_locked) == ('booster_box', True)

    def test_the_same_kind_still_locks_it(self, admin_client, catalog):
        item = payload(patch(admin_client, 100, {'kind': 'booster'}))['data']
        assert (item['kind'], item['kind_locked']) == ('booster', True)
        assert audits()[0].rbaud_details == {'kind_locked': [False, True]}

    def test_null_unlocks_and_recomputes_from_the_category(self, admin_client, catalog):
        patch(admin_client, 101, {'kind': 'other'})
        item = payload(patch(admin_client, 101, {'kind': None}))['data']
        assert (item['kind'], item['kind_locked']) == ('booster_box', False)
        assert audits()[1].rbaud_details == {'kind': ['other', 'booster_box'],
                                             'kind_locked': [True, False]}

    def test_null_recomputes_with_the_name_cm_g(self, admin_client, catalog):
        add_product(104, 'Jinx Trial Deck', kind='booster_box',
                    category='Riftbound Riftbound Box Sets', kind_locked=True)
        add_product(105, 'Bulk Runes Box', kind='booster_box',
                    category='Riftbound Riftbound Box Sets', kind_locked=True)
        db.session.commit()
        assert payload(patch(admin_client, 104, {'kind': None}))['data']['kind'] == (
            'champion_deck')
        assert payload(patch(admin_client, 105, {'kind': None}))['data']['kind'] == (
            'sealed_box_set')

    def test_null_on_a_not_used_category_recomputes_other(self, admin_client, catalog):
        """Taxonomy 2026-11-20: Cardmarket Sets / Sealed Products are not used; a row stored
        before the taxonomy that is unlocked gets `other` (the CHECK has no `unused`)."""
        add_product(106, 'Origins: Full Set', kind='booster', category='RB Set',
                    kind_locked=True)
        add_product(107, 'Sealed Lot', kind='booster', category='Riftbound Sealed Products',
                    kind_locked=True)
        db.session.commit()
        for product_id in (106, 107):
            item = payload(patch(admin_client, product_id, {'kind': None}))['data']
            assert (item['kind'], item['kind_locked']) == ('other', False)
            assert (product(product_id).rbpdt_kind, product(product_id).rbpdt_kind_locked) == (
                'other', False)

    def test_after_unlocking_the_refresh_follows_the_category_again(self, admin_client,
                                                                     catalog):
        patch(admin_client, 100, {'kind': 'booster_box'})
        patch(admin_client, 100, {'kind': None})
        db.session.query(RbcmProduct).filter_by(rbprd_date=DAY, rbprd_id_product=100).update(
            {'rbprd_category_name': 'Riftbound Sleeves'})
        db.session.commit()
        refresh_products(DAY)
        assert product(100).rbpdt_kind == 'accessory'

    @pytest.mark.parametrize('kind', ['pizza', 'box', 'case', 'bundle', 'starter', 'sleeves',
                                      'card', 'unused'])
    def test_an_unknown_kind_is_400_and_changes_nothing(self, admin_client, catalog, kind):
        """Taxonomy 2026-11-20: the old kinds and the virtual ones are refused too."""
        resp = patch(admin_client, 100, {'kind': kind})
        assert resp.status_code == 400
        body = payload(resp)
        assert body['code'] == 'validation_error'
        assert [d['field'] for d in body['details']] == ['kind']
        assert (product(100).rbpdt_kind, product(100).rbpdt_kind_locked) == ('booster', False)
        assert audits() == []


class TestPatchSet:
    def test_a_set_locks_it_and_the_refresh_respects_the_lock(self, admin_client, catalog):
        item = payload(patch(admin_client, 100, {'set_id': 'SFD'}))['data']
        assert (item['set_id'], item['set_locked']) == ('SFD', True)
        assert audits()[0].rbaud_details == {'set_id': ['OGN', 'SFD'],
                                             'set_locked': [False, True]}
        refresh_products(DAY)
        row = product(100)
        assert (row.rbpdt_id_set, row.rbpdt_set_locked) == ('SFD', True)

    def test_null_clears_and_locks_the_set(self, admin_client, catalog):
        item = payload(patch(admin_client, 100, {'set_id': None}))['data']
        assert (item['set_id'], item['set_locked']) == (None, True)
        refresh_products(DAY)
        row = product(100)
        assert (row.rbpdt_id_set, row.rbpdt_set_locked) == (None, True)

    def test_auto_unlocks_and_recomputes_from_the_expansion(self, admin_client, catalog):
        patch(admin_client, 100, {'set_id': 'SFD'})
        item = payload(patch(admin_client, 100, {'set_id': 'auto'}))['data']
        assert (item['set_id'], item['set_locked']) == ('OGN', False)
        assert audits()[1].rbaud_details == {'set_id': ['SFD', 'OGN'],
                                             'set_locked': [True, False]}

    def test_auto_with_an_unmapped_expansion_gives_no_set(self, admin_client, catalog):
        patch(admin_client, 102, {'set_id': 'OGN'})
        item = payload(patch(admin_client, 102, {'set_id': 'auto'}))['data']
        assert (item['set_id'], item['set_locked']) == (None, False)

    def test_auto_reads_the_latest_cardmarket_row(self, admin_client, catalog):
        cm(NEXT, 100, 'Origins Booster', 'Riftbound Booster', expansion=4)
        db.session.commit()
        patch(admin_client, 100, {'set_id': None})
        assert payload(patch(admin_client, 100, {'set_id': 'auto'}))['data']['set_id'] == 'ARC'

    def test_auto_without_cardmarket_rows_gives_no_set(self, admin_client, catalog):
        add_product(200, 'Manual Product', set_id='OGN', set_locked=True)
        db.session.commit()
        item = payload(patch(admin_client, 200, {'set_id': 'auto'}))['data']
        assert (item['set_id'], item['set_locked']) == (None, False)

    def test_after_auto_the_refresh_follows_the_expansion_again(self, admin_client, catalog):
        patch(admin_client, 100, {'set_id': 'SFD'})
        patch(admin_client, 100, {'set_id': 'auto'})
        db.session.get(RbcmExpansion, 1).rbexp_rbset_id = 'SFD'
        db.session.commit()
        refresh_products(DAY)
        assert product(100).rbpdt_id_set == 'SFD'

    @pytest.mark.parametrize('value', ['NOPE', 'sfd', '', 'AUTO', 7])
    def test_an_unknown_set_is_400_and_changes_nothing(self, admin_client, catalog, value):
        resp = patch(admin_client, 100, {'set_id': value, 'hidden': True})
        assert resp.status_code == 400, value
        body = payload(resp)
        assert body['code'] == 'validation_error'
        assert [d['field'] for d in body['details']] == ['set_id']
        row = product(100)
        assert (row.rbpdt_id_set, row.rbpdt_set_locked, row.rbpdt_hidden) == ('OGN', False,
                                                                              False)
        assert audits() == []


class TestPatchRules:
    def test_several_fields_make_one_audit_row(self, admin_client, catalog):
        resp = patch(admin_client, 100, {'hidden': True, 'kind': 'booster_box',
                                         'set_id': 'SFD'})
        assert resp.status_code == 200
        (audit,) = audits()
        assert audit.rbaud_details == {'hidden': [False, True],
                                       'kind': ['booster', 'booster_box'],
                                       'kind_locked': [False, True],
                                       'set_id': ['OGN', 'SFD'], 'set_locked': [False, True]}

    @pytest.mark.parametrize('body, field', [
        ({'hidden': None}, 'hidden'),
        ({'hidden': 'yes'}, 'hidden'),
        ({'hidden': 1}, 'hidden'),
        ({'name': 'Renamed'}, 'name'),
        ({'kind_locked': False}, 'kind_locked'),
    ])
    def test_bad_bodies_are_400(self, admin_client, catalog, body, field):
        resp = patch(admin_client, 100, body)
        assert resp.status_code == 400
        assert field in [d['field'] for d in payload(resp)['details']]
        assert audits() == []

    @pytest.mark.parametrize('product_id', [999, 900])
    def test_unknown_or_single_products_are_404(self, admin_client, catalog, product_id):
        resp = patch(admin_client, product_id, {'hidden': True})
        assert resp.status_code == 404
        assert payload(resp)['error'] == 'Not Found'
        assert audits() == []


# ---------------------------------------------------------------------------
# S4: POST /admin/products/<id>/image
# ---------------------------------------------------------------------------

class TestImage:
    """F14-d S4 adapted by F13-h S4, S5, S7: every upload is fitted inside 640 x 640 and stored
    as `<id>.webp` (`<id>-<n>.webp` when taken); the previous file stays for the Undo."""

    @pytest.mark.parametrize('data, filename', [
        (PNG, 'scan.png'), (JPG, 'photo.jpg'), (WEBP, 'art.webp'), (JPG, 'renamed.png'),
        (PNG, '../../etc/passwd'),
    ], ids=['png', 'jpeg', 'webp', 'renamed', 'path-name'])
    def test_the_file_is_id_dot_webp(self, admin_client, catalog, product_images_dir, client,
                                     data, filename):
        resp = upload(admin_client, 100, data, filename)
        assert resp.status_code == 200
        item = payload(resp)['data']
        stored = product_images_dir / '100.webp'
        assert item['id'] == 100
        assert item['image_src'] == '/riftbound/media/products/100.webp'
        assert (item['image'], item['previous'], item['has_image']) == ('100.webp', None, True)
        assert (item['width'], item['height'], item['bytes']) == (640, 320, stored.stat().st_size)
        assert sorted(p.name for p in product_images_dir.iterdir()) == ['100.webp']
        assert opened(stored.read_bytes()).format == 'WEBP'
        assert product(100).rbpdt_image == '100.webp'
        (audit,) = audits()
        assert (audit.rbaud_action, audit.rbaud_target_type, audit.rbaud_target_id,
                audit.rbaud_details) == ('product.image', 'product', '100',
                                         {'image': '100.webp', 'bytes_in': len(data),
                                          'bytes_out': stored.stat().st_size,
                                          'width': 640, 'height': 320})
        served = client.get(item['image_src'])
        assert served.status_code == 200
        assert served.data == stored.read_bytes()

    def test_the_list_shows_the_new_image(self, admin_client, catalog, product_images_dir):
        upload(admin_client, 100, PNG)
        items = payload(admin_client.get(f'{URL}?q=Origins Booster'))['data']['items']
        assert items[0]['image_src'] == '/riftbound/media/products/100.webp'
        assert items[0]['has_image'] is True
        # 103 names 103.png, which is not on disk: it is missing too (S2)
        assert ids(admin_client.get(f'{URL}?no_image=true')) == [103, 102, 101]

    def test_a_re_upload_gets_the_next_number_and_keeps_the_previous(self, admin_client,
                                                                     catalog,
                                                                     product_images_dir):
        upload(admin_client, 100, PNG)
        item = payload(upload(admin_client, 100, WEBP))['data']
        assert (item['image'], item['previous']) == ('100-2.webp', '100.webp')
        assert sorted(p.name for p in product_images_dir.iterdir()) == ['100-2.webp',
                                                                        '100.webp']
        assert product(100).rbpdt_image == '100-2.webp'

    def test_the_next_upload_deletes_the_older_files(self, admin_client, catalog,
                                                     product_images_dir):
        product_images_dir.mkdir()
        (product_images_dir / '100.png').write_bytes(PNG)
        product(100).rbpdt_image = '100.png'
        db.session.commit()
        upload(admin_client, 100, PNG)
        assert sorted(p.name for p in product_images_dir.iterdir()) == ['100.png', '100.webp']
        upload(admin_client, 100, PNG)
        assert sorted(p.name for p in product_images_dir.iterdir()) == ['100-2.webp',
                                                                        '100.webp']

    def test_an_image_not_named_after_the_product_is_kept(self, admin_client, catalog,
                                                          product_images_dir):
        product_images_dir.mkdir()
        (product_images_dir / 'shared.png').write_bytes(PNG)
        product(100).rbpdt_image = 'shared.png'
        db.session.commit()
        upload(admin_client, 100, JPG)
        upload(admin_client, 100, JPG)
        assert sorted(p.name for p in product_images_dir.iterdir()) == [
            '100-2.webp', '100.webp', 'shared.png']

    def test_an_unsafe_stored_name_is_ignored(self, admin_client, catalog, product_images_dir,
                                              tmp_path):
        (tmp_path / 'outside.png').write_bytes(b'keep me')
        product(100).rbpdt_image = '../outside.png'
        db.session.commit()
        assert upload(admin_client, 100, PNG).status_code == 200
        assert upload(admin_client, 100, PNG).status_code == 200
        assert (tmp_path / 'outside.png').read_bytes() == b'keep me'

    def test_a_120_px_image_is_accepted(self, admin_client, catalog, product_images_dir):
        assert upload(admin_client, 100, png((120, 120))).status_code == 200

    @pytest.mark.parametrize('data, code, params', [
        (png((119, 400)), 'too_small', {'min': 120}),
        (None, 'out_of_range', {'max': MAX_BYTES}),
    ], ids=['tiny', '12mb'])
    def test_too_small_or_too_large_is_400_and_writes_nothing(self, admin_client, catalog,
                                                              product_images_dir, data, code,
                                                              params):
        data = data if data is not None else noise_png(12 * 1024 * 1024)
        resp = upload(admin_client, 100, data)
        assert resp.status_code == 400
        body = payload(resp)
        assert body['code'] == 'validation_error'
        assert any(d['field'] == 'file' and d['code'] == code and d['params'] == params
                   for d in body['details'])
        self._nothing_written(product_images_dir)

    @pytest.mark.parametrize('data', [b'GIF89a' + b'x' * 100, b'<svg></svg>', b'',
                                      b'RIFF\x00\x00\x00\x00AVI LIST',
                                      b'\x89PNG\r\n\x1a\n' + b'product-image-bytes' * 50],
                             ids=['gif', 'svg', 'empty', 'avi', 'fake-png'])
    def test_bad_or_damaged_files_are_400_and_write_nothing(self, admin_client, catalog,
                                                           product_images_dir, data):
        resp = upload(admin_client, 100, data, 'fake.png')
        assert resp.status_code == 400
        assert any(d['field'] == 'file' and d['code'] == 'invalid_format'
                   for d in payload(resp)['details'])
        self._nothing_written(product_images_dir)

    def test_a_missing_file_is_400(self, admin_client, catalog, product_images_dir):
        resp = admin_client.post(f'{URL}/100/image', data={},
                                 content_type='multipart/form-data')
        assert resp.status_code == 400
        assert any(d['field'] == 'file' and d['code'] == 'required'
                   for d in payload(resp)['details'])
        self._nothing_written(product_images_dir)

    @pytest.mark.parametrize('product_id', [999, 900])
    def test_unknown_or_single_products_are_404(self, admin_client, catalog,
                                                product_images_dir, product_id):
        assert upload(admin_client, product_id, PNG).status_code == 404
        assert not product_images_dir.exists()

    def _nothing_written(self, root):
        assert not root.exists()
        assert product(100).rbpdt_image is None
        assert audits() == []


# ---------------------------------------------------------------------------
# Authorization (AC4)
# ---------------------------------------------------------------------------

class TestAuthz:
    ENDPOINTS = {'api_admin.list_products': ('GET', '/riftbound/api/v1/admin/products'),
                 'api_admin.update_product': ('PATCH',
                                              '/riftbound/api/v1/admin/products/<int:product_id>'),
                 'api_admin.upload_product_image': (
                     'POST', '/riftbound/api/v1/admin/products/<int:product_id>/image')}

    def test_the_rules_are_admin_only(self, app):
        found = {r.endpoint: r for r in app.url_map.iter_rules()
                 if r.endpoint in self.ENDPOINTS}
        assert set(found) == set(self.ENDPOINTS)
        for endpoint, (method, rule) in self.ENDPOINTS.items():
            assert found[endpoint].rule == rule
            assert method in found[endpoint].methods
            assert classify(found[endpoint]) == 'A'

    def test_a_plain_user_gets_403_and_nothing_changes(self, authenticated_client, catalog,
                                                       product_images_dir):
        assert authenticated_client.get(URL).status_code == 403
        assert patch(authenticated_client, 100, {'hidden': True}).status_code == 403
        assert upload(authenticated_client, 100, PNG).status_code == 403
        assert product(100).rbpdt_hidden is False
        assert not product_images_dir.exists()
        assert audits() == []

    def test_anonymous_gets_401(self, client, catalog, product_images_dir):
        assert client.get(URL).status_code == 401
        assert patch(client, 100, {'hidden': True}).status_code == 401
        assert upload(client, 100, PNG).status_code == 401
        assert product(100).rbpdt_hidden is False
        assert not product_images_dir.exists()
