"""RESET-b: `flask reset production-data` (AC2-AC7, S3-S20) on SQLite.

The PostgreSQL-only behaviour (sequences, foreign keys enforced with RESTRICT/CASCADE as on the
server, a real rollback of `ALTER SEQUENCE`) lives in `tests/test_reset_pg.py` (`-m postgres`).
Here the foreign key order is proven with `PRAGMA foreign_keys=ON` and by recording the DELETE
statements. `read_backup_toc` and the revision reader are replaced; one test runs the real
revision check on a database built by the migrations, and one runs `read_backup_toc` against a
fake `PG_RESTORE` executable.
"""
import os
import stat
import sys
import time

import pytest
import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import RbAdminAudit, RbJob
from app.services import data_reset
from app.services.data_reset import KEEP, TABLE_POLICY, WIPE
from tests.reset_helpers import (
    BACKUP_NAME, KEPT, count, expansion_mappings, fake_toc, metadata_tables, seed_world, snapshot,
    table_rows)

DATABASE = ':memory:'


@pytest.fixture
def head(app):
    heads = data_reset.code_heads()
    assert len(heads) == 1
    return heads[0]


@pytest.fixture
def world(app, head, monkeypatch):
    """The AC2 world on the `app` fixture, at the code head (the create_all database has no
    alembic_version table, so the revision reader is replaced)."""
    monkeypatch.setattr(data_reset, 'current_revision', lambda: head)
    return seed_world()


@pytest.fixture
def backup(tmp_path, monkeypatch):
    path = tmp_path / BACKUP_NAME
    path.write_bytes(b'P' * 4096)
    monkeypatch.setattr(data_reset, 'read_backup_toc', lambda p: fake_toc())
    return path


@pytest.fixture
def reset(app):
    runner = app.test_cli_runner(mix_stderr=False)

    def _invoke(*extra, keep=KEPT, database=DATABASE, env='testing'):
        args = ['reset', 'production-data']
        for name in keep:
            args += ['--keep-user', name]
        if database is not None:
            args += ['--database', database]
        if env is not None:
            args += ['--env', env]
        return runner.invoke(args=args + [str(x) for x in extra])

    return _invoke


def execute_args(backup, database=DATABASE):
    return ('--backup', backup, '--execute', '--confirm', f'RESET {database}')


def assert_refused(result, message, before, mappings, exit_code=1):
    assert result.exit_code == exit_code, (result.stdout, result.stderr)
    assert result.stderr == f'Error: {message}\n'
    assert snapshot() == before
    assert expansion_mappings() == mappings


EXPECTED_TABLE_LINES = {
    'rbcaptcha_used': '1  delete 1',
    'rbcardbans': '1  keep',
    'rbcm_categories': '1  keep',
    'rbcm_expansions': '3  keep 3, mapping cleared 2',
    'rbcm_ignored': '1  keep',
    'rbcm_load_history': '1  keep',
    'rbcm_price': '1  keep',
    'rbcm_product_card_map': '1  delete 1',
    'rbcm_products': '1  keep',
    'rbproducts': '2  keep',
    'rbset': '2  delete 2',
    'rbusers': '5  delete 2, keep 3',
    'rbadminaudit': '2  delete 2',
    'rbcards': '2  delete 2',
    'rbjobs': '4  delete 2, keep 2',
    'rbcardchanges': '1  delete 1',
    'rbcardmarket': '1  delete 1',
}


def table_lines():
    """One line per metadata table in `sorted_tables` order (S18): every per-user table of the
    world holds 2 rows (one for a deleted user, one for a kept one)."""
    return [f'{t.name}  {EXPECTED_TABLE_LINES.get(t.name, "2  delete 2")}'
            for t in metadata_tables()]


def report(head, backup_line='Backup: not given (needed for --execute)', users=None):
    return [
        f'Database: {DATABASE} at {head}; RB_ENV testing',
        backup_line,
        users or 'Users: keep 3 (rbadmin, racmos, rbqa), delete 2; missing: -',
        *table_lines(),
    ]


# --- AC3: dry run -------------------------------------------------------------------------

class TestDryRun:
    def test_prints_the_report_and_changes_nothing(self, reset, world, head):
        before, mappings = snapshot(), expansion_mappings()
        result = reset()
        assert result.exit_code == 0, result.stderr
        assert result.stdout.splitlines() == report(head) + [
            'Dry run: nothing was changed. Run again with --execute --confirm "RESET :memory:".']
        assert snapshot() == before
        assert expansion_mappings() == mappings

    def test_reports_the_backup_when_given(self, reset, world, head, backup):
        before = snapshot()
        result = reset('--backup', backup)
        assert result.exit_code == 0, result.stderr
        lines = result.stdout.splitlines()
        assert lines[1] == f'Backup: {BACKUP_NAME}, 4096 bytes, 3 TOC entries, 0.0 h old'
        assert snapshot() == before

    def test_lists_missing_users_and_warns_when_no_kept_user_is_an_admin(self, reset, world):
        result = reset(keep=('rbqa', 'ghost', 'rbqa'))
        assert result.exit_code == 0, result.stderr
        lines = result.stdout.splitlines()
        assert lines[2] == 'Users: keep 1 (rbqa), delete 4; missing: ghost'
        assert 'rbusers  5  delete 4, keep 1' in lines
        assert lines[-1] == ('No kept user is an admin: create one with '
                             'flask users create <name> --admin.')

    def test_says_nothing_about_admins_when_one_is_kept(self, reset, world):
        result = reset()
        assert 'No kept user is an admin' not in result.stdout


# --- AC4: execute -------------------------------------------------------------------------

class TestExecute:
    def test_wipes_keeps_and_clears_as_the_policy_says(self, reset, world, head, backup):
        before, user_ids = snapshot(), world['user_ids']
        result = reset(*execute_args(backup))
        assert result.exit_code == 0, (result.stdout, result.stderr)
        assert result.stdout.splitlines() == report(
            head, f'Backup: {BACKUP_NAME}, 4096 bytes, 3 TOC entries, 0.0 h old') + [
            'Reset done: 50 rows deleted in 27 tables, 2 expansion mappings cleared; '
            'kept tables unchanged.']
        after = snapshot()

        for table, policy in TABLE_POLICY.items():
            if policy == KEEP:
                assert after[table] == before[table], table      # full tuples, row by row
            elif policy == WIPE and table != 'rbadminaudit':
                assert after[table] == [], table
        # rbproducts keeps the old set codes although rbset is empty.
        assert count('rbset') == 0
        assert sorted(r[0] for r in after['rbproducts']) == ['OGN', 'SFD']
        # rbcm_expansions: same rows, only the mapping cleared.
        cols = [c.name for c in db.metadata.tables['riftbound.rbcm_expansions'].columns]
        mapping = cols.index('rbexp_rbset_id')
        assert after['rbcm_expansions'] == [
            tuple(None if i == mapping else v for i, v in enumerate(row))
            for row in before['rbcm_expansions']]

    def test_keeps_the_named_users_with_their_lock_cleared(self, reset, world, backup):
        before = {r[1]: r for r in table_rows('rbusers')}
        result = reset(*execute_args(backup))
        assert result.exit_code == 0, result.stderr
        cols = [c.name for c in db.metadata.tables['riftbound.rbusers'].columns]
        after = {r[1]: r for r in table_rows('rbusers')}
        assert sorted(after) == sorted(KEPT)
        for name in KEPT:
            expected = dict(zip(cols, before[name]), failed_login_count=0, locked_until=None)
            assert dict(zip(cols, after[name])) == expected, name
        assert after['rbadmin'][cols.index('is_admin')] is True
        assert after['rbqa'][cols.index('is_blocked')] is True

    def test_keeps_only_the_finished_daily_prices_jobs(self, reset, world, backup):
        ids, users = world['job_ids'], world['user_ids']
        result = reset(*execute_args(backup))
        assert result.exit_code == 0, result.stderr
        db.session.expire_all()
        jobs = {j.rbjob_id: j for j in RbJob.query.all()}
        assert sorted(jobs) == sorted([ids['daily_ok'], ids['daily_error']])
        assert jobs[ids['daily_ok']].rbjob_requested_by is None       # pointed to olduser1
        assert jobs[ids['daily_error']].rbjob_requested_by == users['rbadmin']
        assert jobs[ids['daily_error']].rbjob_message == 'boom'

    def test_writes_one_audit_row_with_counts_only(self, reset, world, backup):
        result = reset('--keep-user', 'ghost', *execute_args(backup))
        assert result.exit_code == 0, result.stderr
        db.session.expire_all()
        rows = RbAdminAudit.query.all()
        assert len(rows) == 1
        row = rows[0]
        assert (row.rbaud_actor_id, row.rbaud_actor_username, row.rbaud_action,
                row.rbaud_target_type, row.rbaud_target_id) == (
            None, 'system', 'data.reset', 'database', DATABASE)
        deleted = {t: 2 for t, p in TABLE_POLICY.items() if p == WIPE}
        deleted.update(rbcaptcha_used=1, rbcm_product_card_map=1, rbcardchanges=1,
                       rbcardmarket=1, rbusers=2, rbjobs=2)
        assert row.rbaud_details == {
            'deleted': deleted,
            'cleared_expansion_mappings': 2,
            'kept_users': ['rbadmin', 'racmos', 'rbqa'],
            'missing_users': ['ghost'],
            'backup': BACKUP_NAME,
        }
        text = str(row.rbaud_details) + result.stdout + result.stderr
        for secret in ('@mail.example', 'hash-of-', str(backup.parent), 'sqlite:'):
            assert secret not in text

    def test_a_second_run_finds_nothing_more_to_delete(self, reset, world, backup):
        assert reset(*execute_args(backup)).exit_code == 0
        result = reset()
        assert result.exit_code == 0, result.stderr
        lines = result.stdout.splitlines()
        assert 'rbset  0  delete 0' in lines
        assert 'rbcm_expansions  3  keep 3, mapping cleared 0' in lines
        assert 'rbadminaudit  1  delete 1' in lines
        assert 'rbusers  3  delete 0, keep 3' in lines

    def test_never_touches_files_on_disk(self, reset, world, backup, card_images_dir,
                                         avatar_dir, product_images_dir):
        files = []
        for root in (card_images_dir, avatar_dir, product_images_dir):
            (root / 'ogn').mkdir(parents=True)
            (root / 'ogn' / 'file.webp').write_bytes(b'x')
            files.append(root / 'ogn' / 'file.webp')
        backup_stat = backup.stat()
        assert reset(*execute_args(backup)).exit_code == 0
        assert all(f.read_bytes() == b'x' for f in files)
        assert backup.stat().st_mtime == backup_stat.st_mtime
        assert backup.read_bytes() == b'P' * 4096


# --- S14: explicit deletes in foreign key order ------------------------------------------

class TestDeleteOrder:
    def test_order_puts_every_child_before_its_parent(self, app):
        order = data_reset.delete_order()
        position = {name: i for i, name in enumerate(order)}
        assert set(order) == set(TABLE_POLICY)
        for table in metadata_tables():
            for fk in table.foreign_keys:
                parent = fk.column.table.name
                if parent != table.name:
                    assert position[table.name] < position[parent], (table.name, parent)

    def test_runs_with_foreign_keys_enforced_and_deletes_each_table_explicitly(
            self, reset, world, backup):
        with db.engine.connect() as conn:
            conn.exec_driver_sql('PRAGMA foreign_keys=ON')
        try:
            # The enforcement is real: a user with collection lines cannot go first (RESTRICT).
            with pytest.raises(IntegrityError):
                with db.session.begin_nested():
                    db.session.execute(sa.text(
                        "DELETE FROM riftbound.rbusers WHERE username = 'olduser1'"))
            db.session.rollback()
            statements = []

            def remember(conn, cursor, statement, parameters, context, executemany):
                if statement.lstrip().upper().startswith('DELETE'):
                    statements.append(statement)

            event.listen(db.engine, 'before_cursor_execute', remember)
            try:
                result = reset(*execute_args(backup))
            finally:
                event.remove(db.engine, 'before_cursor_execute', remember)
            assert result.exit_code == 0, (result.stdout, result.stderr)
        finally:
            with db.engine.connect() as conn:
                conn.exec_driver_sql('PRAGMA foreign_keys=OFF')

        deleted_from = [s.split('FROM', 1)[1].split()[0].split('.')[-1] for s in statements]
        expected = [t for t in data_reset.delete_order()
                    if TABLE_POLICY[t] == WIPE or t in ('rbusers', 'rbjobs')]
        assert deleted_from == expected
        assert all(count(t) == 0 for t, p in TABLE_POLICY.items()
                   if p == WIPE and t != 'rbadminaudit')


# --- AC5: refusals -------------------------------------------------------------------------

class TestUsage:
    def test_execute_needs_confirm(self, reset, world, backup):
        before, mappings = snapshot(), expansion_mappings()
        result = reset('--backup', backup, '--execute')
        assert_refused(result, '--execute needs --confirm "RESET :memory:".', before, mappings,
                       exit_code=2)

    def test_confirm_is_only_for_execute(self, reset, world):
        before, mappings = snapshot(), expansion_mappings()
        result = reset('--confirm', 'RESET :memory:')
        assert_refused(result, '--confirm is only used with --execute.', before, mappings,
                       exit_code=2)

    def test_execute_needs_a_backup(self, reset, world):
        before, mappings = snapshot(), expansion_mappings()
        result = reset('--execute', '--confirm', 'RESET :memory:')
        assert_refused(result, '--execute needs --backup PATH.', before, mappings, exit_code=2)

    @pytest.mark.parametrize('missing', ['keep', 'database', 'env'])
    def test_required_options(self, reset, world, missing):
        before = snapshot()
        kwargs = {'keep': ()} if missing == 'keep' else {missing: None}
        result = reset(**kwargs)
        assert result.exit_code == 2
        assert 'Missing option' in result.stderr
        assert snapshot() == before

    def test_wrong_confirmation(self, reset, world, backup):
        before, mappings = snapshot(), expansion_mappings()
        result = reset('--backup', backup, '--execute', '--confirm', 'RESET riftbound')
        assert_refused(result, 'The confirmation does not match; nothing was changed.',
                       before, mappings)

    def test_help_lists_the_command(self, reset, app):
        result = app.test_cli_runner().invoke(args=['reset', '--help'])
        assert result.exit_code == 0
        assert 'production-data' in result.output


class TestGuards:
    def test_unclassified_tables(self, reset, world, backup):
        db.session.execute(sa.text('CREATE TABLE riftbound.rbzeta (id INTEGER)'))
        db.session.execute(sa.text('CREATE TABLE riftbound.rbalpha (id INTEGER)'))
        db.session.commit()
        try:
            before, mappings = snapshot(), expansion_mappings()
            result = reset(*execute_args(backup))
            assert_refused(result, 'Unclassified tables: rbalpha, rbzeta. Classify them in '
                           'app/services/data_reset.py; nothing was changed.', before, mappings)
        finally:
            db.session.execute(sa.text('DROP TABLE riftbound.rbzeta'))
            db.session.execute(sa.text('DROP TABLE riftbound.rbalpha'))
            db.session.commit()

    def test_other_database(self, reset, world, backup):
        before, mappings = snapshot(), expansion_mappings()
        result = reset(*execute_args(backup, database='riftbound'), database='riftbound')
        assert_refused(result, "Connected to database ':memory:', not 'riftbound'; "
                       'nothing was changed.', before, mappings)

    def test_other_env(self, reset, world, backup):
        before, mappings = snapshot(), expansion_mappings()
        result = reset(*execute_args(backup), env='production')
        assert_refused(result, "RB_ENV is 'testing', not 'production'; nothing was changed.",
                       before, mappings)

    def test_a_test_database_needs_allow_test_db(self, reset, world, backup, monkeypatch):
        monkeypatch.setattr(data_reset, 'connected_database', lambda: 'riftbound_Reset_TEST')
        monkeypatch.setattr(data_reset, 'read_backup_toc',
                            lambda p: fake_toc('riftbound_Reset_TEST'))
        before, mappings = snapshot(), expansion_mappings()
        result = reset(*execute_args(backup, 'riftbound_Reset_TEST'),
                       database='riftbound_Reset_TEST')
        assert_refused(result, "Database 'riftbound_Reset_TEST' looks like a test database; "
                       'add --allow-test-db for a rehearsal.', before, mappings)
        result = reset('--allow-test-db', *execute_args(backup, 'riftbound_Reset_TEST'),
                       database='riftbound_Reset_TEST')
        assert result.exit_code == 0, result.stderr
        assert count('rbset') == 0

    def test_allow_test_db_only_for_a_test_name(self, reset, world, backup):
        before, mappings = snapshot(), expansion_mappings()
        result = reset('--allow-test-db')
        assert_refused(result, '--allow-test-db is only for a database whose name contains '
                       '"test".', before, mappings)

    def test_revision_behind_the_code(self, reset, world, head, monkeypatch, backup):
        monkeypatch.setattr(data_reset, 'current_revision', lambda: '0031_mfa')
        before, mappings = snapshot(), expansion_mappings()
        result = reset(*execute_args(backup))
        assert_refused(result, f'The database is at 0031_mfa, the code expects {head}; '
                       'run flask db upgrade first.', before, mappings)

    def test_no_revision_at_all(self, reset, app, head):
        before, mappings = snapshot(), expansion_mappings()
        result = reset()        # the create_all database has no alembic_version table
        assert_refused(result, f'The database is at no revision, the code expects {head}; '
                       'run flask db upgrade first.', before, mappings)

    @pytest.mark.parametrize('status', ['queued', 'running'])
    def test_active_jobs(self, reset, world, backup, status):
        db.session.add(RbJob(rbjob_kind='heartbeat', rbjob_status=status))
        db.session.commit()
        before, mappings = snapshot(), expansion_mappings()
        result = reset(*execute_args(backup))
        assert_refused(result, '1 job(s) queued or running; stop the timers and wait '
                       '(flask jobs list).', before, mappings)


class TestBackupChecks:
    def test_not_found(self, reset, world, backup, tmp_path):
        before, mappings = snapshot(), expansion_mappings()
        missing = tmp_path / 'nope.dump'
        result = reset(*execute_args(missing))
        assert_refused(result, f'Backup file not found: {missing}', before, mappings)

    def test_a_directory_is_not_a_backup_file(self, reset, world, backup, tmp_path):
        before, mappings = snapshot(), expansion_mappings()
        result = reset(*execute_args(tmp_path))
        assert_refused(result, f'Backup file not found: {tmp_path}', before, mappings)

    def test_empty(self, reset, world, backup):
        backup.write_bytes(b'')
        before, mappings = snapshot(), expansion_mappings()
        result = reset(*execute_args(backup))
        assert_refused(result, f'Backup file is empty: {backup}', before, mappings)

    def test_older_than_six_hours(self, reset, world, backup):
        old = time.time() - 6 * 3600 - 60
        os.utime(backup, (old, old))
        before, mappings = snapshot(), expansion_mappings()
        result = reset(*execute_args(backup))
        assert_refused(result, f'Backup file is older than 6 hours: {backup}', before, mappings)
        # The dry run checks a given backup the same way.
        assert_refused(reset('--backup', backup),
                       f'Backup file is older than 6 hours: {backup}', before, mappings)

    def test_unreadable_by_pg_restore(self, reset, world, backup, monkeypatch):
        def unreadable(path):
            raise data_reset.BackupUnreadable('pg_restore: error: input file is too short')

        monkeypatch.setattr(data_reset, 'read_backup_toc', unreadable)
        before, mappings = snapshot(), expansion_mappings()
        result = reset(*execute_args(backup))
        assert_refused(result, 'pg_restore cannot read the backup (pg_restore: error: input '
                       'file is too short).', before, mappings)

    def test_of_another_database(self, reset, world, backup, monkeypatch):
        monkeypatch.setattr(data_reset, 'read_backup_toc', lambda p: fake_toc('riftbound'))
        before, mappings = snapshot(), expansion_mappings()
        result = reset(*execute_args(backup))
        assert_refused(result, "The backup is of database 'riftbound', not ':memory:'.",
                       before, mappings)

    def test_without_price_data(self, reset, world, backup, monkeypatch):
        monkeypatch.setattr(data_reset, 'read_backup_toc', lambda p: fake_toc(price=False))
        before, mappings = snapshot(), expansion_mappings()
        result = reset(*execute_args(backup))
        assert_refused(result, 'The backup has no data for riftbound.rbcm_price.',
                       before, mappings)


class TestReadBackupToc:
    """The one function that runs pg_restore, against a fake executable named by PG_RESTORE."""

    def fake_pg_restore(self, tmp_path, body):
        script = tmp_path / 'pg_restore'
        script.write_text(f'#!{sys.executable} -I\nimport sys\n{body}\n')
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
        return script

    def test_returns_the_listing(self, tmp_path, monkeypatch):
        exe = self.fake_pg_restore(
            tmp_path, "assert sys.argv[1:] == ['-l', sys.argv[2]]\n"
                      "print(';     dbname: riftbound')\nprint(open(sys.argv[2]).read())")
        dump = tmp_path / 'x.dump'
        dump.write_text('3367; 0 16390 TABLE DATA riftbound rbcm_price rb')
        monkeypatch.setenv('PG_RESTORE', str(exe))
        toc = data_reset.read_backup_toc(dump)
        assert ';     dbname: riftbound' in toc
        assert 'TABLE DATA riftbound rbcm_price' in toc

    def test_a_failure_carries_the_first_stderr_line(self, tmp_path, monkeypatch):
        exe = self.fake_pg_restore(
            tmp_path, "sys.stderr.write('pg_restore: error: not an archive\\nmore\\n')\n"
                      'sys.exit(1)')
        monkeypatch.setenv('PG_RESTORE', str(exe))
        with pytest.raises(data_reset.BackupUnreadable) as error:
            data_reset.read_backup_toc(tmp_path / 'x.dump')
        assert str(error.value) == 'pg_restore: error: not an archive'

    def test_a_missing_executable(self, tmp_path, monkeypatch):
        monkeypatch.setenv('PG_RESTORE', str(tmp_path / 'absent'))
        with pytest.raises(data_reset.BackupUnreadable) as error:
            data_reset.read_backup_toc(tmp_path / 'x.dump')
        assert str(error.value) == f'cannot run {tmp_path / "absent"}'


# --- AC5: the real revision check on a database built by the migrations -----------------

class TestRealRevision:
    def test_passes_at_head_and_refuses_one_step_behind(self, migration_app):
        from tests.migration_helpers import downgrade, upgrade
        upgrade('head')
        head = data_reset.code_heads()[0]
        runner = migration_app.test_cli_runner(mix_stderr=False)
        args = ['reset', 'production-data', '--keep-user', 'rbadmin', '--database', DATABASE,
                '--env', 'testing']
        result = runner.invoke(args=args)
        assert result.exit_code == 0, result.stderr
        assert result.stdout.splitlines()[0] == f'Database: {DATABASE} at {head}; RB_ENV testing'
        assert result.stdout.splitlines()[2] == 'Users: keep 0 (-), delete 0; missing: rbadmin'
        downgrade('-1')
        result = runner.invoke(args=args)
        assert result.exit_code == 1
        assert result.stderr.startswith('Error: The database is at ')
        assert result.stderr.endswith(f', the code expects {head}; run flask db upgrade first.\n')


# --- AC7: one transaction ------------------------------------------------------------------

class TestRollback:
    def test_a_failure_midway_rolls_everything_back(self, reset, world, backup, monkeypatch):
        real, calls = data_reset._delete_all, []

        def failing(table):
            calls.append(table.name)
            if len(calls) == 5:
                raise RuntimeError('disk on fire')
            return real(table)

        monkeypatch.setattr(data_reset, '_delete_all', failing)
        before, mappings = snapshot(), expansion_mappings()
        result = reset(*execute_args(backup))
        assert result.exit_code == 1
        assert result.stderr == ('Error: Reset failed (RuntimeError); rolled back, '
                                 'nothing was changed.\n')
        assert 'Traceback' not in result.stdout + result.stderr
        assert 'disk on fire' not in result.stdout + result.stderr
        assert len(calls) == 5
        assert snapshot() == before
        assert expansion_mappings() == mappings

    def test_a_kept_table_changed_inside_the_transaction(self, reset, world, backup,
                                                         monkeypatch):
        def sneaky():
            db.session.execute(sa.text(
                "INSERT INTO riftbound.rbcardbans (rbban_name_key, rbban_name, rbban_mode, "
                "rbban_since) VALUES ('annie', 'Annie', '2v2', '2026-01-01')"))

        monkeypatch.setattr(data_reset, '_reset_sequences', sneaky)
        before, mappings = snapshot(), expansion_mappings()
        result = reset(*execute_args(backup))
        assert_refused(result, 'Kept table rbcardbans changed during the reset; rolled back, '
                       'nothing was changed.', before, mappings)

    def test_an_expansion_row_changed_inside_the_transaction(self, reset, world, backup,
                                                             monkeypatch):
        def sneaky():
            db.session.execute(sa.text(
                'UPDATE riftbound.rbcm_expansions SET rbexp_id = 104 WHERE rbexp_id = 103'))

        monkeypatch.setattr(data_reset, '_reset_sequences', sneaky)
        before, mappings = snapshot(), expansion_mappings()
        result = reset(*execute_args(backup))
        assert_refused(result, 'Kept table rbcm_expansions changed during the reset; rolled '
                       'back, nothing was changed.', before, mappings)


# --- PRESERVE: the other command groups are still registered -------------------------------

def test_the_other_command_groups_still_work(app):
    runner = app.test_cli_runner()
    for group in ('schema', 'users', 'jobs', 'bans', 'images', 'riot', 'sessions'):
        result = runner.invoke(args=[group, '--help'])
        assert result.exit_code == 0, group
    assert runner.invoke(args=['sessions', 'purge', '--dry-run']).output == (
        'Would purge 0 session(s)\n')
