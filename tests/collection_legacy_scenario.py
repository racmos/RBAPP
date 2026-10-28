"""A fixed sequence of Jinja collection requests (F3-a S6).

Used by `tests/test_collection_legacy_routes.py`. The CSV it returns was first produced by the code
before F3-a (`tests/fixtures/collection_export_legacy.csv`), so the test proves the export is
byte-identical: only the quantity source changed."""
from app import db
from app.models import RbCard, RbCollection, RbSet

USER = 'testuser'


def seed_catalog():
    db.session.add(RbSet(rbset_id='OGN', rbset_name='Origins', rbset_ncard=3))
    db.session.add_all([
        RbCard(rbcar_rbset_id='OGN', rbcar_id='1', rbcar_name='Ember Wisp', rbcar_rarity='Common'),
        RbCard(rbcar_rbset_id='OGN', rbcar_id='2', rbcar_name='Fury Rune', rbcar_rarity='Common'),
        RbCard(rbcar_rbset_id='OGN', rbcar_id='3', rbcar_name='Ayla', rbcar_rarity='Rare'),
    ])
    db.session.commit()


def add(client, card, qty, foil='N', selling='N', price=None, condition=None, language=None):
    body = {'rbcol_rbset_id': 'OGN', 'rbcol_rbcar_id': card, 'rbcol_foil': foil,
            'rbcol_quantity': qty, 'rbcol_selling': selling, 'rbcol_sell_price': price,
            'rbcol_condition': condition, 'rbcol_language': language}
    response = client.post('/riftbound/collection/add', json=body)
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()['rbcol_id']


def post(client, path, **body):
    response = client.post(f'/riftbound/collection/{path}', json=body)
    assert response.status_code == 200, response.get_data(as_text=True)
    return response


def export(client):
    response = client.post('/riftbound/collection/export_csv',
                           json={'rbset_id': 'OGN', 'rarity': 'Common'})
    assert response.status_code == 200
    return response.get_data(as_text=True)


def run(client, check=lambda: None):
    """Play the sequence; `check()` runs after every write. Returns the exported CSV text."""
    seed_catalog()
    a = add(client, '1', 4, selling='Y', price=2.5, language='English')
    check()
    assert add(client, '1', 2, selling='Y', price=2.5, language='English') == a  # merge
    check()
    b = add(client, '1', 2, foil='S', selling='N')
    check()
    c = add(client, '2', 3, selling='Y', price=1.5)
    check()
    post(client, 'update_playset', rbcol_id=a, rbcol_playset=3)
    check()
    post(client, 'update_playset', rbcol_id=b, rbcol_playset=2)
    check()
    d = add(client, '2', 5, foil='S', selling='Y')
    check()
    post(client, 'bulk_apply', ids=[c, d], playset=3)
    check()
    post(client, 'import_csv', csv_data='OGN;2;N;7\nOGN;1;N;9')
    check()
    post(client, 'update_quantity', rbcol_id=a, quantity=5)
    check()
    post(client, 'update_selling', rbcol_id=d, rbcol_selling='N')
    check()
    post(client, 'bulk_apply', ids=[a], quantity=4, selling='Y')
    check()
    return export(client)


def rows():
    return RbCollection.query.order_by(RbCollection.rbcol_id).all()
