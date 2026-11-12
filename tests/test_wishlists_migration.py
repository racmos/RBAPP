"""F3-f-1: migration `0026_wishlists`: `rbwishlists`, `rbwishlistlines` and `rbwishlistalerts`
with their named constraints, the case-insensitive list name per user, one default list per
user (partial unique index), the NULL-safe unique target of a line and of an alert
(expression unique indexes over `COALESCE`), the value CHECKs, the cascades, round trip and
drift (docs/requirements/F3/F3-f-wishlists-design.md, "Data model")."""
import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from tests.migration_helpers import downgrade, drift, inspector, rows, run, tables, upgrade

BEFORE = '0025_decks_v2'
REVISION = '0026_wishlists'
NEW_TABLES = {'rbwishlists', 'rbwishlistlines', 'rbwishlistalerts'}
NOW = "'2030-01-01 12:00:00'"
USER = ("INSERT INTO riftbound.rbusers (id, username, email, password_hash, is_admin, is_blocked, "
        "failed_login_count) VALUES (:id, :name, :name || '@test.com', 'x', 0, 0, 0)")
LIST = ("INSERT INTO riftbound.rbwishlists (rbwls_id, rbwls_user_id, rbwls_name, rbwls_is_default, "
        f"rbwls_position, rbwls_created_at, rbwls_updated_at) VALUES (:id, :user, :name, :default, "
        f":pos, {NOW}, {NOW})")
LINE = ("INSERT INTO riftbound.rbwishlistlines (rbwsl_list_id, rbwsl_name_key, rbwsl_name, "
        "rbwsl_rbset_id, rbwsl_rbcar_id, rbwsl_foil, rbwsl_qty, rbwsl_max_price, rbwsl_note, "
        f"rbwsl_created_at, rbwsl_updated_at) VALUES (:list, :key, :key, :set, :card, :foil, :qty, "
        f":max_price, NULL, {NOW}, {NOW})")
ALERT = ("INSERT INTO riftbound.rbwishlistalerts (rbwal_user_id, rbwal_name_key, rbwal_name, "
         "rbwal_rbset_id, rbwal_rbcar_id, rbwal_price, rbwal_max_price, rbwal_price_date, "
         f"rbwal_created_at, rbwal_read_at) VALUES (:user, :key, :key, :set, :card, :price, :max, "
         f":day, {NOW}, NULL)")
COLLECTION = ("INSERT INTO riftbound.rbcollection (rbcol_id, rbcol_rbset_id, rbcol_rbcar_id, "
              "rbcol_foil, rbcol_user, rbcol_quantity, rbcol_selling, rbcol_sell_qty, "
              f"rbcol_chadat) VALUES (7, 'OGN', '1', 'N', 'ana', 3, 'N', 0, {NOW})")


def _list(id=1, user=1, name='Wishlist', default=0, pos=1):
    return dict(id=id, user=user, name=name, default=default, pos=pos)


def _line(list=1, key='alpha', set=None, card=None, foil='any', qty=1, max_price=None):
    return dict(list=list, key=key, set=set, card=card, foil=foil, qty=qty, max_price=max_price)


def _alert(user=1, key='alpha', set=None, card=None, price='1.50', max='2.00', day='2030-01-01'):
    return dict(user=user, key=key, set=set, card=card, price=price, max=max, day=day)


def _users():
    run(USER, id=1, name='ana')
    run(USER, id=2, name='bo')


def _rejected(sql, **params):
    with pytest.raises(IntegrityError):
        run(sql, **params)


def _index_ddl(name):
    # SQLAlchemy cannot reflect expression or partial indexes on SQLite: read the DDL itself.
    return rows('SELECT sql FROM riftbound.sqlite_master WHERE name = :name', name=name)


def test_the_tables_have_their_named_constraints_and_indexes(migration_app):
    upgrade(REVISION)
    assert NEW_TABLES <= tables()
    insp = inspector()
    pks = {table: insp.get_pk_constraint(table, schema='riftbound') for table in NEW_TABLES}
    assert pks == {
        'rbwishlists': {'name': 'rbwishlists_pkey', 'constrained_columns': ['rbwls_id']},
        'rbwishlistlines': {'name': 'rbwishlistlines_pkey', 'constrained_columns': ['rbwsl_id']},
        'rbwishlistalerts': {'name': 'rbwishlistalerts_pkey', 'constrained_columns': ['rbwal_id']},
    }
    fks = sorted((fk['name'], fk['referred_table'], tuple(fk['referred_columns']),
                  fk['options'].get('ondelete'))
                 for table in NEW_TABLES for fk in insp.get_foreign_keys(table, schema='riftbound'))
    assert fks == [('rbwishlistalerts_user_fk', 'rbusers', ('id',), 'CASCADE'),
                   ('rbwishlistlines_list_fk', 'rbwishlists', ('rbwls_id',), 'CASCADE'),
                   ('rbwishlists_user_fk', 'rbusers', ('id',), 'CASCADE')]
    checks = {table: {c['name'] for c in insp.get_check_constraints(table, schema='riftbound')}
              for table in NEW_TABLES}
    assert checks == {
        'rbwishlists': {'rbwishlists_name_chk', 'rbwishlists_position_chk'},
        'rbwishlistlines': {'rbwishlistlines_printing_chk', 'rbwishlistlines_foil_chk',
                            'rbwishlistlines_qty_chk', 'rbwishlistlines_max_price_chk'},
        'rbwishlistalerts': {'rbwishlistalerts_printing_chk', 'rbwishlistalerts_price_chk'},
    }
    uniques = {u['name']: u['column_names'] for table in NEW_TABLES
               for u in insp.get_unique_constraints(table, schema='riftbound')}
    assert uniques == {'rbwishlists_user_position_uq': ['rbwls_user_id', 'rbwls_position']}
    plain = {i['name']: i['column_names'] for table in NEW_TABLES
             for i in insp.get_indexes(table, schema='riftbound')}
    assert plain['ix_rbwishlistlines_name_key'] == ['rbwsl_name_key']
    assert plain['ix_rbwishlistalerts_user_created'] == ['rbwal_user_id', 'rbwal_created_at']
    assert _index_ddl('rbwishlists_user_name_uq') == [(
        'CREATE UNIQUE INDEX rbwishlists_user_name_uq ON rbwishlists '
        '(rbwls_user_id, lower(rbwls_name))',)]
    assert _index_ddl('rbwishlists_user_default_uq') == [(
        'CREATE UNIQUE INDEX rbwishlists_user_default_uq ON rbwishlists (rbwls_user_id) '
        'WHERE rbwls_is_default',)]
    assert _index_ddl('rbwishlistlines_target_uq') == [(
        "CREATE UNIQUE INDEX rbwishlistlines_target_uq ON rbwishlistlines (rbwsl_list_id, "
        "rbwsl_name_key, coalesce(rbwsl_rbset_id, '*'), coalesce(rbwsl_rbcar_id, '*'), "
        "rbwsl_foil)",)]
    assert _index_ddl('rbwishlistalerts_target_uq') == [(
        "CREATE UNIQUE INDEX rbwishlistalerts_target_uq ON rbwishlistalerts (rbwal_user_id, "
        "rbwal_name_key, coalesce(rbwal_rbset_id, '*'), coalesce(rbwal_rbcar_id, '*'), "
        "rbwal_price_date)",)]
    assert _index_ddl('ix_rbwishlistalerts_user_unread') == [(
        'CREATE INDEX ix_rbwishlistalerts_user_unread ON rbwishlistalerts (rbwal_user_id) '
        'WHERE rbwal_read_at IS NULL',)]


def test_the_columns_have_their_types_and_nullability(migration_app):
    upgrade(REVISION)
    insp = inspector()
    columns = {(table, c['name']): c for table in NEW_TABLES
               for c in insp.get_columns(table, schema='riftbound')}
    expected = {
        ('rbwishlists', 'rbwls_name'): ('VARCHAR(80)', False),
        ('rbwishlists', 'rbwls_is_default'): ('BOOLEAN', False),
        ('rbwishlists', 'rbwls_position'): ('INTEGER', False),
        ('rbwishlists', 'rbwls_created_at'): ('DATETIME', False),
        ('rbwishlists', 'rbwls_updated_at'): ('DATETIME', False),
        ('rbwishlistlines', 'rbwsl_list_id'): ('INTEGER', False),
        ('rbwishlistlines', 'rbwsl_name_key'): ('VARCHAR(200)', False),
        ('rbwishlistlines', 'rbwsl_name'): ('VARCHAR(200)', False),
        ('rbwishlistlines', 'rbwsl_rbset_id'): ('TEXT', True),
        ('rbwishlistlines', 'rbwsl_rbcar_id'): ('TEXT', True),
        ('rbwishlistlines', 'rbwsl_foil'): ('VARCHAR(3)', False),
        ('rbwishlistlines', 'rbwsl_qty'): ('SMALLINT', False),
        ('rbwishlistlines', 'rbwsl_max_price'): ('NUMERIC(10, 2)', True),
        ('rbwishlistlines', 'rbwsl_note'): ('VARCHAR(200)', True),
        ('rbwishlistalerts', 'rbwal_user_id'): ('INTEGER', False),
        ('rbwishlistalerts', 'rbwal_rbset_id'): ('TEXT', True),
        ('rbwishlistalerts', 'rbwal_price'): ('NUMERIC(10, 2)', False),
        ('rbwishlistalerts', 'rbwal_max_price'): ('NUMERIC(10, 2)', False),
        ('rbwishlistalerts', 'rbwal_price_date'): ('DATE', False),
        ('rbwishlistalerts', 'rbwal_created_at'): ('DATETIME', False),
        ('rbwishlistalerts', 'rbwal_read_at'): ('DATETIME', True),
    }
    actual = {key: (str(columns[key]['type']), columns[key]['nullable']) for key in expected}
    assert actual == expected
    # Daily alerts (A3): no arming state on a line.
    assert not any('arm' in name for table, name in columns if table == 'rbwishlistlines')


def test_defaults(migration_app):
    upgrade(REVISION)
    _users()
    run("INSERT INTO riftbound.rbwishlists (rbwls_user_id, rbwls_name, rbwls_position, "
        f"rbwls_created_at, rbwls_updated_at) VALUES (1, 'Wishlist', 1, {NOW}, {NOW})")
    run("INSERT INTO riftbound.rbwishlistlines (rbwsl_list_id, rbwsl_name_key, rbwsl_name, "
        f"rbwsl_created_at, rbwsl_updated_at) VALUES (1, 'alpha', 'Alpha', {NOW}, {NOW})")
    assert rows('SELECT rbwls_is_default FROM riftbound.rbwishlists') == [(0,)]
    assert rows('SELECT rbwsl_foil, rbwsl_qty, rbwsl_max_price, rbwsl_rbset_id, rbwsl_rbcar_id '
                'FROM riftbound.rbwishlistlines') == [('any', 1, None, None, None)]


def test_the_list_name_is_unique_per_user_ignoring_case(migration_app):
    upgrade(REVISION)
    _users()
    run(LIST, **_list(id=1, user=1, name='Wishlist'))
    run(LIST, **_list(id=2, user=2, name='WISHLIST'))
    _rejected(LIST, **_list(id=3, user=1, name='wishLIST', pos=2))
    _rejected(LIST, **_list(id=4, user=1, name='', pos=2))
    _rejected(LIST, **_list(id=5, user=1, name='   ', pos=2))
    _rejected(LIST, **_list(id=6, user=1, name='Other', pos=1))
    _rejected(LIST, **_list(id=7, user=1, name='Zero', pos=0))
    run(LIST, **_list(id=8, user=1, name='Trades', pos=2))
    assert rows('SELECT rbwls_user_id, rbwls_name FROM riftbound.rbwishlists ORDER BY rbwls_id'
                ) == [(1, 'Wishlist'), (2, 'WISHLIST'), (1, 'Trades')]


def test_one_default_list_per_user(migration_app):
    upgrade(REVISION)
    _users()
    run(LIST, **_list(id=1, user=1, name='A', default=1, pos=1))
    run(LIST, **_list(id=2, user=1, name='B', default=0, pos=2))
    run(LIST, **_list(id=3, user=1, name='C', default=0, pos=3))
    run(LIST, **_list(id=4, user=2, name='A', default=1, pos=1))
    _rejected(LIST, **_list(id=5, user=1, name='D', default=1, pos=4))
    _rejected('UPDATE riftbound.rbwishlists SET rbwls_is_default = 1 WHERE rbwls_id = 2')
    assert rows('SELECT rbwls_id FROM riftbound.rbwishlists WHERE rbwls_is_default = 1 '
                'ORDER BY rbwls_id') == [(1,), (4,)]


@pytest.mark.parametrize('qty', [0, 100, -1])
def test_the_quantity_is_between_1_and_99(migration_app, qty):
    upgrade(REVISION)
    _users()
    run(LIST, **_list())
    _rejected(LINE, **_line(key='alpha', qty=qty))
    run(LINE, **_line(key='alpha', qty=1))
    run(LINE, **_line(key='beta', qty=99))
    assert rows('SELECT rbwsl_qty FROM riftbound.rbwishlistlines ORDER BY rbwsl_id') == [(1,), (99,)]


def test_foil_values_printing_pairs_and_max_price(migration_app):
    upgrade(REVISION)
    _users()
    run(LIST, **_list())
    for params in (_line(foil='Y'), _line(foil='s'), _line(foil=''),
                   _line(set='OGN', card=None), _line(set=None, card='1'),
                   _line(max_price='-0.01')):
        _rejected(LINE, **params)
    run(LINE, **_line(key='a', foil='any'))
    run(LINE, **_line(key='b', foil='N', set='OGN', card='1'))
    run(LINE, **_line(key='c', foil='S', max_price='0'))
    run(LINE, **_line(key='d', max_price='12.34'))
    assert rows('SELECT rbwsl_name_key, rbwsl_foil, rbwsl_rbset_id, rbwsl_rbcar_id '
                'FROM riftbound.rbwishlistlines ORDER BY rbwsl_id') == [
        ('a', 'any', None, None), ('b', 'N', 'OGN', '1'), ('c', 'S', None, None),
        ('d', 'any', None, None)]


def test_a_target_is_unique_per_list_including_by_name_lines(migration_app):
    upgrade(REVISION)
    _users()
    run(LIST, **_list(id=1, name='A', pos=1))
    run(LIST, **_list(id=2, name='B', pos=2))
    run(LINE, **_line(list=1, key='alpha', foil='any'))
    run(LINE, **_line(list=1, key='alpha', set='OGN', card='1', foil='N'))
    _rejected(LINE, **_line(list=1, key='alpha', foil='any'))           # by name, NULL printing
    _rejected(LINE, **_line(list=1, key='alpha', set='OGN', card='1', foil='N'))
    run(LINE, **_line(list=1, key='alpha', set='OGN', card='1', foil='S'))     # foil differs
    run(LINE, **_line(list=1, key='alpha', set='OGN', card='1a', foil='N'))    # alt art
    run(LINE, **_line(list=1, key='alpha', foil='N'))                   # by name, other foil
    run(LINE, **_line(list=2, key='alpha', foil='any'))                 # another list
    run(LINE, **_line(list=2, key='alpha', set='OGN', card='1', foil='N'))
    assert rows('SELECT COUNT(*) FROM riftbound.rbwishlistlines') == [(7,)]


def test_an_alert_is_unique_per_user_target_and_day(migration_app):
    upgrade(REVISION)
    _users()
    run(ALERT, **_alert(user=1, key='alpha', set='OGN', card='1', day='2030-01-01'))
    run(ALERT, **_alert(user=1, key='alpha', day='2030-01-01'))
    _rejected(ALERT, **_alert(user=1, key='alpha', set='OGN', card='1', day='2030-01-01'))
    _rejected(ALERT, **_alert(user=1, key='alpha', day='2030-01-01'))
    run(ALERT, **_alert(user=1, key='alpha', set='OGN', card='1', day='2030-01-02'))
    run(ALERT, **_alert(user=2, key='alpha', set='OGN', card='1', day='2030-01-01'))
    for params in (_alert(key='beta', set='OGN', card=None), _alert(key='beta', set=None, card='1'),
                   _alert(key='beta', price='-1'), _alert(key='beta', max='-1')):
        _rejected(ALERT, **params)
    assert rows('SELECT rbwal_user_id, rbwal_rbset_id, rbwal_price_date, rbwal_read_at '
                'FROM riftbound.rbwishlistalerts ORDER BY rbwal_id') == [
        (1, 'OGN', '2030-01-01', None), (1, None, '2030-01-01', None),
        (1, 'OGN', '2030-01-02', None), (2, 'OGN', '2030-01-01', None)]


def test_deleting_a_list_or_a_user_cascades(migration_app):
    upgrade(REVISION)
    from app import db
    with db.engine.begin() as conn:
        conn.exec_driver_sql('PRAGMA foreign_keys=ON')    # SQLite enforces FKs only when asked
        for params in (dict(id=1, name='ana'), dict(id=2, name='bo')):
            conn.execute(sa.text(USER), params)
        for params in (_list(id=1, user=1, name='A', pos=1), _list(id=2, user=1, name='B', pos=2),
                       _list(id=3, user=2, name='A', pos=1)):
            conn.execute(sa.text(LIST), params)
        for params in (_line(list=1, key='a'), _line(list=2, key='b'), _line(list=3, key='c')):
            conn.execute(sa.text(LINE), params)
        for params in (_alert(user=1, key='a'), _alert(user=2, key='c')):
            conn.execute(sa.text(ALERT), params)
        conn.execute(sa.text('DELETE FROM riftbound.rbwishlists WHERE rbwls_id = 1'))
    assert rows('SELECT rbwsl_name_key FROM riftbound.rbwishlistlines ORDER BY rbwsl_id') == [
        ('b',), ('c',)]
    # A5: alerts already raised stay when a list goes.
    assert rows('SELECT COUNT(*) FROM riftbound.rbwishlistalerts') == [(2,)]
    with db.engine.begin() as conn:
        conn.exec_driver_sql('PRAGMA foreign_keys=ON')
        conn.execute(sa.text('DELETE FROM riftbound.rbusers WHERE id = 1'))
    assert rows('SELECT rbwls_user_id FROM riftbound.rbwishlists') == [(2,)]
    assert rows('SELECT rbwsl_name_key FROM riftbound.rbwishlistlines') == [('c',)]
    assert rows('SELECT rbwal_user_id FROM riftbound.rbwishlistalerts') == [(2,)]


def test_round_trip_leaves_the_other_tables_and_data_alone_and_has_no_drift(migration_app):
    upgrade(BEFORE)
    before = tables()
    run(USER, id=1, name='ana')
    run("INSERT INTO riftbound.rbset (rbset_id, rbset_name) VALUES ('OGN', 'Origins')")
    run("INSERT INTO riftbound.rbcards (rbcar_rbset_id, rbcar_id, rbcar_name) "
        "VALUES ('OGN', '1', 'Alpha')")
    run(COLLECTION)
    upgrade(REVISION)           # 0028 (F11-f) drops rbdecks: compare the tables at 0026
    assert tables() == before | NEW_TABLES
    run(LIST, **_list())
    run(LINE, **_line())
    run(ALERT, **_alert())
    downgrade(BEFORE)
    assert tables() == before
    assert rows('SELECT username FROM riftbound.rbusers') == [('ana',)]
    assert rows('SELECT rbcol_id, rbcol_user, rbcol_quantity FROM riftbound.rbcollection') == [
        (7, 'ana', 3)]
    upgrade()
    assert NEW_TABLES <= tables()
    assert rows('SELECT COUNT(*) FROM riftbound.rbwishlists') == [(0,)]
    assert drift() == []


def test_the_revision_chains_and_states_the_data_loss():
    versions = Path(__file__).resolve().parents[1] / 'migrations' / 'versions'
    spec = importlib.util.spec_from_file_location('m_0026', versions / f'{REVISION}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert (module.revision, module.down_revision) == (REVISION, BEFORE)
    assert "drops every user's wishlists, their lines and their alerts" in ' '.join(
        module.__doc__.split())
