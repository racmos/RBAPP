"""F13-h S2, S7, S9 (AC1, AC2, AC6): images missing on disk, the summary, Undo and finalize.

Files live only in the `card_images_dir` / `product_images_dir` fixtures.
"""
import io
import os

import pytest
from sqlalchemy import event

from app import db
from app.models import RbProducts
from app.models.audit import RbAdminAudit
from app.models.card import RbCard
from app.models.set import RbSet
from app.services import card_images, product_images
from tests.image_helpers import png
from tests.product_helpers import add_product
from tests.test_authz_matrix import classify

ADMIN = '/riftbound/api/v1/admin'
CARDS = f'{ADMIN}/cards'
PRODUCTS = f'{ADMIN}/products'


@pytest.fixture
def catalog(app, card_images_dir, product_images_dir):
    """OGN-1 with its file, OGN-2 empty, OGN-3 naming a file that is gone, SFD-1 with its file;
    products 100 (file), 101 (no image), 102 (file gone)."""
    db.session.add_all([RbSet(rbset_id='OGN', rbset_name='Origen', rbset_ncard=3),
                        RbSet(rbset_id='SFD', rbset_name='Segundo', rbset_ncard=1)])
    db.session.add_all([
        RbCard(rbcar_rbset_id='OGN', rbcar_id='1', rbcar_name='Alpha', image='ogn_1.png'),
        RbCard(rbcar_rbset_id='OGN', rbcar_id='2', rbcar_name='Beta', image=None),
        RbCard(rbcar_rbset_id='OGN', rbcar_id='3', rbcar_name='Gamma', image='ogn_3.png'),
        RbCard(rbcar_rbset_id='SFD', rbcar_id='1', rbcar_name='Delta', image='sfd_1.png'),
    ])
    add_product(100, 'Alpha Booster', image='100.png')
    add_product(101, 'Beta Booster')
    add_product(102, 'Gamma Booster', image='102.png')
    db.session.commit()
    for folder, name in (('ogn', 'ogn_1.png'), ('sfd', 'sfd_1.png')):
        (card_images_dir / folder).mkdir(parents=True, exist_ok=True)
        (card_images_dir / folder / name).write_bytes(png())
    product_images_dir.mkdir()
    (product_images_dir / '100.png').write_bytes(png())
    return app


def payload(resp):
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()['data']


def keys(resp):
    return [item['key'] for item in payload(resp)['items']]


def product_ids(resp):
    return [item['id'] for item in payload(resp)['items']]


def audits():
    return RbAdminAudit.query.order_by(RbAdminAudit.rbaud_id).all()


class TestCardList:
    """S2 / AC1."""

    @pytest.mark.parametrize('query, expected', [
        ('', ['OGN-1', 'OGN-2', 'OGN-3', 'SFD-1']),
        ('image=any', ['OGN-1', 'OGN-2', 'OGN-3', 'SFD-1']),
        ('image=missing', ['OGN-2', 'OGN-3']),
        ('image=empty', ['OGN-2']),                 # the switch "Include files missing on disk" off
        ('image=present', ['OGN-1', 'SFD-1']),
        ('missing_image=true', ['OGN-2', 'OGN-3']),
        ('missing_image=false', ['OGN-1', 'OGN-2', 'OGN-3', 'SFD-1']),
        ('image=missing&set=OGN&q=gam', ['OGN-3']),
    ])
    def test_the_image_filter(self, admin_client, catalog, query, expected):
        assert keys(admin_client.get(f'{CARDS}?{query}')) == expected

    def test_the_total_follows_the_filter(self, admin_client, catalog):
        assert payload(admin_client.get(f'{CARDS}?image=missing'))['meta']['total'] == 2

    def test_every_row_says_whether_the_file_exists(self, admin_client, catalog):
        rows = payload(admin_client.get(CARDS))['items']
        assert {row['key']: row['has_image'] for row in rows} == {
            'OGN-1': True, 'OGN-2': False, 'OGN-3': False, 'SFD-1': True}

    def test_a_symlink_out_of_the_root_does_not_count(self, admin_client, catalog,
                                                      card_images_dir, tmp_path):
        (tmp_path / 'secret.png').write_bytes(png())
        (card_images_dir / 'ogn' / 'ogn_3.png').symlink_to(tmp_path / 'secret.png')
        assert keys(admin_client.get(f'{CARDS}?image=missing')) == ['OGN-2', 'OGN-3']

    @pytest.mark.parametrize('query', ['image=none', 'image=MISSING', 'image=true'])
    def test_a_bad_value_is_400(self, admin_client, catalog, query):
        resp = admin_client.get(f'{CARDS}?{query}')
        assert resp.status_code == 400
        assert resp.get_json()['code'] == 'validation_error'

    def test_one_directory_scan_per_folder_and_bounded_statements(self, admin_client, catalog,
                                                                  monkeypatch):
        for n in range(4, 120):
            db.session.add(RbCard(rbcar_rbset_id='OGN', rbcar_id=str(n), rbcar_name=f'C{n}',
                                  image=f'ogn_{n}.png'))
        db.session.commit()
        scanned, statements = [], []
        real = os.scandir

        def counting(path):
            scanned.append(os.path.basename(path))
            return real(path)
        monkeypatch.setattr(card_images.os, 'scandir', counting)

        def before(conn, cursor, statement, params, context, executemany):
            statements.append(statement)
        event.listen(db.engine, 'before_cursor_execute', before)
        try:
            payload(admin_client.get(f'{CARDS}?image=missing&per_page=200'))
        finally:
            event.remove(db.engine, 'before_cursor_execute', before)
        assert sorted(scanned) == ['ogn', 'sfd']
        assert len([s for s in statements if s.lstrip().upper().startswith('SELECT')]) <= 3


class TestProductList:
    @pytest.mark.parametrize('query, expected', [
        ('', [100, 101, 102]),
        ('image=missing', [101, 102]),
        ('image=empty', [101]),
        ('image=present', [100]),
        ('no_image=true', [101, 102]),
    ])
    def test_the_image_filter(self, admin_client, catalog, query, expected):
        assert product_ids(admin_client.get(f'{PRODUCTS}?{query}')) == expected

    def test_every_row_says_whether_the_file_exists(self, admin_client, catalog):
        rows = payload(admin_client.get(PRODUCTS))['items']
        assert {row['id']: (row['image'], row['has_image']) for row in rows} == {
            100: ('100.png', True), 101: (None, False), 102: ('102.png', False)}

    def test_one_directory_scan(self, admin_client, catalog, monkeypatch):
        scanned = []
        real = os.scandir

        def counting(path):
            scanned.append(path)
            return real(path)
        monkeypatch.setattr(product_images.os, 'scandir', counting)
        payload(admin_client.get(f'{PRODUCTS}?image=missing'))
        assert len(scanned) == 1


class TestSummary:
    def test_counters_of_both_tabs(self, admin_client, catalog):
        assert payload(admin_client.get(f'{ADMIN}/images/summary')) == {
            'cards': {'missing': 2, 'total': 4}, 'products': {'missing': 2, 'total': 3}}

    def test_singles_are_not_products(self, admin_client, catalog):
        add_product(900, 'A single', type_='single')
        db.session.commit()
        assert payload(admin_client.get(f'{ADMIN}/images/summary'))['products'] == {
            'missing': 2, 'total': 3}

    def test_no_directory_at_all(self, admin_client, app):
        assert payload(admin_client.get(f'{ADMIN}/images/summary')) == {
            'cards': {'missing': 0, 'total': 0}, 'products': {'missing': 0, 'total': 0}}


def card(set_id, card_id):
    db.session.expire_all()
    return db.session.get(RbCard, (set_id, card_id))


def product(product_id):
    db.session.expire_all()
    return db.session.get(RbProducts, product_id)


class TestFinalize:
    """S7: the previous file is deleted when the Undo toast expires, only when no row uses it
    and it is inside the images root."""

    URL = f'{ADMIN}/images/finalize'

    def test_an_unused_card_file_is_deleted(self, admin_client, catalog, card_images_dir):
        (card_images_dir / 'ogn' / 'ogn_9.png').write_bytes(png())
        body = payload(admin_client.post(self.URL, json={'type': 'card', 'set_id': 'OGN',
                                                         'image': 'ogn_9.png'}))
        assert body == {'deleted': True}
        assert not (card_images_dir / 'ogn' / 'ogn_9.png').exists()

    def test_a_file_a_card_uses_is_kept(self, admin_client, catalog, card_images_dir):
        body = payload(admin_client.post(self.URL, json={'type': 'card', 'set_id': 'OGN',
                                                         'image': 'ogn_1.png'}))
        assert body == {'deleted': False}
        assert (card_images_dir / 'ogn' / 'ogn_1.png').exists()

    def test_a_missing_file_is_not_an_error(self, admin_client, catalog):
        assert payload(admin_client.post(self.URL, json={'type': 'card', 'set_id': 'OGN',
                                                         'image': 'ogn_77.png'})) == {
            'deleted': False}

    def test_a_product_file(self, admin_client, catalog, product_images_dir):
        (product_images_dir / '101.png').write_bytes(png())
        assert payload(admin_client.post(self.URL, json={'type': 'product',
                                                         'image': '101.png'})) == {
            'deleted': True}
        assert payload(admin_client.post(self.URL, json={'type': 'product',
                                                         'image': '100.png'})) == {
            'deleted': False}
        assert sorted(p.name for p in product_images_dir.iterdir()) == ['100.png']

    def test_a_symlink_is_never_followed_out_of_the_root(self, admin_client, catalog,
                                                         card_images_dir, tmp_path):
        (tmp_path / 'outside.png').write_bytes(b'keep me')
        (card_images_dir / 'ogn' / 'ogn_8.png').symlink_to(tmp_path / 'outside.png')
        assert payload(admin_client.post(self.URL, json={'type': 'card', 'set_id': 'OGN',
                                                         'image': 'ogn_8.png'})) == {
            'deleted': False}
        assert (tmp_path / 'outside.png').read_bytes() == b'keep me'

    @pytest.mark.parametrize('body', [
        {'type': 'card', 'image': '../outside.png'},
        {'type': 'card', 'image': 'a/b.png'},
        {'type': 'product', 'image': '..'},
        {'type': 'product', 'image': ''},
        {'type': 'deck', 'image': 'x.png'},
        {'type': 'card', 'image': 'ogn_1.png', 'extra': 1},
    ])
    def test_unsafe_or_bad_bodies_are_400(self, admin_client, catalog, body, tmp_path):
        resp = admin_client.post(self.URL, json=body)
        assert resp.status_code == 400
        assert resp.get_json()['code'] == 'validation_error'


class TestUndo:
    URL = f'{ADMIN}/images/undo'

    def test_a_card_gets_its_previous_image_back(self, admin_client, catalog, card_images_dir):
        uploaded = payload(admin_client.post(f'{CARDS}/OGN/1/image',
                                             data={'file': (io.BytesIO(png()),
                                                            'x.png')},
                                             content_type='multipart/form-data'))
        assert uploaded['image'] == 'ogn_1.webp'
        body = payload(admin_client.post(self.URL, json={
            'type': 'card', 'set_id': 'OGN', 'card_id': '1', 'image': 'ogn_1.webp',
            'previous': 'ogn_1.png'}))
        assert (body['key'], body['image'], body['has_image']) == ('OGN-1', 'ogn_1.png', True)
        assert card('OGN', '1').image == 'ogn_1.png'
        assert sorted(p.name for p in (card_images_dir / 'ogn').iterdir()) == ['ogn_1.png']
        undo = audits()[-1]
        assert (undo.rbaud_action, undo.rbaud_target_id, undo.rbaud_details) == (
            'card.image_undo', 'OGN-1', {'image': 'ogn_1.png', 'replaced': 'ogn_1.webp'})

    def test_a_card_without_an_image_before_gets_none(self, admin_client, catalog,
                                                      card_images_dir):
        card('OGN', '2').image = 'ogn_2.webp'
        db.session.commit()
        (card_images_dir / 'ogn' / 'ogn_2.webp').write_bytes(png())
        body = payload(admin_client.post(self.URL, json={
            'type': 'card', 'set_id': 'OGN', 'card_id': '2', 'image': 'ogn_2.webp',
            'previous': None}))
        assert (body['image'], body['has_image']) == (None, False)
        assert not (card_images_dir / 'ogn' / 'ogn_2.webp').exists()

    def test_a_product(self, admin_client, catalog, product_images_dir):
        product(100).rbpdt_image = '100.webp'
        db.session.commit()
        (product_images_dir / '100.webp').write_bytes(png())
        body = payload(admin_client.post(self.URL, json={
            'type': 'product', 'product_id': 100, 'image': '100.webp', 'previous': '100.png'}))
        assert (body['id'], body['image'], body['has_image']) == (100, '100.png', True)
        assert sorted(p.name for p in product_images_dir.iterdir()) == ['100.png']
        assert audits()[-1].rbaud_action == 'product.image_undo'

    def test_a_changed_image_is_409_and_nothing_changes(self, admin_client, catalog,
                                                        card_images_dir):
        resp = admin_client.post(self.URL, json={
            'type': 'card', 'set_id': 'OGN', 'card_id': '1', 'image': 'ogn_1.webp',
            'previous': None})
        assert resp.status_code == 409
        assert card('OGN', '1').image == 'ogn_1.png'
        assert audits() == []

    @pytest.mark.parametrize('body, status', [
        ({'type': 'card', 'set_id': 'OGN', 'card_id': '99', 'image': 'x.webp',
          'previous': None}, 404),
        ({'type': 'product', 'product_id': 999, 'image': 'x.webp', 'previous': None}, 404),
        ({'type': 'card', 'set_id': 'OGN', 'image': 'x.webp', 'previous': None}, 400),
        ({'type': 'product', 'image': 'x.webp', 'previous': None}, 400),
        ({'type': 'card', 'set_id': 'OGN', 'card_id': '1', 'image': 'ogn_1.png',
          'previous': '../x.png'}, 400),
    ])
    def test_bad_targets(self, admin_client, catalog, body, status):
        assert admin_client.post(self.URL, json=body).status_code == status
        assert audits() == []


class TestAuthz:
    ENDPOINTS = {
        'api_admin.images_summary': ('GET', f'{ADMIN}/images/summary'),
        'api_admin.images_finalize': ('POST', f'{ADMIN}/images/finalize'),
        'api_admin.images_undo': ('POST', f'{ADMIN}/images/undo'),
    }

    def test_the_rules_are_admin_only(self, app):
        found = {r.endpoint: r for r in app.url_map.iter_rules() if r.endpoint in self.ENDPOINTS}
        assert set(found) == set(self.ENDPOINTS)
        for endpoint, (method, rule) in self.ENDPOINTS.items():
            assert found[endpoint].rule == rule
            assert method in found[endpoint].methods
            assert classify(found[endpoint]) == 'A'

    def test_plain_users_are_refused(self, authenticated_client, catalog, card_images_dir):
        (card_images_dir / 'ogn' / 'ogn_9.png').write_bytes(png())
        body = {'type': 'card', 'set_id': 'OGN', 'image': 'ogn_9.png'}
        assert authenticated_client.get(f'{ADMIN}/images/summary').status_code == 403
        assert authenticated_client.post(f'{ADMIN}/images/finalize', json=body).status_code \
            == 403
        assert (card_images_dir / 'ogn' / 'ogn_9.png').exists()

    def test_csrf_is_required(self, csrf_app, admin_client, catalog, card_images_dir):
        (card_images_dir / 'ogn' / 'ogn_9.png').write_bytes(png())
        resp = admin_client.post(f'{ADMIN}/images/finalize',
                                 json={'type': 'card', 'set_id': 'OGN', 'image': 'ogn_9.png'})
        assert resp.status_code == 400
        assert resp.get_json()['code'] == 'csrf_invalid'
        assert (card_images_dir / 'ogn' / 'ogn_9.png').exists()
