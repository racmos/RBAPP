"""F4-c S1, S3 (AC3): migrations `0016_value_snapshots` and `0017_jobs_value_snapshot`:
round trips, drift, constraints, cascade (SQLite; `migrations-pg` runs them on PostgreSQL 18)."""
import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from tests.migration_helpers import downgrade, drift, inspector, rows, run, tables, upgrade

BEFORE = '0015_playset'
TABLE = '0016_value_snapshots'
KIND = '0017_jobs_value_snapshot'
USER = ("INSERT INTO riftbound.rbusers (id, username, email, password_hash, is_admin, is_blocked, "
        "failed_login_count) VALUES (:id, :name, :name || '@test.com', 'x', 0, 0, 0)")
SNAP = ("INSERT INTO riftbound.rbvaluesnaps (rbvsn_user_id, rbvsn_date, rbvsn_value, rbvsn_cost, "
        "rbvsn_qty, rbvsn_unique, rbvsn_unpriced) VALUES (:user, :day, 12.5, NULL, 3, 2, 1)")
JOB = ("INSERT INTO riftbound.rbjobs (rbjob_kind, rbjob_status, rbjob_requested_at) "
       "VALUES (:kind, :status, '2030-01-01 12:00:00')")


def test_the_table_has_its_named_constraints(migration_app):
    upgrade(TABLE)
    assert 'rbvaluesnaps' in tables()
    assert inspector().get_pk_constraint('rbvaluesnaps', schema='riftbound') == {
        'name': 'rbvaluesnaps_pkey', 'constrained_columns': ['rbvsn_user_id', 'rbvsn_date']}
    fks = inspector().get_foreign_keys('rbvaluesnaps', schema='riftbound')
    assert [(fk['name'], fk['referred_table']) for fk in fks] == [
        ('rbvaluesnaps_user_fk', 'rbusers')]


def test_one_row_per_user_and_day(migration_app):
    upgrade(TABLE)
    run(USER, id=1, name='ana')
    run(SNAP, user=1, day='2030-01-01')
    run(SNAP, user=1, day='2030-01-02')
    with pytest.raises(IntegrityError):
        run(SNAP, user=1, day='2030-01-01')
    assert rows('SELECT COUNT(*) FROM riftbound.rbvaluesnaps') == [(2,)]
    assert rows('SELECT rbvsn_created_at IS NOT NULL FROM riftbound.rbvaluesnaps '
                'LIMIT 1') == [(True,)]


def test_value_must_not_be_null(migration_app):
    upgrade(TABLE)
    run(USER, id=1, name='ana')
    with pytest.raises(IntegrityError):
        run("INSERT INTO riftbound.rbvaluesnaps (rbvsn_user_id, rbvsn_date, rbvsn_value, "
            "rbvsn_qty, rbvsn_unique, rbvsn_unpriced) VALUES (1, '2030-01-01', NULL, 1, 1, 0)")


def test_deleting_a_user_deletes_their_snapshots(migration_app):
    from app import db
    upgrade(TABLE)
    with db.engine.begin() as conn:
        conn.exec_driver_sql('PRAGMA foreign_keys=ON')   # SQLite enforces FKs only when asked
        for sql, params in ((USER, dict(id=1, name='ana')), (USER, dict(id=2, name='bo'))):
            conn.execute(sa.text(sql), params)
        for user in (1, 2):
            conn.execute(sa.text(SNAP), dict(user=user, day='2030-01-01'))
        conn.execute(sa.text(
            'DELETE FROM riftbound.rbusers WHERE id = 1'))
    assert rows('SELECT rbvsn_user_id FROM riftbound.rbvaluesnaps') == [(2,)]


def test_table_round_trip_and_drift(migration_app):
    upgrade(TABLE)
    upgrade()
    assert drift() == []
    downgrade(BEFORE)
    assert 'rbvaluesnaps' not in tables()
    upgrade()
    assert 'rbvaluesnaps' in tables()
    assert drift() == []


def test_kind_check_accepts_value_snapshot(migration_app):
    upgrade(TABLE)
    with pytest.raises(IntegrityError):
        run(JOB, kind='value_snapshot', status='queued')
    upgrade(KIND)
    run(JOB, kind='value_snapshot', status='queued')
    run(JOB, kind='daily_prices', status='queued')
    with pytest.raises(IntegrityError):
        run(JOB, kind='nope', status='queued')


def test_kind_downgrade_refuses_while_such_jobs_exist(migration_app):
    upgrade(KIND)
    run(JOB, kind='value_snapshot', status='success')
    with pytest.raises(RuntimeError) as caught:
        downgrade(TABLE)
    assert "holds 1 'value_snapshot' job(s)" in str(caught.value)
    assert rows('SELECT rbjob_kind FROM riftbound.rbjobs') == [('value_snapshot',)]
    run("DELETE FROM riftbound.rbjobs")
    downgrade(TABLE)
    with pytest.raises(IntegrityError):
        run(JOB, kind='value_snapshot', status='queued')


def test_revisions_chain():
    import importlib.util
    from pathlib import Path
    versions = Path(__file__).resolve().parents[1] / 'migrations' / 'versions'
    for name, down in ((TABLE, BEFORE), (KIND, TABLE)):
        spec = importlib.util.spec_from_file_location(f'm_{name}', versions / f'{name}.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert (module.revision, module.down_revision) == (name, down)
