"""F14-c S1, S2 (AC1): migrations `0021_user_products` and `0022_snapshot_products_value`:
round trips, drift, constraints, FK restrict on product delete, cascade on user delete."""
import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from tests.migration_helpers import downgrade, drift, inspector, rows, run, tables, upgrade

BEFORE = '0020_jobs_products_refresh'
TABLE = '0021_user_products'
COLUMN = '0022_snapshot_products_value'
USER = ("INSERT INTO riftbound.rbusers (id, username, email, password_hash, is_admin, is_blocked, "
        "failed_login_count) VALUES (:id, :name, :name || '@test.com', 'x', 0, 0, 0)")
PRODUCT = ("INSERT INTO riftbound.rbproducts (rbpdt_id_product, rbpdt_name, rbpdt_type) "
           "VALUES (:id, 'Booster', 'nonsingle')")
LINE = ("INSERT INTO riftbound.rbuserproducts (rbupr_user_id, rbupr_id_product, rbupr_quantity, "
        "rbupr_purchase_price, rbupr_created_at, rbupr_updated_at) VALUES (:user, :product, "
        ":qty, :price, '2030-01-01 12:00:00', '2030-01-01 12:00:00')")
SNAP = ("INSERT INTO riftbound.rbvaluesnaps (rbvsn_user_id, rbvsn_date, rbvsn_value, rbvsn_cost, "
        "rbvsn_qty, rbvsn_unique, rbvsn_unpriced) VALUES (1, '2030-01-01', 12.5, NULL, 3, 2, 1)")


def _seed(conn=None):
    statements = ((USER, dict(id=1, name='ana')), (USER, dict(id=2, name='bo')),
                  (PRODUCT, dict(id=10)), (PRODUCT, dict(id=20)))
    for sql, params in statements:
        if conn is None:
            run(sql, **params)
        else:
            conn.execute(sa.text(sql), params)


def test_the_table_has_its_named_constraints_and_index(migration_app):
    upgrade(TABLE)
    assert 'rbuserproducts' in tables()
    assert inspector().get_pk_constraint('rbuserproducts', schema='riftbound') == {
        'name': 'rbuserproducts_pkey', 'constrained_columns': ['rbupr_id']}
    fks = sorted((fk['name'], fk['referred_table'], fk['options'].get('ondelete'))
                 for fk in inspector().get_foreign_keys('rbuserproducts', schema='riftbound'))
    assert fks == [('rbuserproducts_product_fk', 'rbproducts', 'RESTRICT'),
                   ('rbuserproducts_user_fk', 'rbusers', 'CASCADE')]
    checks = {c['name'] for c in inspector().get_check_constraints('rbuserproducts',
                                                                   schema='riftbound')}
    assert checks == {'rbuserproducts_quantity_chk', 'rbuserproducts_purchase_price_chk'}
    assert 'ix_rbuserproducts_user' in {
        i['name'] for i in inspector().get_indexes('rbuserproducts', schema='riftbound')}


def test_quantity_and_price_checks(migration_app):
    upgrade(TABLE)
    _seed()
    run(LINE, user=1, product=10, qty=1, price=None)
    run(LINE, user=1, product=10, qty=9999, price=0)
    for qty, price in ((0, None), (10000, None), (1, -0.01)):
        with pytest.raises(IntegrityError):
            run(LINE, user=1, product=10, qty=qty, price=price)
    assert rows('SELECT rbupr_quantity FROM riftbound.rbuserproducts '
                'ORDER BY rbupr_id') == [(1,), (9999,)]


def test_a_product_with_owners_cannot_be_deleted(migration_app):
    from app import db
    upgrade(TABLE)
    with db.engine.begin() as conn:
        conn.exec_driver_sql('PRAGMA foreign_keys=ON')   # SQLite enforces FKs only when asked
        _seed(conn)
        conn.execute(sa.text(LINE), dict(user=1, product=10, qty=2, price=None))
    with pytest.raises(IntegrityError):
        with db.engine.begin() as conn:
            conn.exec_driver_sql('PRAGMA foreign_keys=ON')
            conn.execute(sa.text('DELETE FROM riftbound.rbproducts WHERE rbpdt_id_product = 10'))
    with db.engine.begin() as conn:
        conn.exec_driver_sql('PRAGMA foreign_keys=ON')
        conn.execute(sa.text('DELETE FROM riftbound.rbproducts WHERE rbpdt_id_product = 20'))
    assert rows('SELECT rbpdt_id_product FROM riftbound.rbproducts') == [(10,)]
    assert rows('SELECT rbupr_id_product FROM riftbound.rbuserproducts') == [(10,)]


def test_deleting_a_user_deletes_their_products(migration_app):
    from app import db
    upgrade(TABLE)
    with db.engine.begin() as conn:
        conn.exec_driver_sql('PRAGMA foreign_keys=ON')
        _seed(conn)
        for user in (1, 2):
            conn.execute(sa.text(LINE), dict(user=user, product=10, qty=1, price=None))
        conn.execute(sa.text('DELETE FROM riftbound.rbusers WHERE id = 1'))
    assert rows('SELECT rbupr_user_id FROM riftbound.rbuserproducts') == [(2,)]


def test_table_round_trip_and_drift(migration_app):
    upgrade()
    assert drift() == []
    downgrade(BEFORE)
    assert 'rbuserproducts' not in tables()
    upgrade()
    assert 'rbuserproducts' in tables()
    assert drift() == []


def _snapshot_columns():
    return {c['name'] for c in inspector().get_columns('rbvaluesnaps', schema='riftbound')}


def test_snapshot_column_round_trip_keeps_the_rows(migration_app):
    upgrade(TABLE)
    run(USER, id=1, name='ana')
    run(SNAP)
    assert 'rbvsn_products_value' not in _snapshot_columns()
    upgrade(COLUMN)
    column = next(c for c in inspector().get_columns('rbvaluesnaps', schema='riftbound')
                  if c['name'] == 'rbvsn_products_value')
    assert column['nullable'] is True
    assert (column['type'].precision, column['type'].scale) == (12, 2)
    assert rows('SELECT rbvsn_value, rbvsn_products_value FROM riftbound.rbvaluesnaps') == [
        (12.5, None)]
    run('UPDATE riftbound.rbvaluesnaps SET rbvsn_products_value = 40.25')
    assert drift() == []
    downgrade(TABLE)
    assert 'rbvsn_products_value' not in _snapshot_columns()
    assert rows('SELECT rbvsn_value, rbvsn_qty FROM riftbound.rbvaluesnaps') == [(12.5, 3)]
    upgrade()
    assert rows('SELECT rbvsn_products_value FROM riftbound.rbvaluesnaps') == [(None,)]
    assert drift() == []


def test_revisions_chain_and_state_the_data_loss():
    import importlib.util
    from pathlib import Path
    versions = Path(__file__).resolve().parents[1] / 'migrations' / 'versions'
    for name, down, loss in ((TABLE, BEFORE, "drops every user's products"),
                             (COLUMN, TABLE, 'drops the column and its values')):
        spec = importlib.util.spec_from_file_location(f'm_{name}', versions / f'{name}.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert (module.revision, module.down_revision) == (name, down)
        assert loss in ' '.join(module.__doc__.split())
