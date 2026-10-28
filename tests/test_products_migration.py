"""F14-a S2, S5 (AC1): migrations `0019_products_catalog` and `0020_jobs_products_refresh`:
round trips, drift, the key change keeps existing rows, the downgrade refusals, the kind CHECK
(SQLite; `migrations-pg` runs them on PostgreSQL 18)."""
import pytest
from sqlalchemy.exc import IntegrityError

from tests.migration_helpers import downgrade, drift, inspector, rows, run, upgrade

BEFORE = '0018_import_previews'
CATALOG = '0019_products_catalog'
KIND = '0020_jobs_products_refresh'
OLD_ROW = ("INSERT INTO riftbound.rbproducts (rbpdt_id_set, rbpdt_id_product, rbpdt_name, "
           "rbpdt_description, rbpdt_type, rbpdt_image_url, rbpdt_image) "
           "VALUES (:set, :id, :name, 'desc', 'nonsingle', 'http://x/i.png', 'i.png')")
NEW_ROW = ("INSERT INTO riftbound.rbproducts (rbpdt_id_set, rbpdt_id_product, rbpdt_name, "
           "rbpdt_kind) VALUES (:set, :id, :name, :kind)")
JOB = ("INSERT INTO riftbound.rbjobs (rbjob_kind, rbjob_status, rbjob_requested_at) "
       "VALUES (:kind, :status, '2030-01-01 12:00:00')")
NEW_COLUMNS = {'rbpdt_category', 'rbpdt_kind', 'rbpdt_kind_locked', 'rbpdt_set_locked',
               'rbpdt_hidden', 'rbpdt_listed', 'rbpdt_updated_at'}


def columns():
    return {c['name']: c for c in inspector().get_columns('rbproducts', schema='riftbound')}


def pk():
    return inspector().get_pk_constraint('rbproducts', schema='riftbound')


def test_the_key_is_the_product_id_and_the_set_is_nullable(migration_app):
    upgrade(CATALOG)
    assert pk() == {'name': 'rbproducts_pkey', 'constrained_columns': ['rbpdt_id_product']}
    cols = columns()
    assert NEW_COLUMNS <= set(cols)
    assert cols['rbpdt_id_set']['nullable'] is True
    assert cols['rbpdt_category']['nullable'] is True
    assert cols['rbpdt_updated_at']['nullable'] is True
    for flag in ('rbpdt_kind_locked', 'rbpdt_set_locked', 'rbpdt_hidden', 'rbpdt_listed'):
        assert cols[flag]['nullable'] is False
    checks = {c['name'] for c in inspector().get_check_constraints('rbproducts',
                                                                    schema='riftbound')}
    assert 'rbproducts_kind_chk' in checks


def test_existing_rows_survive_the_key_change_with_the_defaults(migration_app):
    upgrade(BEFORE)
    run(OLD_ROW, set='OGN', id=10, name='Booster')
    run(OLD_ROW, set='SFD', id=11, name='Display')
    upgrade(CATALOG)
    assert rows('SELECT rbpdt_id_set, rbpdt_id_product, rbpdt_name, rbpdt_description, '
                'rbpdt_type, rbpdt_image_url, rbpdt_image, rbpdt_category, rbpdt_kind, '
                'rbpdt_kind_locked, rbpdt_set_locked, rbpdt_hidden, rbpdt_listed, '
                'rbpdt_updated_at FROM riftbound.rbproducts ORDER BY rbpdt_id_product') == [
        ('OGN', 10, 'Booster', 'desc', 'nonsingle', 'http://x/i.png', 'i.png',
         None, None, False, False, False, True, None),
        ('SFD', 11, 'Display', 'desc', 'nonsingle', 'http://x/i.png', 'i.png',
         None, None, False, False, False, True, None),
    ]


def test_the_upgrade_refuses_duplicate_product_ids(migration_app):
    upgrade(BEFORE)
    run(OLD_ROW, set='OGN', id=10, name='Booster')
    run(OLD_ROW, set='SFD', id=10, name='Booster again')
    with pytest.raises(RuntimeError) as caught:
        upgrade(CATALOG)
    assert "rbproducts holds 1 product id(s) in more than one row" in str(caught.value)
    assert 'Nothing was changed' in str(caught.value)
    assert pk()['constrained_columns'] == ['rbpdt_id_set', 'rbpdt_id_product']
    assert rows('SELECT COUNT(*) FROM riftbound.rbproducts') == [(2,)]


def test_one_row_per_product_id_and_no_set_needed(migration_app):
    upgrade(CATALOG)
    run(NEW_ROW, set=None, id=10, name='Booster', kind='booster')
    with pytest.raises(IntegrityError):
        run(NEW_ROW, set='OGN', id=10, name='Booster', kind='booster')
    assert rows('SELECT rbpdt_id_set, rbpdt_listed FROM riftbound.rbproducts') == [(None, True)]


@pytest.mark.parametrize('kind', ['booster', 'box', 'case', 'bundle', 'starter', 'sleeves',
                                  'accessory', 'other', None])
def test_the_kind_check_accepts_the_kinds_and_null(migration_app, kind):
    upgrade(CATALOG)
    run(NEW_ROW, set=None, id=1, name='P', kind=kind)
    assert rows('SELECT rbpdt_kind FROM riftbound.rbproducts') == [(kind,)]


def test_the_kind_check_rejects_anything_else(migration_app):
    upgrade(CATALOG)
    with pytest.raises(IntegrityError):
        run(NEW_ROW, set=None, id=1, name='P', kind='Booster')
    assert rows('SELECT COUNT(*) FROM riftbound.rbproducts') == [(0,)]


def test_catalog_round_trip_and_drift(migration_app):
    upgrade()
    assert drift() == []
    run(NEW_ROW, set='OGN', id=10, name='Booster', kind='booster')
    downgrade(BEFORE)
    assert pk() == {'name': 'rbproducts_pkey',
                    'constrained_columns': ['rbpdt_id_set', 'rbpdt_id_product']}
    cols = columns()
    assert not NEW_COLUMNS & set(cols)
    assert cols['rbpdt_id_set']['nullable'] is False
    assert rows('SELECT rbpdt_id_set, rbpdt_id_product, rbpdt_name FROM '
                'riftbound.rbproducts') == [('OGN', 10, 'Booster')]
    upgrade()
    assert pk()['constrained_columns'] == ['rbpdt_id_product']
    assert drift() == []


def test_the_downgrade_refuses_a_product_without_a_set(migration_app):
    upgrade(CATALOG)
    run(NEW_ROW, set=None, id=10, name='Booster', kind='booster')
    run(NEW_ROW, set='OGN', id=11, name='Display', kind='box')
    with pytest.raises(RuntimeError) as caught:
        downgrade(BEFORE)
    assert "rbproducts holds 1 product(s) without rbpdt_id_set" in str(caught.value)
    assert 'Nothing was changed' in str(caught.value)
    assert pk()['constrained_columns'] == ['rbpdt_id_product']
    assert NEW_COLUMNS <= set(columns())
    assert rows('SELECT rbpdt_id_product, rbpdt_kind FROM riftbound.rbproducts '
                'ORDER BY 1') == [(10, 'booster'), (11, 'box')]
    run("DELETE FROM riftbound.rbproducts WHERE rbpdt_id_set IS NULL")
    downgrade(BEFORE)
    assert rows('SELECT rbpdt_id_set, rbpdt_id_product FROM riftbound.rbproducts') == [
        ('OGN', 11)]


def test_kind_check_accepts_products_refresh(migration_app):
    upgrade(CATALOG)
    with pytest.raises(IntegrityError):
        run(JOB, kind='products_refresh', status='queued')
    upgrade(KIND)
    run(JOB, kind='products_refresh', status='queued')
    run(JOB, kind='value_snapshot', status='queued')
    with pytest.raises(IntegrityError):
        run(JOB, kind='nope', status='queued')


def test_kind_downgrade_refuses_while_such_jobs_exist(migration_app):
    upgrade(KIND)
    run(JOB, kind='products_refresh', status='success')
    with pytest.raises(RuntimeError) as caught:
        downgrade(CATALOG)
    assert "holds 1 'products_refresh' job(s)" in str(caught.value)
    assert rows('SELECT rbjob_kind FROM riftbound.rbjobs') == [('products_refresh',)]
    run("DELETE FROM riftbound.rbjobs")
    downgrade(CATALOG)
    with pytest.raises(IntegrityError):
        run(JOB, kind='products_refresh', status='queued')


def test_revisions_chain():
    import importlib.util
    from pathlib import Path
    versions = Path(__file__).resolve().parents[1] / 'migrations' / 'versions'
    for name, down in ((CATALOG, BEFORE), (KIND, CATALOG)):
        spec = importlib.util.spec_from_file_location(f'm_{name}', versions / f'{name}.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert (module.revision, module.down_revision) == (name, down)
