"""F9-h S1 (AC1): migration `0032_api_keys`: the `rbapikeys` table with its named constraints,
the cascade from `rbusers`, the round trip and the drift check (SQLite; the `migrations-pg` CI
job runs migrations on PostgreSQL 18)."""
import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from app.models import RbApiKey
from tests.migration_helpers import downgrade, drift, inspector, rows, run, tables, upgrade

BEFORE = '0031_mfa'
REVISION = '0032_api_keys'
USER = ("INSERT INTO riftbound.rbusers (id, username, email, password_hash, is_admin, is_blocked, "
        "failed_login_count) VALUES (:id, :name, :name || '@test.com', 'x', 0, 0, 0)")
KEY = ("INSERT INTO riftbound.rbapikeys (rbapk_user_id, rbapk_prefix, rbapk_key_hash, "
       "rbapk_created_at) VALUES (:user, 'rb_live_abcdef', :hash, '2030-01-01 12:00:00')")


def columns(table):
    return {c['name']: c for c in inspector().get_columns(table, schema='riftbound')}


def test_the_model_uses_the_migration_table():
    assert RbApiKey.__tablename__ == 'rbapikeys'


def test_the_columns(migration_app):
    upgrade(REVISION)
    found = columns('rbapikeys')
    assert list(found) == ['rbapk_id', 'rbapk_user_id', 'rbapk_prefix', 'rbapk_key_hash',
                           'rbapk_created_at', 'rbapk_last_used_at']
    nullable = {name for name, c in found.items() if c['nullable']}
    assert nullable == {'rbapk_last_used_at'}
    assert isinstance(found['rbapk_user_id']['type'], sa.Integer)
    assert isinstance(found['rbapk_prefix']['type'], sa.String)
    assert found['rbapk_prefix']['type'].length == 16
    assert isinstance(found['rbapk_key_hash']['type'], sa.CHAR)
    assert found['rbapk_key_hash']['type'].length == 64
    assert isinstance(found['rbapk_created_at']['type'], sa.DateTime)
    assert isinstance(found['rbapk_last_used_at']['type'], sa.DateTime)


def test_named_constraints(migration_app):
    upgrade(REVISION)
    insp = inspector()
    assert insp.get_pk_constraint('rbapikeys', schema='riftbound') == {
        'name': 'rbapikeys_pkey', 'constrained_columns': ['rbapk_id']}
    fks = [(fk['name'], fk['referred_table'], fk['referred_columns'],
            fk['constrained_columns'], fk['options'].get('ondelete'))
           for fk in insp.get_foreign_keys('rbapikeys', schema='riftbound')]
    assert fks == [('rbapikeys_user_fk', 'rbusers', ['id'], ['rbapk_user_id'], 'CASCADE')]
    uniques = {u['name']: u['column_names']
               for u in insp.get_unique_constraints('rbapikeys', schema='riftbound')}
    assert uniques == {'rbapikeys_user_key': ['rbapk_user_id'],
                       'rbapikeys_key_hash_key': ['rbapk_key_hash']}


def test_one_key_per_user_and_unique_hashes(migration_app):
    upgrade(REVISION)
    run(USER, id=1, name='ana')
    run(USER, id=2, name='bo')
    run(KEY, user=1, hash='a' * 64)
    with pytest.raises(IntegrityError):
        run(KEY, user=1, hash='b' * 64)
    with pytest.raises(IntegrityError):
        run(KEY, user=2, hash='a' * 64)
    run(KEY, user=2, hash='c' * 64)
    assert rows('SELECT rbapk_id, rbapk_user_id, rbapk_last_used_at FROM riftbound.rbapikeys '
                'ORDER BY rbapk_id') == [(1, 1, None), (2, 2, None)]


def test_deleting_a_user_deletes_the_key(migration_app):
    from app import db
    upgrade(REVISION)
    with db.engine.begin() as conn:
        conn.exec_driver_sql('PRAGMA foreign_keys=ON')
        for user, name in ((1, 'ana'), (2, 'bo')):
            conn.execute(sa.text(USER), dict(id=user, name=name))
            conn.execute(sa.text(KEY), dict(user=user, hash=str(user) * 64))
        conn.execute(sa.text('DELETE FROM riftbound.rbusers WHERE id = 1'))
    assert rows('SELECT rbapk_user_id FROM riftbound.rbapikeys') == [(2,)]


def test_round_trip_and_drift(migration_app):
    upgrade()
    assert drift() == []
    run(USER, id=1, name='ana')
    run(KEY, user=1, hash='a' * 64)
    downgrade(BEFORE)
    assert 'rbapikeys' not in tables()
    assert rows('SELECT username FROM riftbound.rbusers') == [('ana',)]
    upgrade()
    assert 'rbapikeys' in tables()
    assert rows('SELECT COUNT(*) FROM riftbound.rbapikeys') == [(0,)]
    assert drift() == []


def _module():
    versions = Path(__file__).resolve().parents[1] / 'migrations' / 'versions'
    spec = importlib.util.spec_from_file_location('m_0032', versions / f'{REVISION}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_revision_chain_and_the_data_loss_note():
    module = _module()
    assert (module.revision, module.down_revision) == (REVISION, BEFORE)
    doc = ' '.join(module.__doc__.split())
    assert 'every API key stops working' in doc
