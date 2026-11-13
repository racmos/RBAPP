"""F9-a S1 (AC1): migration `0029_sessions`: the `rbsessions` table with its named
constraints and indexes, the `sessions_purge` job kind, the guarded downgrade and the drift
check (SQLite; the `migrations-pg` CI job runs migrations on PostgreSQL 18)."""
import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from app.models.job import JOB_KINDS
from tests.migration_helpers import downgrade, drift, inspector, rows, run, tables, upgrade

BEFORE = '0028_legacy_schema_cleanup'
REVISION = '0029_sessions'
OLD_KINDS = ('heartbeat', 'daily_prices', 'riot_sync', 'value_snapshot', 'products_refresh',
             'price_alerts')
JOB = ("INSERT INTO riftbound.rbjobs (rbjob_kind, rbjob_status, rbjob_requested_at) "
       "VALUES (:kind, :status, '2030-01-01 12:00:00')")
USER = ("INSERT INTO riftbound.rbusers (id, username, email, password_hash, is_admin, is_blocked, "
        "failed_login_count) VALUES (:id, :name, :name || '@test.com', 'x', 0, 0, 0)")
SESSION = ("INSERT INTO riftbound.rbsessions (rbses_user_id, rbses_token_hash, rbses_created_at, "
           "rbses_last_seen_at) VALUES (:user, :hash, '2030-01-01 12:00:00', "
           "'2030-01-01 12:00:00')")
WITH_METHOD = ("INSERT INTO riftbound.rbsessions (rbses_user_id, rbses_token_hash, "
               "rbses_created_at, rbses_last_seen_at, rbses_auth_method) VALUES (:user, :hash, "
               "'2030-01-01 12:00:00', '2030-01-01 12:00:00', :method)")


def kinds():
    return rows('SELECT rbjob_kind FROM riftbound.rbjobs ORDER BY rbjob_id')


def columns():
    return {c['name']: c for c in inspector().get_columns('rbsessions', schema='riftbound')}


def test_the_model_allows_sessions_purge():
    assert JOB_KINDS == OLD_KINDS + ('sessions_purge',)


def test_the_table_columns(migration_app):
    upgrade(REVISION)
    assert 'rbsessions' in tables()
    found = columns()
    assert list(found) == [
        'rbses_id', 'rbses_user_id', 'rbses_token_hash', 'rbses_created_at',
        'rbses_last_seen_at', 'rbses_expires_at', 'rbses_remember', 'rbses_auth_method',
        'rbses_mfa', 'rbses_reauth_at', 'rbses_user_agent', 'rbses_ip_prefix',
        'rbses_revoked_at']
    nullable = {name for name, c in found.items() if c['nullable']}
    assert nullable == {'rbses_expires_at', 'rbses_reauth_at', 'rbses_user_agent',
                        'rbses_ip_prefix', 'rbses_revoked_at'}
    assert found['rbses_token_hash']['type'].length == 64
    assert found['rbses_auth_method']['type'].length == 16
    assert found['rbses_user_agent']['type'].length == 255
    assert found['rbses_ip_prefix']['type'].length == 48


def test_named_constraints_and_indexes(migration_app):
    upgrade(REVISION)
    insp = inspector()
    assert insp.get_pk_constraint('rbsessions', schema='riftbound') == {
        'name': 'rbsessions_pkey', 'constrained_columns': ['rbses_id']}
    fks = [(fk['name'], fk['referred_table'], fk['constrained_columns'],
            fk['options'].get('ondelete'))
           for fk in insp.get_foreign_keys('rbsessions', schema='riftbound')]
    assert fks == [('rbsessions_user_fk', 'rbusers', ['rbses_user_id'], 'CASCADE')]
    uniques = {u['name']: u['column_names']
               for u in insp.get_unique_constraints('rbsessions', schema='riftbound')}
    assert uniques == {'rbsessions_token_hash_key': ['rbses_token_hash']}
    checks = {c['name'] for c in insp.get_check_constraints('rbsessions', schema='riftbound')}
    assert checks == {'ck_rbsessions_auth_method'}
    indexes = {i['name']: i['column_names']
               for i in insp.get_indexes('rbsessions', schema='riftbound')}
    assert indexes['ix_rbsessions_user_revoked'] == ['rbses_user_id', 'rbses_revoked_at']
    assert indexes['ix_rbsessions_expires_at'] == ['rbses_expires_at']


def test_defaults_and_checks(migration_app):
    upgrade(REVISION)
    run(USER, id=1, name='ana')
    run(SESSION, user=1, hash='a' * 64)
    assert rows('SELECT rbses_remember, rbses_auth_method, rbses_mfa, rbses_expires_at, '
                'rbses_revoked_at FROM riftbound.rbsessions') == [(0, 'password', 0, None, None)]
    with pytest.raises(IntegrityError):
        run(SESSION, user=1, hash='a' * 64)
    for method in ('discord', 'google'):
        run(WITH_METHOD, user=1, hash=method.ljust(64, '0'), method=method)
    with pytest.raises(IntegrityError):
        run(WITH_METHOD, user=1, hash='b' * 64, method='github')
    assert rows('SELECT COUNT(*) FROM riftbound.rbsessions') == [(3,)]


def test_deleting_a_user_deletes_their_sessions(migration_app):
    from app import db
    upgrade(REVISION)
    with db.engine.begin() as conn:
        conn.exec_driver_sql('PRAGMA foreign_keys=ON')
        for user, name in ((1, 'ana'), (2, 'bo')):
            conn.execute(sa.text(USER), dict(id=user, name=name))
            conn.execute(sa.text(SESSION), dict(user=user, hash=str(user) * 64))
        conn.execute(sa.text('DELETE FROM riftbound.rbusers WHERE id = 1'))
    assert rows('SELECT rbses_user_id FROM riftbound.rbsessions') == [(2,)]


def test_kind_check_accepts_sessions_purge(migration_app):
    upgrade(BEFORE)
    with pytest.raises(IntegrityError):
        run(JOB, kind='sessions_purge', status='queued')
    upgrade(REVISION)
    run(JOB, kind='sessions_purge', status='queued')
    for kind in OLD_KINDS:
        run(JOB, kind=kind, status='success')
    with pytest.raises(IntegrityError):
        run(JOB, kind='nope', status='queued')
    assert kinds() == [('sessions_purge',)] + [(k,) for k in OLD_KINDS]


def test_round_trip_and_drift(migration_app):
    upgrade()
    assert drift() == []
    downgrade(BEFORE)
    assert 'rbsessions' not in tables()
    with pytest.raises(IntegrityError):
        run(JOB, kind='sessions_purge', status='queued')
    upgrade()
    assert 'rbsessions' in tables()
    assert drift() == []


def test_downgrade_refuses_while_purge_jobs_exist(migration_app):
    upgrade(REVISION)
    run(USER, id=1, name='ana')
    run(SESSION, user=1, hash='a' * 64)
    run(JOB, kind='heartbeat', status='success')
    run(JOB, kind='sessions_purge', status='success')
    with pytest.raises(RuntimeError) as caught:
        downgrade(BEFORE)
    message = str(caught.value)
    assert "rbjobs holds 1 'sessions_purge' job(s)" in message
    assert 'Nothing was changed' in message
    assert "DELETE FROM riftbound.rbjobs WHERE rbjob_kind = 'sessions_purge'" in message
    # Nothing changed: the table, its rows and the kind are all still there.
    assert rows('SELECT COUNT(*) FROM riftbound.rbsessions') == [(1,)]
    run(JOB, kind='sessions_purge', status='queued')
    run("DELETE FROM riftbound.rbjobs WHERE rbjob_kind = 'sessions_purge'")
    downgrade(BEFORE)
    assert 'rbsessions' not in tables()
    assert kinds() == [('heartbeat',)]


def _module():
    versions = Path(__file__).resolve().parents[1] / 'migrations' / 'versions'
    spec = importlib.util.spec_from_file_location('m_0029', versions / f'{REVISION}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_revision_chain_and_the_data_loss_note():
    module = _module()
    assert (module.revision, module.down_revision) == (REVISION, BEFORE)
    assert 'deletes every session' in ' '.join(module.__doc__.split())


def test_the_downgrade_refuses_offline_mode(monkeypatch):
    module = _module()
    monkeypatch.setattr(module.context, 'is_offline_mode', lambda: True)
    with pytest.raises(RuntimeError) as caught:
        module.downgrade()
    assert 'offline' in str(caught.value)
