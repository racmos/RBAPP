"""
PostgreSQL migration tests ([PG-CI] scenarios of unit b).

Marked `postgres`: they run only when TEST_POSTGRES_URL points at a throw-away
database whose name contains "test" (see the `pg_url` fixture, D20). In CI the
`migrations-pg` job provides one (PostgreSQL 18 service container).
"""
import os
import re
import stat
from pathlib import Path

import pytest
import sqlalchemy as sa

from app import create_app, db
from tests.migration_helpers import (
    alembic, downgrade, drift, inspector, rows, run, tables, upgrade)
from tests.snapshot_utils import FIXTURE

pytestmark = pytest.mark.postgres

BASELINE = '0001_baseline'
DROP_LEGACY = '0002_drop_legacy_tables'
QUANTITY = '0003_collection_quantity_integer'
LEGACY_SEQUENCE = 'rbusers_rbus_id_seq'


@pytest.fixture
def pg_app(pg_url, tmp_path):
    """App bound to the empty test database (schema `riftbound` absent)."""
    app = create_app(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI=pg_url,
        SECRET_KEY='test-secret-key',
        LEGACY_BACKUP_DIR=str(tmp_path / 'backups'),
    )
    with app.app_context():
        yield app
        db.session.remove()
        db.engine.dispose()


def backups(app):
    folder = Path(app.config['LEGACY_BACKUP_DIR'])
    return sorted(folder.glob('legacy_tables_*.sql')) if folder.exists() else []


def snapshot_text(app):
    result = app.test_cli_runner().invoke(args=['schema', 'snapshot'])
    assert result.exit_code == 0, result.output
    return result.output


_NOT_NULL_CONSTRAINT = re.compile(r'^\s+CONSTRAINT \S+ NOT NULL \S+$')


def comparable(text):
    """The snapshot minus what legitimately differs between servers and runs:
    the version header, PostgreSQL 18's named NOT NULL constraints (dev has them,
    older servers do not) and trailing whitespace."""
    return [line.rstrip() for line in text.splitlines()
            if not line.startswith('-- PostgreSQL')
            and not _NOT_NULL_CONSTRAINT.match(line)]


def seed_world():
    """A small but complete database at revision 0001: live users and
    collection (text quantities), legacy users/decks, live decks."""
    run("INSERT INTO riftbound.rbset (rbset_id, rbset_name) VALUES ('OGN', 'Origins')")
    run("INSERT INTO riftbound.rbcards (rbcar_rbset_id, rbcar_id, rbcar_name) VALUES"
        " ('OGN', '1', 'Ahri'), ('OGN', '2', 'Annie')")
    run("INSERT INTO riftbound.rbusers (username, email, password_hash) VALUES"
        " ('alice', 'alice@live.io', 'live-a'), ('bob', 'bob@live.io', 'live-b')")
    run("INSERT INTO riftbound.old1_rbusers (rbus_username, rbus_email, rbus_password) VALUES"
        " ('alice', 'alice@old.io', 'old-a'), ('bob', 'bob@old.io', 'old-b')")
    run("INSERT INTO riftbound.rbdecks (rbdck_user, rbdck_name, rbdck_seq, rbdck_cards) VALUES"
        " ('alice', 'Foo', 1, '{\"main\": []}'), ('alice', 'Foo', 2, '{\"main\": [1]}')")
    run("INSERT INTO riftbound.old_rbdecks (rbdck_name, rbdck_decription, rbdck_max_set,"
        " rbdck_rbset_id, rbdck_rbcar_id, rbdck_user, rbdck_orden) VALUES"
        " ('Foo', 'O''Brien''s; deck', 'OGN', 'OGN', '1', 'alice', 1),"
        " ('Old only', NULL, 'OGN', 'OGN', '2', 'alice', 2),"
        " ('Foo', NULL, 'OGN', 'OGN', '1', 'bob', 3)")
    run("INSERT INTO riftbound.rbcollection (rbcol_rbset_id, rbcol_rbcar_id, rbcol_foil,"
        " rbcol_quantity, rbcol_chadat, rbcol_user) VALUES"
        " ('OGN', '1', 'N', '12', now(), 'alice'), ('OGN', '2', 'S', ' 3 ', now(), 'alice')")


def public_objects():
    return rows("SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace"
                " WHERE n.nspname = 'public' ORDER BY 1")


class TestBaseline:
    def test_empty_database_gets_schema_riftbound_and_nothing_in_public(self, pg_app):
        before = public_objects()
        assert rows("SELECT count(*) FROM pg_namespace WHERE nspname = 'riftbound'") == [(0,)]

        upgrade(BASELINE)

        assert rows("SELECT count(*) FROM pg_namespace WHERE nspname = 'riftbound'") == [(1,)]
        assert public_objects() == before
        assert rows('SELECT version_num FROM riftbound.alembic_version') == [(BASELINE,)]
        assert len(tables() - {'alembic_version'}) == 16

    def test_structure_equals_the_dev_snapshot(self, pg_app):
        upgrade(BASELINE)
        want = comparable(FIXTURE.read_text())
        got = comparable(snapshot_text(pg_app))
        assert got == want

    def test_snapshot_comparison_is_not_vacuous(self, pg_app):
        upgrade(BASELINE)
        run('ALTER TABLE riftbound.rbset ADD COLUMN rbset_extra text')
        assert comparable(snapshot_text(pg_app)) != comparable(FIXTURE.read_text())


class TestQuantityCast:
    def test_using_cast_works_up_and_down_and_keeps_values(self, pg_app):
        upgrade(BASELINE)
        seed_world()
        upgrade(DROP_LEGACY)
        assert rows("SELECT data_type FROM information_schema.columns WHERE table_schema = 'riftbound'"
                    " AND table_name = 'rbcollection' AND column_name = 'rbcol_quantity'") == [('text',)]

        upgrade(QUANTITY)
        assert rows('SELECT rbcol_quantity, pg_typeof(rbcol_quantity)::text FROM'
                    ' riftbound.rbcollection ORDER BY rbcol_id') == [(12, 'integer'), (3, 'integer')]

        downgrade(DROP_LEGACY)
        assert rows('SELECT rbcol_quantity, pg_typeof(rbcol_quantity)::text FROM'
                    ' riftbound.rbcollection ORDER BY rbcol_id') == [('12', 'text'), ('3', 'text')]

    def test_preflight_abort_leaves_the_text_column(self, pg_app):
        upgrade(DROP_LEGACY)
        run("INSERT INTO riftbound.rbset (rbset_id, rbset_name) VALUES ('OGN', 'Origins')")
        run("INSERT INTO riftbound.rbcards (rbcar_rbset_id, rbcar_id, rbcar_name)"
            " VALUES ('OGN', '1', 'Ahri')")
        run("INSERT INTO riftbound.rbusers (username, email, password_hash)"
            " VALUES ('alice', 'a@x.io', 'h')")
        run("INSERT INTO riftbound.rbcollection (rbcol_rbset_id, rbcol_rbcar_id, rbcol_quantity,"
            " rbcol_chadat, rbcol_user) VALUES ('OGN', '1', 'abc', now(), 'alice')")
        with pytest.raises(RuntimeError, match='rbcol_id'):
            upgrade(QUANTITY)
        assert rows("SELECT data_type FROM information_schema.columns WHERE table_schema = 'riftbound'"
                    " AND table_name = 'rbcollection' AND column_name = 'rbcol_quantity'") == [('text',)]

    def test_check_constraint_is_enforced_by_postgresql(self, pg_app):
        upgrade()
        run("INSERT INTO riftbound.rbset (rbset_id, rbset_name) VALUES ('OGN', 'Origins')")
        run("INSERT INTO riftbound.rbcards (rbcar_rbset_id, rbcar_id, rbcar_name)"
            " VALUES ('OGN', '1', 'Ahri')")
        run("INSERT INTO riftbound.rbusers (username, email, password_hash)"
            " VALUES ('alice', 'a@x.io', 'h')")
        with pytest.raises(sa.exc.IntegrityError):
            run("INSERT INTO riftbound.rbcollection (rbcol_rbset_id, rbcol_rbcar_id,"
                " rbcol_quantity, rbcol_chadat, rbcol_user)"
                " VALUES ('OGN', '1', 0, now(), 'alice')")


class TestForeignKeyAndDrift:
    def test_deck_fk_points_at_rbusers_and_db_check_is_clean(self, pg_app):
        upgrade()
        [fk] = inspector().get_foreign_keys('rbdecks', schema='riftbound')
        assert (fk['name'], fk['referred_table'], fk['referred_columns']) == (
            'fk_deck_user', 'rbusers', ['username'])
        assert fk['options'] == {'onupdate': 'CASCADE', 'ondelete': 'RESTRICT'}
        result = pg_app.test_cli_runner().invoke(args=['db', 'check'])
        assert result.exit_code == 0, result.output

    def test_db_check_fails_when_the_database_drifts(self, pg_app):
        upgrade()
        run('ALTER TABLE riftbound.rbset ADD COLUMN rbset_extra text')
        result = pg_app.test_cli_runner().invoke(args=['db', 'check'])
        assert result.exit_code != 0

    def test_models_equal_the_postgresql_schema(self, pg_app):
        upgrade()
        assert drift() == []


class TestSeededDatabase:
    def test_legacy_rows_and_text_quantities_reach_head_with_data_intact(self, pg_app):
        upgrade(BASELINE)
        seed_world()
        before = dict(
            users=rows('SELECT username, email, password_hash FROM riftbound.rbusers ORDER BY id'),
            decks=rows('SELECT rbdck_user, rbdck_name, rbdck_seq, rbdck_cards FROM'
                       ' riftbound.rbdecks ORDER BY id'),
        )

        upgrade()

        assert rows('SELECT username, email, password_hash FROM riftbound.rbusers ORDER BY id') \
            == before['users']
        assert rows('SELECT rbdck_user, rbdck_name, rbdck_seq, rbdck_cards FROM'
                    ' riftbound.rbdecks ORDER BY id') == before['decks']
        assert rows('SELECT rbcol_rbcar_id, rbcol_foil, rbcol_quantity FROM riftbound.rbcollection'
                    ' ORDER BY rbcol_id') == [('1', 'N', 12), ('2', 'S', 3)]
        assert not {'old1_rbusers', 'old_rbdecks'} & tables()
        assert rows("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace"
                    f" WHERE n.nspname = 'riftbound' AND c.relname = '{LEGACY_SEQUENCE}'") == [(0,)]

        [backup] = backups(pg_app)
        assert stat.S_IMODE(backup.stat().st_mode) == 0o600
        text = backup.read_text(encoding='utf-8')
        assert text.count('INSERT INTO') == 5            # 2 legacy users + 3 legacy deck rows
        assert "O''Brien''s; deck" in text

    def test_downgrade_to_the_baseline_restores_the_legacy_rows(self, pg_app):
        upgrade(BASELINE)
        seed_world()
        legacy_sql = ('SELECT rbus_id, rbus_username, rbus_email, rbus_password, rbus_created'
                      ' FROM riftbound.old1_rbusers ORDER BY 1')
        decks_sql = ('SELECT rbdck_snapshot, rbdck_name, rbdck_decription, rbdck_user, rbdck_orden'
                     ' FROM riftbound.old_rbdecks ORDER BY rbdck_user, rbdck_name')
        legacy_before, decks_before = rows(legacy_sql), rows(decks_sql)
        assert len(legacy_before) == 2 and len(decks_before) == 3

        upgrade()
        downgrade(BASELINE)

        assert rows(legacy_sql) == legacy_before
        assert rows(decks_sql) == decks_before
        [fk] = inspector().get_foreign_keys('rbdecks', schema='riftbound')
        assert fk['referred_table'] == 'old1_rbusers'
        # the restored sequence continues after the replayed ids
        run("INSERT INTO riftbound.old1_rbusers (rbus_username, rbus_email, rbus_password)"
            " VALUES ('carol', 'carol@old.io', 'x')")
        assert rows("SELECT rbus_id FROM riftbound.old1_rbusers WHERE rbus_username = 'carol'") \
            == [(3,)]

    def test_orphan_deck_owner_aborts_and_rolls_everything_back(self, pg_app):
        upgrade(BASELINE)
        run("INSERT INTO riftbound.old1_rbusers (rbus_username, rbus_email, rbus_password)"
            " VALUES ('ghost', 'g@old.io', 'x')")
        run("INSERT INTO riftbound.rbdecks (rbdck_user, rbdck_name) VALUES ('ghost', 'Lost')")
        with pytest.raises(RuntimeError, match='ghost'):
            upgrade()
        assert rows('SELECT version_num FROM riftbound.alembic_version') == [(BASELINE,)]
        assert {'old1_rbusers', 'old_rbdecks'} <= tables()
        assert backups(pg_app) == []


class TestRoundTrip:
    def test_upgrade_downgrade_base_upgrade_is_identical(self, pg_app):
        upgrade()
        first = comparable(snapshot_text(pg_app))
        downgrade('base')
        assert tables() == {'alembic_version'}
        assert [r for r in rows("SELECT c.relname FROM pg_class c JOIN pg_namespace n"
                                " ON n.oid = c.relnamespace WHERE n.nspname = 'riftbound'"
                                " AND c.relkind = 'S'")] == []
        upgrade()
        assert comparable(snapshot_text(pg_app)) == first

    def test_offline_sql_mode_is_refused_for_the_destructive_revision(self, pg_app):
        upgrade(BASELINE)
        with pytest.raises(RuntimeError, match='offline'):
            alembic('upgrade', f'{BASELINE}:{DROP_LEGACY}', sql=True)
