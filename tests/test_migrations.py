"""
Migration tests (unit b, specs MIG-1..9 and QTY-1).

Everything here runs on in-memory SQLite with a `riftbound` schema attached
(exactly like the app tests); PostgreSQL-only checks live in
`tests/test_migrations_pg.py` behind the `postgres` marker.
"""
import logging
import os
import re
import stat
import subprocess
from datetime import datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.pool import StaticPool

from app import db
from app.models import RbCollection, RbDeck
from tests.migration_helpers import (
    alembic, checked_test_database_url, downgrade, drift, inspector, rows, run, tables,
    upgrade)
from tests.snapshot_utils import load_snapshot

ROOT = Path(__file__).resolve().parent.parent

BASELINE = '0001_baseline'


def _sqlite_engine():
    """In-memory SQLite, one shared connection, `riftbound` attached."""
    engine = sa.create_engine(
        'sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
    with engine.begin() as conn:
        # create_app() installs a global Engine 'connect' hook that may have
        # attached `riftbound` already; attach only when it is missing.
        attached = {r[1] for r in conn.exec_driver_sql('PRAGMA database_list')}
        if 'riftbound' not in attached:
            conn.exec_driver_sql('ATTACH DATABASE ":memory:" AS riftbound')
    return engine


# --- 2.3 SPIKE: can batch_alter_table repoint a named FK on SQLite? (D7) ------

def test_batch_fk_change_sqlite():
    engine = _sqlite_engine()
    with engine.begin() as conn:
        conn.exec_driver_sql(
            'CREATE TABLE riftbound.old1_rbusers ('
            ' rbus_id INTEGER PRIMARY KEY, rbus_username VARCHAR(80) NOT NULL UNIQUE)')
        conn.exec_driver_sql(
            'CREATE TABLE riftbound.rbusers ('
            ' id INTEGER PRIMARY KEY, username VARCHAR(64) NOT NULL UNIQUE)')
        conn.exec_driver_sql(
            'CREATE TABLE riftbound.rbdecks ('
            ' id INTEGER PRIMARY KEY, rbdck_user VARCHAR(80) NOT NULL,'
            ' rbdck_name VARCHAR(200) NOT NULL, rbdck_seq TEXT NOT NULL,'
            ' CONSTRAINT fk_deck_user FOREIGN KEY (rbdck_user)'
            '  REFERENCES old1_rbusers (rbus_username))')
        conn.exec_driver_sql(
            "INSERT INTO riftbound.rbusers (id, username) VALUES (1, 'alice')")
        conn.exec_driver_sql(
            "INSERT INTO riftbound.rbdecks (id, rbdck_user, rbdck_name, rbdck_seq)"
            " VALUES (1, 'alice', 'Foo', '7')")

        ops = Operations(MigrationContext.configure(
            conn, opts={'version_table_schema': 'riftbound'}))
        with ops.batch_alter_table('rbdecks', schema='riftbound') as batch:
            batch.drop_constraint('fk_deck_user', type_='foreignkey')
            batch.create_foreign_key(
                'fk_deck_user', 'rbusers', ['rbdck_user'], ['username'],
                referent_schema='riftbound', onupdate='CASCADE', ondelete='RESTRICT')
            batch.alter_column('rbdck_seq', existing_type=sa.Text(),
                               type_=sa.Integer(), existing_nullable=False)

        insp = sa.inspect(conn)
        fks = insp.get_foreign_keys('rbdecks', schema='riftbound')
        assert len(fks) == 1
        assert fks[0]['name'] == 'fk_deck_user'
        assert fks[0]['referred_table'] == 'rbusers'
        assert fks[0]['referred_columns'] == ['username']
        assert fks[0]['options'].get('onupdate') == 'CASCADE'
        assert fks[0]['options'].get('ondelete') == 'RESTRICT'

        cols = {c['name']: c for c in insp.get_columns('rbdecks', schema='riftbound')}
        assert isinstance(cols['rbdck_seq']['type'], sa.Integer)
        assert cols['rbdck_seq']['nullable'] is False
        # data survived the table rebuild and was cast
        row = conn.exec_driver_sql(
            'SELECT rbdck_user, rbdck_name, rbdck_seq FROM riftbound.rbdecks').one()
        assert tuple(row) == ('alice', 'Foo', 7)


# --- 2.5 Layout (MIG-8, MIG-4 ignored path) ---------------------------------

class TestLayout:
    def test_legacy_sql_is_archived_with_a_readme(self):
        legacy = ROOT / 'migrations' / 'legacy_sql'
        assert (legacy / 'install_db.sql').is_file()
        assert (legacy / 'README.md').is_file()
        assert (legacy / 'database' / '01_create_tables.sql').is_file()
        assert (legacy / 'database_setup.sql').is_file()
        assert 'frozen' in (legacy / 'README.md').read_text().lower()

    def test_old_locations_are_gone(self):
        assert not (ROOT / 'migrations' / 'database').exists()
        assert not (ROOT / 'migrations' / 'install_db.sql').exists()
        assert not (ROOT / 'docs' / 'database_setup.sql').exists()

    def test_run_py_does_not_create_tables(self):
        assert 'create_all' not in (ROOT / 'run.py').read_text()

    @pytest.mark.parametrize('path', [
        'instance/backups/x.sql',                                   # default directory
        'somewhere/else/legacy_tables_20261018T201500Z.sql',        # RB_LEGACY_BACKUP_DIR inside the repo
    ])
    def test_backup_path_is_git_ignored(self, path):
        result = subprocess.run(['git', 'check-ignore', '-q', path], cwd=ROOT, capture_output=True)
        assert result.returncode == 0

    def test_ignore_rules_do_not_hide_the_migrations_themselves(self):
        for path in ('migrations/versions/0004_x.py', 'migrations/legacy_sql/install_db.sql',
                     'tests/fixtures/dev_schema_snapshot.txt'):
            result = subprocess.run(['git', 'check-ignore', '-q', path], cwd=ROOT,
                                    capture_output=True)
            assert result.returncode == 1, path


# --- 2.10 Revision 0001: baseline equals the dev snapshot (MIG-1, MIG-2) -----

SNAPSHOT = load_snapshot()
CORE = ['rbset', 'rbusers', 'rbcards', 'rbcardmarket', 'rbproducts']
COLLECTION_DECKS_LEGACY = ['rbcollection', 'rbdecks', 'old1_rbusers', 'old_rbdecks']
CARDMARKET = ['rbcm_categories', 'rbcm_expansions', 'rbcm_ignored',
              'rbcm_load_history', 'rbcm_price', 'rbcm_product_card_map',
              'rbcm_products']


@pytest.fixture
def baseline(migration_app):
    upgrade(BASELINE)
    return migration_app


def _type_matches(reflected, snapshot_type):
    """Loose, dialect-neutral type check: kind, plus length for varchar."""
    if snapshot_type == 'text':
        return isinstance(reflected, sa.Text)
    if snapshot_type.startswith('character varying'):
        length = int(snapshot_type[snapshot_type.index('(') + 1:-1])
        return (isinstance(reflected, sa.String) and not isinstance(reflected, sa.Text)
                and reflected.length == length)
    kinds = {
        'integer': sa.Integer, 'smallint': sa.Integer, 'bigint': sa.Integer,
        'numeric': sa.Numeric, 'date': sa.Date, 'jsonb': sa.JSON,
        'timestamp without time zone': sa.DateTime,
    }
    return isinstance(reflected, kinds[snapshot_type])


class TestBaselineVersioning:
    def test_upgrade_records_the_revision_inside_riftbound(self, baseline):
        assert 'alembic_version' in tables()
        assert rows('SELECT version_num FROM riftbound.alembic_version') == [(BASELINE,)]

    def test_creates_the_16_snapshot_tables_and_nothing_else(self, baseline):
        assert tables() - {'alembic_version'} == set(SNAPSHOT)
        assert len(SNAPSHOT) == 16

    def test_upgrade_does_not_touch_the_default_schema(self, baseline):
        # main (SQLite's default schema) stays empty: everything is riftbound.*
        assert inspector().get_table_names() == []


@pytest.mark.parametrize('family', [CORE, COLLECTION_DECKS_LEGACY, CARDMARKET],
                         ids=['core', 'collection-decks-legacy', 'cardmarket'])
class TestBaselineMatchesSnapshot:
    def test_columns_in_order_with_types_and_nullability(self, baseline, family):
        for name in family:
            want = SNAPSHOT[name].columns
            got = inspector().get_columns(name, schema='riftbound')
            assert [c['name'] for c in got] == [c.name for c in want], name
            for col, ref in zip(want, got):
                assert ref['nullable'] is (not col.notnull), f'{name}.{col.name}'
                assert _type_matches(ref['type'], col.type), f'{name}.{col.name}: {ref["type"]}'

    def test_server_defaults_present_exactly_where_dev_has_them(self, baseline, family):
        for name in family:
            for col, ref in zip(SNAPSHOT[name].columns,
                                inspector().get_columns(name, schema='riftbound')):
                if col.default is None or 'nextval' in col.default:
                    assert ref['default'] is None, f'{name}.{col.name}'
                else:
                    assert ref['default'] is not None, f'{name}.{col.name}'

    def test_keys_constraints_and_indexes_keep_their_dev_names(self, baseline, family):
        insp = inspector()
        for name in family:
            want = SNAPSHOT[name]
            pk = insp.get_pk_constraint(name, schema='riftbound')
            assert (pk['name'], pk['constrained_columns']) == want.primary_key, name
            uniques = {u['name']: u['column_names']
                       for u in insp.get_unique_constraints(name, schema='riftbound')}
            assert uniques == want.uniques, name
            fks = {f['name']: dict(
                columns=f['constrained_columns'], table=f['referred_table'],
                refs=f['referred_columns'],
                onupdate=f['options'].get('onupdate'),
                ondelete=f['options'].get('ondelete'))
                for f in insp.get_foreign_keys(name, schema='riftbound')}
            assert fks == want.foreign_keys, name
            checks = {c['name'] for c in insp.get_check_constraints(name, schema='riftbound')}
            assert checks == set(want.checks), name
            # explicit indexes only: PK / UNIQUE backing indexes carry the constraint name
            constraint_names = {want.primary_key[0], *want.uniques}
            explicit = {n: i for n, i in want.indexes.items() if n not in constraint_names}
            got = {i['name']: i['column_names']
                   for i in insp.get_indexes(name, schema='riftbound')}
            assert got == {n: i['columns'] for n, i in explicit.items()}, name


class TestBaselineSpecScenarios:
    def test_named_indexes_exist(self, baseline):
        names = {i['name'] for t in ('rbcollection', 'rbcm_expansions')
                 for i in inspector().get_indexes(t, schema='riftbound')}
        assert {'idx_rbcollection_selling', 'idx_rbcollection_user_card_foil',
                'idx_rbcm_expansions_unmapped'} <= names

    def test_partial_index_only_covers_unmapped_expansions(self, baseline):
        run("INSERT INTO riftbound.rbcm_expansions (rbexp_id, rbexp_name, rbexp_rbset_id)"
            " VALUES (1, 'a', NULL), (2, 'b', 'OGN')")
        plan = ' '.join(str(r) for r in rows(
            "EXPLAIN QUERY PLAN SELECT rbexp_id FROM riftbound.rbcm_expansions"
            " WHERE rbexp_rbset_id IS NULL"))
        assert 'idx_rbcm_expansions_unmapped' in plan

    def test_no_foreign_keys_the_snapshot_lacks(self, baseline):
        for name in ('rbcm_product_card_map', 'rbproducts'):
            assert inspector().get_foreign_keys(name, schema='riftbound') == []

    def test_rbdecks_user_fk_points_at_the_legacy_users_table(self, baseline):
        [fk] = inspector().get_foreign_keys('rbdecks', schema='riftbound')
        assert (fk['name'], fk['referred_table'], fk['referred_columns']) == (
            'fk_deck_user', 'old1_rbusers', ['rbus_username'])

    @pytest.mark.parametrize('selling,playset', [("'X'", 'NULL'), ("'N'", '4'), ("'N'", '0')])
    def test_collection_checks_reject_bad_values(self, baseline, selling, playset):
        with pytest.raises(sa.exc.IntegrityError):
            run(COLLECTION_INSERT.format(selling=selling, playset=playset))
        assert rows('SELECT count(*) FROM riftbound.rbcollection') == [(0,)]

    @pytest.mark.parametrize('selling,playset', [("'S'", '3'), ("'Y'", '1'), ("'N'", 'NULL')])
    def test_collection_checks_accept_good_values(self, baseline, selling, playset):
        run(COLLECTION_INSERT.format(selling=selling, playset=playset))
        assert rows('SELECT count(*) FROM riftbound.rbcollection') == [(1,)]

    @pytest.mark.parametrize('foil,ok', [('N', True), ('S', True), (None, True), ('X', False)])
    def test_card_map_foil_check(self, baseline, foil, ok):
        sql = ("INSERT INTO riftbound.rbcm_product_card_map "
               "(rbpcm_rbset_id, rbpcm_rbcar_id, rbpcm_foil) VALUES ('OGN', '1', :foil)")
        if ok:
            run(sql, foil=foil)
            assert rows('SELECT rbpcm_foil FROM riftbound.rbcm_product_card_map') == [(foil,)]
        else:
            with pytest.raises(sa.exc.IntegrityError):
                run(sql, foil=foil)


COLLECTION_INSERT = (
    "INSERT INTO riftbound.rbcollection (rbcol_rbset_id, rbcol_rbcar_id, rbcol_foil,"
    " rbcol_quantity, rbcol_chadat, rbcol_user, rbcol_selling, rbcol_playset)"
    " VALUES ('OGN', '1', 'N', '3', '2026-01-01 00:00:00', 'alice', {selling}, {playset})")


# --- 2.14 Revision 0002: legacy tables are backed up, then dropped -----------
# (MIG-4, MIG-5)

DROP_LEGACY = '0002_drop_legacy_tables'

NASTY_DESCRIPTION = "O'Brien's deck\nsecond line; with semicolon -- and \\ backslash, Ñandú"


def seed_users(*names):
    """rbusers rows (the live table) for `names`."""
    for i, name in enumerate(names, start=1):
        run("INSERT INTO riftbound.rbusers (id, username, email, password_hash)"
            " VALUES (:id, :u, :e, 'live-hash')", id=i, u=name, e=f'{name}@live.io')


def seed_legacy(users=(), decks=()):
    """Rows for the legacy tables at revision 0001.

    users: usernames for old1_rbusers (email/hash derive from the name).
    decks: (user, name) pairs for old_rbdecks, one card row each."""
    for i, name in enumerate(users, start=1):
        run("INSERT INTO riftbound.old1_rbusers"
            " (rbus_id, rbus_username, rbus_email, rbus_password)"
            " VALUES (:id, :u, :e, :h)", id=i, u=name, e=f'{name}@old.io', h=f'old-hash-{name}')
    for i, (user, name) in enumerate(decks, start=1):
        run("INSERT INTO riftbound.old_rbdecks (rbdck_snapshot, rbdck_name, rbdck_decription,"
            " rbdck_max_set, rbdck_rbset_id, rbdck_rbcar_id, rbdck_user, rbdck_orden,"
            " rbdck_ncards) VALUES ('2026-01-0%d 10:00:00', :n, :d, 'OGN', 'OGN', :c, :u, :o, 2.5)"
            % i, n=name, d=NASTY_DESCRIPTION if i == 1 else None,
            c=str(i), u=user, o=i)


def seed_live_deck(user, name, seq=1):
    run("INSERT INTO riftbound.rbdecks (rbdck_user, rbdck_name, rbdck_seq) VALUES (:u, :n, :s)",
        u=user, n=name, s=seq)


def backups(app):
    folder = Path(app.config['LEGACY_BACKUP_DIR'])
    return sorted(folder.glob('legacy_tables_*.sql')) if folder.exists() else []


def _normalise(value):
    """SQLite hands timestamps back as TEXT and the backup rewrites them with
    microseconds ('...:00' vs '...:00.000000'): compare them as datetimes."""
    if isinstance(value, str) and re.fullmatch(r'\d{4}-\d\d-\d\d \d\d:\d\d:\d\d(\.\d+)?', value):
        return datetime.fromisoformat(value)
    return value


def snapshot_legacy():
    return {t: [tuple(_normalise(v) for v in row)
                for row in rows(f'SELECT * FROM riftbound.{t} ORDER BY 1, 2, 3, 4')]
            for t in ('old1_rbusers', 'old_rbdecks')}


@pytest.fixture
def at_baseline(migration_app):
    upgrade(BASELINE)
    return migration_app


class TestBackupThenDrop:
    def test_backup_file_has_all_rows_and_the_tables_are_gone(self, at_baseline):
        seed_users('alice', 'bob')
        seed_legacy(users=['alice', 'bob'],
                    decks=[('alice', 'Foo'), ('alice', 'Bar'), ('bob', 'Foo')])
        seed_live_deck('alice', 'Foo')

        upgrade(DROP_LEGACY)

        [backup] = backups(at_baseline)
        text = backup.read_text(encoding='utf-8')
        assert text.count('INSERT INTO') == 5
        for needle in ('alice@old.io', 'old-hash-bob', 'Bar'):
            assert needle in text
        assert not {'old1_rbusers', 'old_rbdecks'} & tables()
        assert rows('SELECT version_num FROM riftbound.alembic_version') == [(DROP_LEGACY,)]

    def test_backup_file_is_private_to_the_owner(self, at_baseline):
        seed_users('alice')
        seed_legacy(users=['alice'])
        upgrade(DROP_LEGACY)
        [backup] = backups(at_baseline)
        assert stat.S_IMODE(backup.stat().st_mode) == 0o600
        assert stat.S_IMODE(backup.parent.stat().st_mode) == 0o700

    def test_no_file_is_written_when_the_legacy_tables_are_empty(self, at_baseline):
        upgrade(DROP_LEGACY)
        assert backups(at_baseline) == []
        assert not {'old1_rbusers', 'old_rbdecks'} & tables()

    def test_only_users_present_still_counts_as_rows(self, at_baseline):
        seed_users('alice')
        seed_legacy(users=['alice'])
        upgrade(DROP_LEGACY)
        [backup] = backups(at_baseline)
        assert backup.read_text().count('INSERT INTO') == 1


class TestMissingDeckWarning:
    def test_warns_for_a_legacy_deck_absent_from_rbdecks_and_completes(
            self, at_baseline, caplog):
        seed_users('u', 'w')
        seed_legacy(users=['u', 'w'], decks=[('u', 'Foo'), ('w', 'Kept')])
        seed_live_deck('w', 'Kept')

        with caplog.at_level(logging.WARNING):
            upgrade(DROP_LEGACY)

        warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        assert any('u/Foo' in m for m in warnings)
        assert not any('w/Kept' in m for m in warnings)
        assert rows('SELECT version_num FROM riftbound.alembic_version') == [(DROP_LEGACY,)]

    def test_one_warning_per_deck_not_per_card_row(self, at_baseline, caplog):
        seed_users('u')
        seed_legacy(users=['u'], decks=[('u', 'Foo')])
        run("INSERT INTO riftbound.old_rbdecks (rbdck_snapshot, rbdck_name, rbdck_max_set,"
            " rbdck_rbset_id, rbdck_rbcar_id, rbdck_user, rbdck_orden)"
            " VALUES ('2026-01-01 10:00:00', 'Foo', 'OGN', 'OGN', '99', 'u', 2)")
        with caplog.at_level(logging.WARNING):
            upgrade(DROP_LEGACY)
        assert sum('u/Foo' in r.getMessage() for r in caplog.records) == 1


class TestAbortsLeaveEverythingIntact:
    def test_unwritable_backup_directory_aborts_before_any_drop(self, at_baseline, tmp_path):
        if os.geteuid() == 0:
            pytest.skip('root can write anywhere')
        locked = tmp_path / 'locked'
        locked.mkdir(mode=0o500)
        at_baseline.config['LEGACY_BACKUP_DIR'] = str(locked / 'backups')
        seed_users('alice')
        seed_legacy(users=['alice'], decks=[('alice', 'Foo')])
        before = snapshot_legacy()
        try:
            with pytest.raises(RuntimeError, match='backup'):
                upgrade(DROP_LEGACY)
        finally:
            locked.chmod(0o700)
        assert {'old1_rbusers', 'old_rbdecks'} <= tables()
        assert snapshot_legacy() == before
        [fk] = inspector().get_foreign_keys('rbdecks', schema='riftbound')
        assert fk['referred_table'] == 'old1_rbusers'
        assert rows('SELECT version_num FROM riftbound.alembic_version') == [(BASELINE,)]

    def test_orphan_deck_owner_aborts_naming_the_user(self, at_baseline):
        seed_users('alice')
        seed_legacy(users=['alice', 'ghost'])
        seed_live_deck('alice', 'Fine')
        seed_live_deck('ghost', 'Lost')
        with pytest.raises(RuntimeError, match='ghost'):
            upgrade(DROP_LEGACY)
        assert rows('SELECT rbdck_user, rbdck_name FROM riftbound.rbdecks ORDER BY id') == [
            ('alice', 'Fine'), ('ghost', 'Lost')]
        [fk] = inspector().get_foreign_keys('rbdecks', schema='riftbound')
        assert fk['referred_table'] == 'old1_rbusers'
        assert {'old1_rbusers', 'old_rbdecks'} <= tables()
        assert backups(at_baseline) == []          # nothing written before the check

    def test_orphan_message_lists_every_orphan(self, at_baseline):
        seed_users('alice')
        seed_live_deck('ghost', 'A')
        seed_live_deck('phantom', 'B')
        with pytest.raises(RuntimeError) as err:
            upgrade(DROP_LEGACY)
        assert 'ghost' in str(err.value) and 'phantom' in str(err.value)
        assert 'alice' not in str(err.value)

    def test_offline_sql_mode_is_refused(self, at_baseline, capsys):
        with pytest.raises(RuntimeError, match='offline'):
            alembic('upgrade', f'{BASELINE}:{DROP_LEGACY}', sql=True)
        assert 'DROP TABLE' not in capsys.readouterr().out


class TestDecksUserForeignKey:
    def test_head_points_rbdecks_at_rbusers_and_nothing_at_old1(self, migration_app):
        upgrade()
        fks = inspector().get_foreign_keys('rbdecks', schema='riftbound')
        assert [(f['name'], f['referred_table'], f['referred_columns'],
                 f['options'].get('onupdate'), f['options'].get('ondelete')) for f in fks] == [
            ('fk_deck_user', 'rbusers', ['username'], 'CASCADE', 'RESTRICT')]
        for table in tables() - {'alembic_version'}:
            assert all(f['referred_table'] != 'old1_rbusers'
                       for f in inspector().get_foreign_keys(table, schema='riftbound'))

    def test_repoint_keeps_deck_rows(self, at_baseline):
        seed_users('alice')
        seed_legacy(users=['alice'])
        seed_live_deck('alice', 'Foo', seq=1)
        seed_live_deck('alice', 'Foo', seq=2)
        upgrade(DROP_LEGACY)
        assert rows('SELECT rbdck_user, rbdck_name, rbdck_seq FROM riftbound.rbdecks'
                    ' ORDER BY id') == [('alice', 'Foo', 1), ('alice', 'Foo', 2)]


class TestDowngradeRestores:
    def test_tables_come_back_with_the_original_rows(self, at_baseline):
        seed_users('alice', 'bob')
        seed_legacy(users=['alice', 'bob'],
                    decks=[('alice', 'Foo'), ('alice', 'Bar'), ('bob', 'Foo')])
        seed_live_deck('alice', 'Foo')
        before = snapshot_legacy()
        assert len(before['old1_rbusers']) == 2 and len(before['old_rbdecks']) == 3

        upgrade(DROP_LEGACY)
        assert not {'old1_rbusers', 'old_rbdecks'} & tables()
        downgrade(BASELINE)

        assert {'old1_rbusers', 'old_rbdecks'} <= tables()
        assert snapshot_legacy() == before
        [fk] = inspector().get_foreign_keys('rbdecks', schema='riftbound')
        assert (fk['referred_table'], fk['referred_columns']) == ('old1_rbusers', ['rbus_username'])
        assert fk['options'] == {}
        # the awkward text survived the SQL round trip untouched
        assert rows("SELECT rbdck_decription FROM riftbound.old_rbdecks"
                    " WHERE rbdck_decription IS NOT NULL") == [(NASTY_DESCRIPTION,)]

    def test_replays_the_newest_backup_only(self, at_baseline):
        seed_users('alice')
        seed_legacy(users=['alice'])
        folder = Path(at_baseline.config['LEGACY_BACKUP_DIR'])
        folder.mkdir(parents=True)
        (folder / 'legacy_tables_20200101T000000Z.sql').write_text(
            "INSERT INTO riftbound.old1_rbusers (rbus_id, rbus_username, rbus_email,"
            " rbus_password) VALUES (99, 'stale', 'stale@old.io', 'x');\n")

        upgrade(DROP_LEGACY)
        downgrade(BASELINE)

        assert rows('SELECT rbus_username FROM riftbound.old1_rbusers') == [('alice',)]

    def test_empty_legacy_tables_come_back_empty(self, at_baseline):
        upgrade(DROP_LEGACY)
        downgrade(BASELINE)
        assert {'old1_rbusers', 'old_rbdecks'} <= tables()
        assert rows('SELECT count(*) FROM riftbound.old1_rbusers') == [(0,)]
        assert rows('SELECT count(*) FROM riftbound.old_rbdecks') == [(0,)]


# --- 2.17 Revision 0003: rbcol_quantity Text -> Integer (QTY-1) ---------------

QUANTITY = '0003_collection_quantity_integer'


def seed_collection(*quantities):
    """One rbcollection line per quantity (stored exactly as given); returns the ids."""
    ids = []
    for i, quantity in enumerate(quantities, start=1):
        run("INSERT INTO riftbound.rbcollection (rbcol_id, rbcol_rbset_id, rbcol_rbcar_id,"
            " rbcol_foil, rbcol_quantity, rbcol_chadat, rbcol_user, rbcol_selling)"
            " VALUES (:id, 'OGN', :card, 'N', :q, '2026-01-01 00:00:00.000000', 'alice', 'N')",
            id=i, card=str(i), q=quantity)
        ids.append(i)
    return ids


def quantity_column():
    [col] = [c for c in inspector().get_columns('rbcollection', schema='riftbound')
             if c['name'] == 'rbcol_quantity']
    return col


@pytest.fixture
def at_drop_legacy(migration_app):
    upgrade(DROP_LEGACY)
    return migration_app


class TestQuantityDataIsConverted:
    @pytest.mark.parametrize('stored,expected', [
        ('12', 12), (' 3 ', 3), ('1', 1), ('9999', 9999), ('0012', 12)])
    def test_text_becomes_the_integer(self, at_drop_legacy, stored, expected):
        seed_collection(stored)
        upgrade(QUANTITY)
        assert rows('SELECT rbcol_quantity, typeof(rbcol_quantity) FROM riftbound.rbcollection') == [
            (expected, 'integer')]
        col = quantity_column()
        assert isinstance(col['type'], sa.Integer)
        assert col['nullable'] is False

    def test_all_other_columns_survive_the_table_rebuild(self, at_drop_legacy):
        seed_collection('12', ' 3 ')
        before = rows('SELECT rbcol_id, rbcol_rbset_id, rbcol_rbcar_id, rbcol_foil, rbcol_chadat,'
                      ' rbcol_user, rbcol_selling FROM riftbound.rbcollection ORDER BY rbcol_id')
        upgrade(QUANTITY)
        assert rows('SELECT rbcol_id, rbcol_rbset_id, rbcol_rbcar_id, rbcol_foil, rbcol_chadat,'
                    ' rbcol_user, rbcol_selling FROM riftbound.rbcollection ORDER BY rbcol_id') == before
        assert rows('SELECT rbcol_quantity FROM riftbound.rbcollection ORDER BY rbcol_id') == [(12,), (3,)]

    def test_constraints_and_indexes_are_kept(self, at_drop_legacy):
        upgrade(QUANTITY)
        insp = inspector()
        assert {i['name'] for i in insp.get_indexes('rbcollection', schema='riftbound')} == {
            'idx_rbcollection_selling', 'idx_rbcollection_user_card_foil'}
        assert {f['name'] for f in insp.get_foreign_keys('rbcollection', schema='riftbound')} == {
            'rbcollection_rbcar_fk_1', 'rbcollection_user_fk_1'}
        assert {c['name'] for c in insp.get_check_constraints('rbcollection', schema='riftbound')} == {
            'rbcollection_playset_chk', 'rbcollection_selling_chk', 'rbcollection_quantity_chk'}
        pk = insp.get_pk_constraint('rbcollection', schema='riftbound')
        assert (pk['name'], pk['constrained_columns']) == ('rbcollection_pk', ['rbcol_id'])
        with pytest.raises(sa.exc.IntegrityError):
            run(COLLECTION_INSERT.format(selling="'X'", playset='NULL').replace("'3'", '3'))


def offending_ids(error):
    """The rbcol_ids named in the pre-flight error, e.g. '(offending rbcol_id): 2, 4.'"""
    found = re.search(r'rbcol_id\): ([\d, ]+)\.', str(error))
    assert found, str(error)
    return [int(n) for n in found.group(1).split(',')]


class TestQuantityPreflight:
    @pytest.mark.parametrize('bad', ['abc', '', '0', '10000', '  ', '-1', '1.5', '1e2', '\t3',
                                     '٣'])
    def test_bad_value_aborts_and_leaves_the_text_column(self, at_drop_legacy, bad):
        seed_collection('7', bad)
        with pytest.raises(RuntimeError) as err:
            upgrade(QUANTITY)
        assert offending_ids(err.value) == [2]
        assert isinstance(quantity_column()['type'], sa.Text)
        assert rows('SELECT rbcol_quantity, typeof(rbcol_quantity) FROM riftbound.rbcollection'
                    ' ORDER BY rbcol_id') == [('7', 'text'), (bad, 'text')]
        assert rows('SELECT version_num FROM riftbound.alembic_version') == [(DROP_LEGACY,)]

    def test_message_lists_every_offending_id_and_only_those(self, at_drop_legacy):
        seed_collection('5', 'abc', '8', '0', '10000')
        with pytest.raises(RuntimeError) as err:
            upgrade(QUANTITY)
        assert offending_ids(err.value) == [2, 4, 5]


class TestQuantityDowngrade:
    def test_back_to_text_with_trimmed_values(self, at_drop_legacy):
        seed_collection('12', ' 3 ')
        upgrade(QUANTITY)
        downgrade(DROP_LEGACY)
        assert isinstance(quantity_column()['type'], sa.Text)
        assert rows('SELECT rbcol_quantity, typeof(rbcol_quantity) FROM riftbound.rbcollection'
                    ' ORDER BY rbcol_id') == [('12', 'text'), ('3', 'text')]

    def test_check_is_gone_after_downgrade_and_back_at_head(self, at_drop_legacy):
        upgrade(QUANTITY)
        with pytest.raises(sa.exc.IntegrityError):
            run(COLLECTION_INSERT.format(selling="'N'", playset='NULL').replace("'3'", '0'))
        downgrade(DROP_LEGACY)
        assert 'rbcollection_quantity_chk' not in {
            c['name'] for c in inspector().get_check_constraints('rbcollection', schema='riftbound')}
        run(COLLECTION_INSERT.format(selling="'N'", playset='NULL').replace("'3'", "'0'"))
        assert rows('SELECT rbcol_quantity FROM riftbound.rbcollection') == [('0',)]


# --- 2.19 Models match the migrated schema (MIG-6, MIG-7) ---------------------


def models_copy():
    """A private copy of the models' metadata the test may mutate freely."""
    copy = sa.MetaData()
    for table in db.metadata.tables.values():
        table.to_metadata(copy)
    return copy


def describe(diff):
    """compare_metadata output as one readable string per operation."""
    return [repr(op) for item in diff for op in (item if isinstance(item, list) else [item])]


def structure():
    """Everything structural about the riftbound schema, comparable across runs."""
    insp = inspector()
    result = {}
    for table in sorted(tables() - {'alembic_version'}):
        schema = 'riftbound'
        result[table] = dict(
            columns=[(c['name'], str(c['type']), c['nullable'], str(c['default']))
                     for c in insp.get_columns(table, schema=schema)],
            pk=insp.get_pk_constraint(table, schema=schema),
            fks=sorted((f['name'], f['referred_table'], tuple(f['constrained_columns']),
                        tuple(f['referred_columns']), tuple(sorted(f['options'].items())))
                       for f in insp.get_foreign_keys(table, schema=schema)),
            uniques=sorted((u['name'], tuple(u['column_names']))
                           for u in insp.get_unique_constraints(table, schema=schema)),
            indexes=sorted((i['name'], tuple(i['column_names']), bool(i['unique']))
                           for i in insp.get_indexes(table, schema=schema)),
            checks=sorted(c['name'] for c in insp.get_check_constraints(table, schema=schema)),
        )
    return result


class TestDriftGuard:
    def test_models_equal_the_schema_at_head(self, migration_app):
        upgrade()
        assert drift() == []

    def test_constraint_and_index_names_in_models_equal_the_database(self, migration_app):
        # compare_metadata does not look at CHECKs and ignores some names, so
        # compare the declared names table by table.
        upgrade()
        insp = inspector()
        for name, table in db.metadata.tables.items():
            bare = table.name
            declared = dict(
                pk=[c.name for c in table.primary_key.columns],
                uniques={c.name for c in table.constraints if isinstance(c, sa.UniqueConstraint)},
                fks={c.name for c in table.constraints if isinstance(c, sa.ForeignKeyConstraint)},
                checks={c.name for c in table.constraints if isinstance(c, sa.CheckConstraint)},
                indexes={i.name for i in table.indexes},
            )
            actual = dict(
                pk=insp.get_pk_constraint(bare, schema='riftbound')['constrained_columns'],
                uniques={u['name'] for u in insp.get_unique_constraints(bare, schema='riftbound')},
                fks={f['name'] for f in insp.get_foreign_keys(bare, schema='riftbound')},
                checks={c['name'] for c in insp.get_check_constraints(bare, schema='riftbound')},
                indexes={i['name'] for i in insp.get_indexes(bare, schema='riftbound')},
            )
            assert declared == actual, name

    def test_every_model_table_exists_and_nothing_else(self, migration_app):
        upgrade()
        assert tables() - {'alembic_version'} == {t.name for t in db.metadata.tables.values()}

    def test_guard_catches_an_extra_model_column_and_names_it(self, migration_app):
        upgrade()
        metadata = models_copy()
        metadata.tables['riftbound.rbset'].append_column(sa.Column('rbset_throwaway', sa.Text()))
        assert any('rbset_throwaway' in line for line in describe(drift(metadata)))

    def test_guard_catches_a_column_missing_from_the_models(self, migration_app):
        upgrade()
        metadata = models_copy()
        metadata.tables['riftbound.rbset']._columns.remove(
            metadata.tables['riftbound.rbset'].c.rbset_outdat)
        assert any('rbset_outdat' in line for line in describe(drift(metadata)))

    def test_guard_catches_a_type_change(self, migration_app):
        upgrade()
        metadata = models_copy()
        column = metadata.tables['riftbound.rbusers'].c.username
        column.type = sa.String(10)
        assert any('username' in line for line in describe(drift(metadata)))

    def test_guard_catches_an_extra_model_table(self, migration_app):
        upgrade()
        metadata = models_copy()
        sa.Table('rbthrowaway', metadata, sa.Column('id', sa.Integer, primary_key=True),
                 schema='riftbound')
        assert any('rbthrowaway' in line for line in describe(drift(metadata)))


class TestDialectTypes:
    def test_collection_id_is_bigint_on_postgresql_and_integer_on_sqlite(self):
        column = RbCollection.__table__.c.rbcol_id
        assert isinstance(column.type.dialect_impl(postgresql.dialect()), sa.BigInteger)
        impl = column.type.dialect_impl(sqlite.dialect())
        assert isinstance(impl, sa.Integer) and not isinstance(impl, sa.BigInteger)

    def test_deck_cards_are_jsonb_on_postgresql_and_json_on_sqlite(self):
        column = RbDeck.__table__.c.rbdck_cards
        assert isinstance(column.type.dialect_impl(postgresql.dialect()), postgresql.JSONB)
        impl = column.type.dialect_impl(sqlite.dialect())
        assert isinstance(impl, sa.JSON) and not isinstance(impl, postgresql.JSONB)


class TestRoundTrip:
    def test_upgrade_downgrade_upgrade_leaves_an_identical_schema(self, migration_app):
        upgrade()
        first = structure()
        assert len(first) == 14       # 16 baseline tables minus the 2 dropped legacy ones

        downgrade('base')
        assert tables() == {'alembic_version'}
        assert rows('SELECT count(*) FROM riftbound.alembic_version') == [(0,)]

        upgrade()
        assert structure() == first
        assert drift() == []

    def test_each_revision_steps_down_one_at_a_time(self, migration_app):
        upgrade()
        steps = ((DROP_LEGACY, 14), (BASELINE, 16), ('base', 0))
        recorded = []
        for target, table_count in steps:
            downgrade(target)
            assert len(tables() - {'alembic_version'}) == table_count, target
            recorded.append(rows('SELECT version_num FROM riftbound.alembic_version'))
        assert recorded == [[(DROP_LEGACY,)], [(BASELINE,)], []]


# --- 2.30 `flask schema snapshot` (PostgreSQL output is covered by test_migrations_pg) ---

class TestSchemaSnapshotCommand:
    def test_is_registered_on_the_cli(self, migration_app):
        result = migration_app.test_cli_runner().invoke(args=['schema', '--help'])
        assert result.exit_code == 0
        assert 'snapshot' in result.output

    def test_refuses_a_non_postgresql_database(self, migration_app):
        result = migration_app.test_cli_runner().invoke(args=['schema', 'snapshot'])
        assert result.exit_code == 1
        assert 'PostgreSQL' in result.output and 'sqlite' in result.output
        assert 'TABLE' not in result.output


# --- 2.32 Runbook (MIG-9). CHAR: written after the doc, pins what it must keep saying ---

class TestRunbook:
    DOC = (ROOT / 'docs' / 'migrations.md')

    @pytest.mark.parametrize('needle', [
        'pg_dump', '-n riftbound', 'pg_restore -l', 'flask schema snapshot',
        'flask db stamp 0001_baseline', 'flask db upgrade', 'flask db check',
        'flask db downgrade 0001_baseline', 'flask db stamp base', 'pg_restore --clean',
        'RB_LEGACY_BACKUP_DIR', 'e-mail addresses and password hashes', 'never be committed',
    ])
    def test_runbook_mentions(self, needle):
        assert needle in self.DOC.read_text(encoding='utf-8')

    def test_steps_are_in_a_safe_order(self):
        text = self.DOC.read_text(encoding='utf-8')
        order = [text.index(s) for s in (
            'pg_dump', 'flask schema snapshot', 'flask db stamp 0001_baseline',
            'flask db upgrade\n   ```')]
        assert order == sorted(order)

    def test_env_example_documents_the_backup_directory(self):
        assert 'RB_LEGACY_BACKUP_DIR=' in (ROOT / '.env.example').read_text()


# --- 2.8 pg_url safety guard (D20): never run destructive tests on a real database ---

class TestTestDatabaseGuard:
    @pytest.mark.parametrize('url', [
        'postgresql+psycopg://rb:rb@localhost:5432/riftbound_test',
        'postgresql+psycopg://rb:rb@localhost/TEST',
        'postgresql+psycopg://rb@/rbtest?host=/tmp/sock',
    ])
    def test_accepts_databases_named_test(self, url):
        assert checked_test_database_url(url) == url

    @pytest.mark.parametrize('url', [
        'postgresql+psycopg://rb:rb@localhost:5432/riftbound',
        'postgresql+psycopg://rb:rb@localhost:5432/postgres',
        'postgresql+psycopg://rb:rb@localhost:5432/',
        'postgresql+psycopg://rb:rb@testhost:5432/riftbound',   # "test" only in the host
    ])
    def test_refuses_any_other_database(self, url):
        with pytest.raises(ValueError, match="must contain 'test'"):
            checked_test_database_url(url)
