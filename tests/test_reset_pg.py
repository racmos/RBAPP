"""RESET-b on PostgreSQL (AC8, S14, S15, S17): foreign keys enforced as on the server, sequences
restarted with `ALTER SEQUENCE ... RESTART` inside the transaction, and a rollback that undoes them.

Marked `postgres`: they run only when TEST_POSTGRES_URL points at a throw-away database whose name
contains "test" (the `pg_url` fixture drops schema `riftbound` before and after each test). The
schema is built by the migrations (`upgrade head`), so the real revision reader and the real table
reflection run here; only `read_backup_toc` is replaced.
"""
import pytest
import sqlalchemy as sa
from sqlalchemy.engine import make_url

from app import create_app, db
from app.services import data_reset
from app.services.data_reset import KEEP, TABLE_POLICY, WIPE
from tests.migration_helpers import upgrade
from tests.reset_helpers import BACKUP_NAME, count, fake_toc, seed_world, snapshot

pytestmark = pytest.mark.postgres


@pytest.fixture
def pg_app(pg_url, tmp_path):
    app = create_app(TESTING=True, SQLALCHEMY_DATABASE_URI=pg_url, SECRET_KEY='test-secret-key',
                     LEGACY_BACKUP_DIR=str(tmp_path / 'backups'))
    with app.app_context():
        upgrade('head')
        yield app
        db.session.remove()
        db.engine.dispose()


@pytest.fixture
def pg_reset(pg_app, pg_url, tmp_path, monkeypatch):
    database = make_url(pg_url).database
    backup = tmp_path / BACKUP_NAME
    backup.write_bytes(b'P' * 4096)
    monkeypatch.setattr(data_reset, 'read_backup_toc', lambda p: fake_toc(database))
    runner = pg_app.test_cli_runner(mix_stderr=False)

    def _invoke():
        return runner.invoke(args=[
            'reset', 'production-data', '--keep-user', 'rbadmin', '--keep-user', 'racmos',
            '--keep-user', 'rbqa', '--database', database, '--env', 'testing',
            '--allow-test-db', '--backup', str(backup), '--execute',
            '--confirm', f'RESET {database}'])

    return _invoke


def owned_sequences(policies):
    """{sequence: (table, column)} for the integer columns of the tables in `policies`."""
    found = {}
    for name, policy in TABLE_POLICY.items():
        if policy not in policies:
            continue
        for column in db.metadata.tables[f'riftbound.{name}'].columns:
            if not isinstance(column.type, sa.Integer):
                continue
            sequence = db.session.execute(
                sa.text('SELECT pg_get_serial_sequence(:t, :c)'),
                {'t': f'riftbound.{name}', 'c': column.name}).scalar()
            if sequence:
                found[sequence] = (name, column.name)
    return found


def nextval(sequence):
    return db.session.execute(
        sa.text('SELECT nextval(CAST(:s AS regclass))'), {'s': sequence}).scalar()


def sequence_states():
    rows = db.session.execute(sa.text(
        "SELECT sequencename, last_value FROM pg_sequences WHERE schemaname = 'riftbound' "
        'ORDER BY 1')).all()
    db.session.rollback()
    return [tuple(r) for r in rows]


def test_execute_with_enforced_foreign_keys(pg_reset):
    seed_world()
    before = snapshot()
    db.session.rollback()
    result = pg_reset()
    assert result.exit_code == 0, (result.stdout, result.stderr)
    after = snapshot()
    for table, policy in TABLE_POLICY.items():
        if policy == KEEP:
            assert after[table] == before[table] != [], table
        elif policy == WIPE and table != 'rbadminaudit':
            assert after[table] == [], table
    # rbproducts (RESTRICT parent of rbuserproducts) and rbcm_ignored are wiped (owner 2026-11-15).
    assert after['rbproducts'] == [] and after['rbcm_ignored'] == []
    assert count('rbadminaudit') == 1
    assert count('rbusers') == 3
    assert db.session.execute(sa.text(
        'SELECT count(*) FROM riftbound.rbcm_expansions WHERE rbexp_rbset_id IS NOT NULL'
    )).scalar() == 0


def test_sequences_restart_and_kept_ones_do_not_move(pg_reset):
    world = seed_world()
    wiped = owned_sequences({WIPE})
    kept = owned_sequences({KEEP}) | {
        s: t for s, t in owned_sequences({'special'}).items() if t[0] == 'rbcm_expansions'}
    assert wiped, 'the migrations create serial columns on the wiped tables'
    # The two tables wiped since 2026-11-15 own no sequence (their keys are Cardmarket ids).
    assert not {t for t, _ in wiped.values()} & {'rbproducts', 'rbcm_ignored'}
    kept_before = {s: v for s, v in sequence_states() if f'riftbound.{s}' in kept or s in kept}

    result = pg_reset()
    assert result.exit_code == 0, (result.stdout, result.stderr)

    audit_id = db.session.execute(sa.text('SELECT rbaud_id FROM riftbound.rbadminaudit')).scalar()
    assert audit_id == 1        # the data.reset row is the first of the new trail
    for sequence, (table, column) in wiped.items():
        if table == 'rbadminaudit':
            continue
        assert nextval(sequence) == 1, (table, column)
    users_seq = db.session.execute(sa.text(
        "SELECT pg_get_serial_sequence('riftbound.rbusers', 'id')")).scalar()
    jobs_seq = db.session.execute(sa.text(
        "SELECT pg_get_serial_sequence('riftbound.rbjobs', 'rbjob_id')")).scalar()
    kept_user_max = max(world['user_ids'][n] for n in ('rbadmin', 'racmos', 'rbqa'))
    kept_job_max = max(world['job_ids'][n] for n in ('daily_ok', 'daily_error'))
    assert nextval(users_seq) == kept_user_max + 1
    assert nextval(jobs_seq) == kept_job_max + 1
    db.session.rollback()
    kept_after = {s: v for s, v in sequence_states() if f'riftbound.{s}' in kept or s in kept}
    assert kept_after == kept_before


def test_a_rollback_after_the_restart_leaves_every_sequence_as_it_was(pg_reset, monkeypatch):
    seed_world()
    before, sequences = snapshot(), sequence_states()
    db.session.rollback()
    real = data_reset._reset_sequences

    def restart_then_fail():
        real()
        raise RuntimeError('power cut')

    monkeypatch.setattr(data_reset, '_reset_sequences', restart_then_fail)
    result = pg_reset()
    assert result.exit_code == 1
    assert result.stderr == ('Error: Reset failed (RuntimeError); rolled back, '
                             'nothing was changed.\n')
    assert snapshot() == before
    db.session.rollback()
    assert sequence_states() == sequences
