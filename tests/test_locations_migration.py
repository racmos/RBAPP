"""F16-a S1, S2 (AC1): migration `0024_locations`: both tables, their named constraints,
the case-insensitive unique code per owner, cascades, round trip and drift."""
import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from tests.migration_helpers import downgrade, drift, inspector, rows, run, tables, upgrade

BEFORE = '0023_card_changes_obsolete'
REVISION = '0024_locations'
USER = ("INSERT INTO riftbound.rbusers (id, username, email, password_hash, is_admin, is_blocked, "
        "failed_login_count) VALUES (:id, :name, :name || '@test.com', 'x', 0, 0, 0)")
LOCATION = ("INSERT INTO riftbound.rblocations (rbloc_user, rbloc_code, rbloc_description, "
            "rbloc_position, rbloc_updated_at) VALUES (:user, :code, NULL, :pos, "
            "'2030-01-01 12:00:00')")
LINE = ("INSERT INTO riftbound.rbcollection (rbcol_id, rbcol_rbset_id, rbcol_rbcar_id, rbcol_foil, "
        "rbcol_user, rbcol_quantity, rbcol_selling, rbcol_sell_qty, rbcol_chadat) "
        "VALUES (:id, 'OGN', '1', 'N', :user, :qty, 'N', 0, '2030-01-01 12:00:00')")
ASSIGN = ("INSERT INTO riftbound.rbcollection_locations (rbcll_line_id, rbcll_location_id, "
          "rbcll_qty) VALUES (:line, :loc, :qty)")


def _exec(conn, sql, **params):
    conn.execute(sa.text(sql), params)


def _seed(conn):
    conn.exec_driver_sql('PRAGMA foreign_keys=ON')    # SQLite enforces FKs only when asked
    _exec(conn, USER, id=1, name='ana')
    _exec(conn, USER, id=2, name='bo')
    _exec(conn, "INSERT INTO riftbound.rbset (rbset_id, rbset_name) VALUES ('OGN', 'Origins')")
    _exec(conn, "INSERT INTO riftbound.rbcards (rbcar_rbset_id, rbcar_id, rbcar_name) "
                "VALUES ('OGN', '1', 'Alpha')")


def test_the_tables_have_their_named_constraints_and_indexes(migration_app):
    upgrade(REVISION)
    assert {'rblocations', 'rbcollection_locations'} <= tables()
    insp = inspector()
    assert insp.get_pk_constraint('rblocations', schema='riftbound') == {
        'name': 'rblocations_pkey', 'constrained_columns': ['rbloc_id']}
    assert insp.get_pk_constraint('rbcollection_locations', schema='riftbound') == {
        'name': 'rbcollection_locations_pkey',
        'constrained_columns': ['rbcll_line_id', 'rbcll_location_id']}
    fks = sorted((fk['name'], fk['referred_table'], fk['options'].get('ondelete'))
                 for table in ('rblocations', 'rbcollection_locations')
                 for fk in insp.get_foreign_keys(table, schema='riftbound'))
    assert fks == [('rbcollection_locations_line_fk', 'rbcollection', 'CASCADE'),
                   ('rbcollection_locations_location_fk', 'rblocations', 'CASCADE'),
                   ('rblocations_user_fk', 'rbusers', 'CASCADE')]
    assert {c['name'] for c in insp.get_check_constraints('rblocations', schema='riftbound')} == {
        'rblocations_code_chk', 'rblocations_position_chk'}
    assert {c['name'] for c in insp.get_check_constraints(
        'rbcollection_locations', schema='riftbound')} == {'rbcollection_locations_qty_chk'}
    uniques = {u['name']: u['column_names']
               for u in insp.get_unique_constraints('rblocations', schema='riftbound')}
    assert uniques == {'rblocations_user_position_uq': ['rbloc_user', 'rbloc_position'],
                       'rblocations_deck_uq': ['rbloc_deck_id']}
    assert 'ix_rbcollection_locations_location' in {
        i['name'] for i in insp.get_indexes('rbcollection_locations', schema='riftbound')}
    # SQLAlchemy cannot reflect expression indexes on SQLite: read the DDL itself.
    ddl = rows("SELECT sql FROM riftbound.sqlite_master WHERE name = 'rblocations_user_code_uq'")
    assert ddl == [('CREATE UNIQUE INDEX rblocations_user_code_uq ON rblocations '
                    '(rbloc_user, lower(rbloc_code))',)]


def test_the_code_is_unique_per_owner_ignoring_case(migration_app):
    upgrade(REVISION)
    from app import db
    with db.engine.begin() as conn:
        _seed(conn)
        _exec(conn, LOCATION, user='ana', code='B001-F001-P0001', pos=1)
        _exec(conn, LOCATION, user='bo', code='b001-f001-p0001', pos=1)
    with pytest.raises(IntegrityError):
        run(LOCATION, user='ana', code='b001-F001-p0001', pos=2)
    assert rows('SELECT rbloc_user, rbloc_code FROM riftbound.rblocations ORDER BY rbloc_id') == [
        ('ana', 'B001-F001-P0001'), ('bo', 'b001-f001-p0001')]


@pytest.mark.parametrize('code', ['', 'a b', 'ab_c', 'ñu', 'x' * 33])
def test_the_code_check_refuses_other_characters_and_lengths(migration_app, code):
    upgrade(REVISION)
    run(USER, id=1, name='ana')
    with pytest.raises(IntegrityError):
        run(LOCATION, user='ana', code=code, pos=1)
    run(LOCATION, user='ana', code='DECK-001', pos=1)
    run(LOCATION, user='ana', code='x' * 32, pos=2)
    assert len(rows('SELECT rbloc_id FROM riftbound.rblocations')) == 2


def test_position_and_qty_checks_and_defaults(migration_app):
    upgrade(REVISION)
    from app import db
    with db.engine.begin() as conn:
        _seed(conn)
        _exec(conn, LOCATION, user='ana', code='A', pos=1)
        _exec(conn, LINE, id=7, user='ana', qty=3)
    for sql, params in ((LOCATION, dict(user='ana', code='B', pos=0)),
                        (LOCATION, dict(user='ana', code='C', pos=1)),
                        (ASSIGN, dict(line=7, loc=1, qty=0))):
        with pytest.raises(IntegrityError):
            run(sql, **params)
    run(ASSIGN, line=7, loc=1, qty=2)
    assert rows('SELECT rbloc_locked, rbloc_deck_id FROM riftbound.rblocations') == [(0, None)]
    assert rows('SELECT rbcll_qty FROM riftbound.rbcollection_locations') == [(2,)]


def test_deleting_a_line_or_a_location_deletes_its_assignments(migration_app):
    upgrade(REVISION)
    from app import db
    with db.engine.begin() as conn:
        _seed(conn)
        _exec(conn, LOCATION, user='ana', code='A', pos=1)
        _exec(conn, LOCATION, user='ana', code='B', pos=2)
        _exec(conn, LINE, id=7, user='ana', qty=3)
        _exec(conn, LINE, id=8, user='ana', qty=3)
        _exec(conn, ASSIGN, line=7, loc=1, qty=1)
        _exec(conn, ASSIGN, line=8, loc=1, qty=1)
        _exec(conn, ASSIGN, line=8, loc=2, qty=1)
        _exec(conn, 'DELETE FROM riftbound.rbcollection WHERE rbcol_id = 7')
        _exec(conn, 'DELETE FROM riftbound.rblocations WHERE rbloc_id = 2')
    assert rows('SELECT rbcll_line_id, rbcll_location_id FROM riftbound.rbcollection_locations'
                ) == [(8, 1)]


def test_round_trip_and_drift(migration_app):
    upgrade()
    assert drift() == []
    run(USER, id=1, name='ana')
    run(LOCATION, user='ana', code='A', pos=1)
    downgrade(BEFORE)
    assert not {'rblocations', 'rbcollection_locations'} & tables()
    assert rows('SELECT username FROM riftbound.rbusers') == [('ana',)]
    upgrade()
    assert {'rblocations', 'rbcollection_locations'} <= tables()
    assert rows('SELECT COUNT(*) FROM riftbound.rblocations') == [(0,)]
    assert drift() == []


def test_the_revision_chains_and_states_the_data_loss():
    versions = Path(__file__).resolve().parents[1] / 'migrations' / 'versions'
    spec = importlib.util.spec_from_file_location('m_0024', versions / f'{REVISION}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert (module.revision, module.down_revision) == (REVISION, BEFORE)
    assert "drops every user's locations" in ' '.join(module.__doc__.split())
