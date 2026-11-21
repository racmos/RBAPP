"""Product kinds taxonomy (owner decision 2026-11-20): migration `0033_product_kinds` renames the
stored kinds and replaces the CHECK `rbproducts_kind_chk`.

Old kinds -> new kinds on the upgrade: box -> booster_box, case -> booster_box, starter ->
champion_deck, bundle -> sealed_box_set, sleeves -> accessory; booster, accessory, other and NULL
stay. The downgrade maps back booster_box -> box, champion_deck -> starter, sealed_box_set ->
bundle; a former `case` comes back as `box` and former `sleeves` stay `accessory` (not
restorable). Runs on SQLite here; the `postgres`-marked copy runs on PostgreSQL 18 in CI
(`migrations-pg`).
"""
import importlib.util
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from app import create_app, db
from app.models.cardmarket import PRODUCT_KINDS
from tests.migration_helpers import downgrade, drift, inspector, rows, run, upgrade

BEFORE = '0032_api_keys'
REVISION = '0033_product_kinds'
OLD_KINDS = ('booster', 'box', 'case', 'bundle', 'starter', 'sleeves', 'accessory', 'other')
NEW_KINDS = ('booster', 'booster_box', 'champion_deck', 'sealed_box_set', 'accessory', 'other')
ROW = ("INSERT INTO riftbound.rbproducts (rbpdt_id_product, rbpdt_name, rbpdt_type, "
       "rbpdt_category, rbpdt_kind, rbpdt_kind_locked) "
       "VALUES (:id, :name, 'nonsingle', :category, :kind, :locked)")

# (id, old kind, locked, kind after the upgrade, kind after the downgrade)
MAPPING = [
    (1, 'booster', False, 'booster', 'booster'),
    (2, 'box', False, 'booster_box', 'box'),
    (3, 'case', True, 'booster_box', 'box'),            # a case is a booster box
    (4, 'bundle', False, 'sealed_box_set', 'bundle'),
    (5, 'starter', True, 'champion_deck', 'starter'),
    (6, 'sleeves', False, 'accessory', 'accessory'),    # sleeves are an accessory
    (7, 'accessory', False, 'accessory', 'accessory'),
    (8, 'other', False, 'other', 'other'),
    (9, None, False, None, None),
]


def seed_old_kinds():
    for product_id, kind, locked, _, _ in MAPPING:
        run(ROW, id=product_id, name=f'P{product_id}', category=f'Category {product_id}',
            kind=kind, locked=locked)


def stored():
    return rows('SELECT rbpdt_id_product, rbpdt_kind, rbpdt_kind_locked, rbpdt_category '
                'FROM riftbound.rbproducts ORDER BY rbpdt_id_product')


def expected(column):
    index = {'upgrade': 3, 'downgrade': 4}[column]
    return [(entry[0], entry[index], entry[2], f'Category {entry[0]}') for entry in MAPPING]


def check_names():
    return {c['name'] for c in inspector().get_check_constraints('rbproducts',
                                                                 schema='riftbound')}


def test_the_model_kinds():
    assert PRODUCT_KINDS == NEW_KINDS


def test_the_upgrade_maps_every_old_kind(migration_app):
    upgrade(BEFORE)
    seed_old_kinds()
    upgrade(REVISION)
    assert stored() == expected('upgrade')
    assert 'rbproducts_kind_chk' in check_names()


@pytest.mark.parametrize('kind', NEW_KINDS + (None,))
def test_the_new_check_accepts_the_new_kinds_and_null(migration_app, kind):
    upgrade(REVISION)
    run(ROW, id=1, name='P', category=None, kind=kind, locked=False)
    assert rows('SELECT rbpdt_kind FROM riftbound.rbproducts') == [(kind,)]


@pytest.mark.parametrize('kind', ('box', 'case', 'bundle', 'starter', 'sleeves', 'unused',
                                  'card', 'Booster'))
def test_the_new_check_refuses_old_and_virtual_kinds(migration_app, kind):
    upgrade(REVISION)
    with pytest.raises(IntegrityError):
        run(ROW, id=1, name='P', category=None, kind=kind, locked=False)
    assert rows('SELECT COUNT(*) FROM riftbound.rbproducts') == [(0,)]


def test_round_trip_and_drift(migration_app):
    upgrade(BEFORE)
    seed_old_kinds()
    upgrade()
    assert drift() == []
    downgrade(BEFORE)
    assert stored() == expected('downgrade')
    # the old CHECK is back: old kinds insert, new ones are refused
    run(ROW, id=20, name='Case', category=None, kind='case', locked=False)
    with pytest.raises(IntegrityError):
        run(ROW, id=21, name='Box', category=None, kind='booster_box', locked=False)
    upgrade()
    assert drift() == []
    assert rows('SELECT rbpdt_kind FROM riftbound.rbproducts WHERE rbpdt_id_product IN (3, 20) '
                'ORDER BY rbpdt_id_product') == [('booster_box',), ('booster_box',)]
    assert stored()[:len(MAPPING)] == expected('upgrade')


def test_revision_chain():
    versions = Path(__file__).resolve().parents[1] / 'migrations' / 'versions'
    spec = importlib.util.spec_from_file_location('m_0033', versions / f'{REVISION}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert (module.revision, module.down_revision) == (REVISION, BEFORE)
    assert module.KINDS_BEFORE == OLD_KINDS
    assert module.KINDS_AFTER == NEW_KINDS


# --- PostgreSQL 18 (CI `migrations-pg`, `pytest -m postgres`) ---------------------------------

@pytest.fixture
def pg_migration_app(pg_url, tmp_path):
    app = create_app(TESTING=True, SQLALCHEMY_DATABASE_URI=pg_url, SECRET_KEY='test-secret-key',
                     LEGACY_BACKUP_DIR=str(tmp_path / 'backups'))
    with app.app_context():
        yield app
        db.session.remove()
        db.engine.dispose()


@pytest.mark.postgres
def test_postgres_upgrade_maps_check_and_round_trip(pg_migration_app):
    upgrade(BEFORE)
    seed_old_kinds()
    upgrade(REVISION)
    assert stored() == expected('upgrade')
    with pytest.raises(IntegrityError):
        run(ROW, id=30, name='Case', category=None, kind='case', locked=False)
    assert drift() == []
    downgrade(BEFORE)
    assert stored() == expected('downgrade')
    with pytest.raises(IntegrityError):
        run(ROW, id=31, name='Box', category=None, kind='booster_box', locked=False)
    upgrade()
    assert drift() == []
    assert stored() == expected('upgrade')
