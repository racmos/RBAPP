"""F2-b S8 (AC4): migration `0013_price_product_date_idx` adds the
`(rbprc_id_product, rbprc_date)` index on `rbcm_price`; downgrade drops it.
Round trip 0012 <-> 0013 and drift (SQLite; the `migrations-pg` CI job runs
the same revisions on PostgreSQL 18)."""
from app.models.cardmarket import RbcmPrice
from tests.migration_helpers import downgrade, drift, inspector, tables, upgrade

INDEX = 'idx_rbcm_price_product_date'


def _migration():
    import importlib.util
    from pathlib import Path
    path = (Path(__file__).resolve().parents[1] / 'migrations' / 'versions' /
            '0013_price_product_date_idx.py')
    spec = importlib.util.spec_from_file_location('migration_0013_price_product_date_idx', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_revision_chains_after_0012():
    module = _migration()
    assert (module.revision, module.down_revision) == (
        '0013_price_product_date_idx', '0012_jobs_riot_sync')


def _index_names():
    return {index['name'] for index in inspector().get_indexes('rbcm_price', schema='riftbound')}


def test_round_trip_and_no_drift(migration_app):
    upgrade()
    assert INDEX in _index_names()
    downgrade('0012_jobs_riot_sync')
    assert INDEX not in _index_names()
    assert 'rbcm_price' in tables()
    upgrade()
    assert drift() == []


def test_index_columns_in_order(migration_app):
    upgrade()
    indexes = {index['name']: index
               for index in inspector().get_indexes('rbcm_price', schema='riftbound')}
    assert indexes[INDEX]['column_names'] == ['rbprc_id_product', 'rbprc_date']


def test_model_declares_the_index():
    names = [index.name for index in RbcmPrice.__table__.indexes]
    assert INDEX in names
    columns = next(index for index in RbcmPrice.__table__.indexes if index.name == INDEX)
    assert [column.name for column in columns.columns] == ['rbprc_id_product', 'rbprc_date']
