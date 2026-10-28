"""F14-a S6 (AC5): the Jinja product endpoints (`price_bp`, admin only) keep working once
`rbproducts` is keyed by the product id alone."""
import sqlalchemy as sa

from app import db
from app.models import RbProducts

BASE = '/riftbound/price'


def products():
    db.session.expire_all()
    return [(p.rbpdt_id_set, p.rbpdt_id_product, p.rbpdt_name, p.rbpdt_description,
             p.rbpdt_type) for p in db.session.execute(
        sa.select(RbProducts).order_by(RbProducts.rbpdt_id_product)).scalars()]


def upsert(client, **body):
    return client.post(f'{BASE}/cardmarket-upsert-product', json=body)


def detail(client, set_id, product_id):
    return client.get(f'{BASE}/cardmarket-product-detail',
                      query_string={'rbpdt_id_set': set_id, 'rbpdt_id_product': product_id})


PRODUCT = {'rbpdt_id_set': 'OGN', 'rbpdt_id_product': 10, 'rbpdt_name': 'Origins Booster',
           'rbpdt_description': 'desc', 'rbpdt_type': 'nonsingle',
           'rbpdt_image_url': 'http://img/x.png', 'rbpdt_image': 'x.png'}


def test_upsert_creates_then_updates(admin_client):
    response = upsert(admin_client, **PRODUCT)
    assert (response.status_code, response.get_json()) == (200, {
        'success': True, 'status': 'created', 'rbpdt_id_set': 'OGN', 'rbpdt_id_product': 10,
        'rbpdt_name': 'Origins Booster'})
    response = upsert(admin_client, rbpdt_id_set='OGN', rbpdt_id_product='10',
                      rbpdt_name='Origins Booster Pack', rbpdt_description='')
    assert response.get_json() == {
        'success': True, 'status': 'updated', 'rbpdt_id_set': 'OGN', 'rbpdt_id_product': 10,
        'rbpdt_name': 'Origins Booster Pack'}
    assert products() == [('OGN', 10, 'Origins Booster Pack', None, 'nonsingle')]


def test_upsert_with_another_set_moves_the_one_product(admin_client):
    upsert(admin_client, **PRODUCT)
    response = upsert(admin_client, rbpdt_id_set='SFD', rbpdt_id_product=10,
                      rbpdt_name='Origins Booster')
    assert response.get_json()['status'] == 'updated'
    assert products() == [('SFD', 10, 'Origins Booster', 'desc', 'nonsingle')]


def test_upsert_rejects_bad_input_and_stores_nothing(admin_client):
    response = upsert(admin_client, rbpdt_id_set='OGN', rbpdt_id_product='x', rbpdt_name='A')
    assert (response.status_code, response.get_json()) == (
        400, {'success': False, 'message': 'rbpdt_id_product inválido'})
    for body in ({'rbpdt_id_product': 1, 'rbpdt_name': 'A'},
                 {'rbpdt_id_set': 'OGN', 'rbpdt_id_product': 1, 'rbpdt_name': ' '}):
        response = upsert(admin_client, **body)
        assert (response.status_code, response.get_json()) == (
            400, {'success': False, 'message': 'rbpdt_id_set y rbpdt_name son obligatorios'})
    assert products() == []


def test_detail_finds_the_product_of_that_set(admin_client):
    upsert(admin_client, **PRODUCT)
    response = detail(admin_client, 'OGN', 10)
    assert (response.status_code, response.get_json()) == (200, {
        'success': True, 'exists': True, 'product': PRODUCT})
    for set_id, product_id in (('SFD', 10), ('OGN', 11)):
        assert detail(admin_client, set_id, product_id).get_json() == {
            'success': True, 'exists': False, 'product': None}


def test_detail_rejects_bad_input(admin_client):
    response = detail(admin_client, 'OGN', 'x')
    assert (response.status_code, response.get_json()) == (
        400, {'success': False, 'message': 'rbpdt_id_product inválido'})
    response = detail(admin_client, '', 10)
    assert (response.status_code, response.get_json()) == (
        400, {'success': False, 'message': 'rbpdt_id_set requerido'})


def test_search_by_name(admin_client):
    upsert(admin_client, **PRODUCT)
    upsert(admin_client, rbpdt_id_set='SFD', rbpdt_id_product=20, rbpdt_name='Spirit Booster')
    upsert(admin_client, rbpdt_id_set='SFD', rbpdt_id_product=21, rbpdt_name='Playmat')
    response = admin_client.get(f'{BASE}/cardmarket-product-search', query_string={'q': 'boos'})
    found = response.get_json()
    assert found['success'] is True
    assert [(p['rbpdt_id_set'], p['rbpdt_id_product'], p['rbpdt_name'])
            for p in found['products']] == [('OGN', 10, 'Origins Booster'),
                                            ('SFD', 20, 'Spirit Booster')]
    assert set(found['products'][0]) == set(PRODUCT)
    short = admin_client.get(f'{BASE}/cardmarket-product-search', query_string={'q': 'bo'})
    assert short.get_json() == {'success': True, 'products': []}


def test_a_product_without_a_set_is_found_by_search(admin_client):
    db.session.add(RbProducts(rbpdt_id_product=30, rbpdt_name='Unmapped Booster',
                              rbpdt_type='nonsingle'))
    db.session.commit()
    response = admin_client.get(f'{BASE}/cardmarket-product-search', query_string={'q': 'unmap'})
    assert [(p['rbpdt_id_set'], p['rbpdt_id_product'])
            for p in response.get_json()['products']] == [(None, 30)]


def test_plain_users_are_refused(authenticated_client):
    assert upsert(authenticated_client, **PRODUCT).status_code == 403
    assert detail(authenticated_client, 'OGN', 10).status_code == 403
    assert authenticated_client.get(f'{BASE}/cardmarket-product-search',
                                    query_string={'q': 'boos'}).status_code == 403
    assert products() == []
