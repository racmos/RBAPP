"""F3-a S6: the Jinja collection keeps `rbcol_sell_qty` coherent after every write, and the CSV
export still produces the bytes it produced before (only the quantity source changed)."""
from pathlib import Path

import pytest

from app import db
from app.models import RbCard, RbCollection, RbSet
from app.services.collection_rules import legacy_sell_qty
from tests.collection_legacy_scenario import add, post, rows, run, seed_catalog
from tests.conftest import login_as

FIXTURE = Path(__file__).parent / 'fixtures' / 'collection_export_legacy.csv'


@pytest.fixture
def client(app, make_user):
    make_user('testuser')
    return login_as(app.test_client(), 'testuser')


def assert_coherent():
    db.session.expire_all()
    for col in rows():
        expected = legacy_sell_qty(col.rbcol_quantity, col.rbcol_playset, col.rbcol_selling)
        assert col.rbcol_sell_qty == expected, (col.rbcol_id, col.rbcol_quantity,
                                                col.rbcol_playset, col.rbcol_selling)
        assert 0 <= col.rbcol_sell_qty <= col.rbcol_quantity


def test_every_write_keeps_sell_qty_coherent(client):
    run(client, check=assert_coherent)


def test_add_records_the_copies_for_sale(client):
    seed_catalog()
    first = add(client, '1', 4, selling='Y')
    second = add(client, '2', 4, selling='N')
    db.session.expire_all()
    assert db.session.get(RbCollection, first).rbcol_sell_qty == 4
    assert db.session.get(RbCollection, second).rbcol_sell_qty == 0


def test_a_merge_adds_the_new_copies_to_the_sale(client):
    seed_catalog()
    row = add(client, '1', 4, selling='Y')
    add(client, '1', 3, selling='Y')
    db.session.expire_all()
    col = db.session.get(RbCollection, row)
    assert (col.rbcol_quantity, col.rbcol_sell_qty) == (7, 7)


def test_lowering_the_quantity_lowers_the_copies_for_sale(client):
    seed_catalog()
    row = add(client, '1', 6, selling='Y')
    post(client, 'update_quantity', rbcol_id=row, quantity=2)
    db.session.expire_all()
    assert db.session.get(RbCollection, row).rbcol_sell_qty == 2


def test_update_selling_toggles_the_whole_row_without_a_playset(client):
    seed_catalog()
    row = add(client, '1', 3)
    post(client, 'update_selling', rbcol_id=row, rbcol_selling='Y')
    db.session.expire_all()
    assert db.session.get(RbCollection, row).rbcol_sell_qty == 3
    post(client, 'update_selling', rbcol_id=row, rbcol_selling='N')
    db.session.expire_all()
    assert db.session.get(RbCollection, row).rbcol_sell_qty == 0


def test_the_playset_decides_what_is_for_sale(client):
    seed_catalog()
    row = add(client, '1', 5)
    post(client, 'update_playset', rbcol_id=row, rbcol_playset=3)
    db.session.expire_all()
    col = db.session.get(RbCollection, row)
    assert (col.rbcol_selling, col.rbcol_sell_qty) == ('Y', 2)


def test_import_overwrites_the_quantity_and_the_copies_for_sale(client):
    seed_catalog()
    row = add(client, '1', 5, selling='Y')
    post(client, 'import_csv', csv_data='OGN;1;N;2\nOGN;2;N;6')
    db.session.expire_all()
    imported = RbCollection.query.filter_by(rbcol_rbcar_id='2').one()
    assert db.session.get(RbCollection, row).rbcol_sell_qty == 2
    assert (imported.rbcol_quantity, imported.rbcol_sell_qty) == (6, 0)


def test_export_is_byte_identical_to_the_one_before_f3a(client):
    text = run(client)
    with FIXTURE.open(encoding='utf-8', newline='') as handle:
        assert text == handle.read()


def test_export_quantity_comes_from_the_copies_to_sell(client):
    seed_catalog()
    row = add(client, '1', 5, selling='Y')
    db.session.expire_all()
    db.session.get(RbCollection, row).rbcol_sell_qty = 2   # as F3-c will write it
    db.session.commit()
    text = client.post('/riftbound/collection/export_csv',
                       json={'rbset_id': 'OGN', 'rarity': 'Common'}).get_data(as_text=True)
    assert '"Ember Wisp","","2","0.00"' in text


def test_export_skips_rows_with_nothing_to_sell(client):
    seed_catalog()
    row = add(client, '1', 5, selling='Y')
    db.session.expire_all()
    db.session.get(RbCollection, row).rbcol_sell_qty = 0
    db.session.commit()
    response = client.post('/riftbound/collection/export_csv',
                           json={'rbset_id': 'OGN', 'rarity': 'Common'})
    assert response.headers['X-Rows-Exported'] == '0'
