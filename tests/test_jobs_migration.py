"""F4-a S1/S7: migration `0007_jobs` round trip and drift (SQLite; the
`migrations-pg` CI job runs the same round trip on PostgreSQL 18)."""
import pytest
from sqlalchemy.exc import IntegrityError

from tests.migration_helpers import downgrade, drift, inspector, rows, run, tables, upgrade

INSERT = ("INSERT INTO riftbound.rbjobs (rbjob_kind, rbjob_status, rbjob_requested_at) "
          "VALUES (:kind, :status, '2030-01-01 12:00:00')")


def test_round_trip_and_no_drift(migration_app):
    upgrade()
    assert 'rbjobs' in tables()
    downgrade('0006_user_prefs')
    assert 'rbjobs' not in tables()
    assert 'rbuserprefs' in tables()
    upgrade()
    assert 'rbjobs' in tables()
    assert drift() == []


def test_named_constraints_and_indexes(migration_app):
    upgrade()
    checks = {c['name'] for c in inspector().get_check_constraints('rbjobs', schema='riftbound')}
    assert {'ck_rbjobs_kind', 'ck_rbjobs_status'} <= checks
    indexes = {i['name']: i for i in inspector().get_indexes('rbjobs', schema='riftbound')}
    assert indexes['ux_rbjobs_active_kind']['unique']
    assert indexes['ux_rbjobs_active_kind']['column_names'] == ['rbjob_kind']
    assert indexes['ix_rbjobs_status_requested']['column_names'] == [
        'rbjob_status', 'rbjob_requested_at']
    fks = inspector().get_foreign_keys('rbjobs', schema='riftbound')
    assert [(fk['referred_table'], fk['constrained_columns'], fk['options'].get('ondelete'))
            for fk in fks] == [('rbusers', ['rbjob_requested_by'], 'SET NULL')]


def test_migrated_schema_enforces_one_active_job_per_kind(migration_app):
    upgrade()
    run(INSERT, kind='heartbeat', status='queued')
    with pytest.raises(IntegrityError):
        run(INSERT, kind='heartbeat', status='running')
    run("UPDATE riftbound.rbjobs SET rbjob_status = 'success'")
    run(INSERT, kind='heartbeat', status='queued')
    assert rows('SELECT rbjob_status, rbjob_params FROM riftbound.rbjobs ORDER BY rbjob_id') == [
        ('success', '{}'), ('queued', '{}')]


@pytest.mark.parametrize('kind, status', [('nope', 'queued'), ('heartbeat', 'paused')])
def test_migrated_schema_checks_kind_and_status(migration_app, kind, status):
    upgrade()
    with pytest.raises(IntegrityError):
        run(INSERT, kind=kind, status=status)
    assert rows('SELECT COUNT(*) FROM riftbound.rbjobs') == [(0,)]
