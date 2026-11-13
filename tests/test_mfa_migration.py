"""F9-d S3 (AC1): migration `0031_mfa`: the `rbusermfa` and `rbrecoverycodes` tables with their
named constraints and index, cascades from `rbusers`, the round trip and the drift check
(SQLite; the `migrations-pg` CI job runs migrations on PostgreSQL 18)."""
import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from app.models import RbRecoveryCode, RbUserMfa
from tests.migration_helpers import downgrade, drift, inspector, rows, run, tables, upgrade

BEFORE = '0030_user_profile'
REVISION = '0031_mfa'
USER = ("INSERT INTO riftbound.rbusers (id, username, email, password_hash, is_admin, is_blocked, "
        "failed_login_count) VALUES (:id, :name, :name || '@test.com', 'x', 0, 0, 0)")
MFA = ("INSERT INTO riftbound.rbusermfa (rbmfa_user_id, rbmfa_secret_enc, rbmfa_created_at) "
       "VALUES (:user, 'gAAAA-ciphertext', '2030-01-01 12:00:00')")
CODE = ("INSERT INTO riftbound.rbrecoverycodes (rbrco_user_id, rbrco_code_hash) "
        "VALUES (:user, :hash)")


def columns(table):
    return {c['name']: c for c in inspector().get_columns(table, schema='riftbound')}


def test_the_models_use_the_migration_tables():
    assert (RbUserMfa.__tablename__, RbRecoveryCode.__tablename__) == (
        'rbusermfa', 'rbrecoverycodes')


def test_the_mfa_table_columns(migration_app):
    upgrade(REVISION)
    found = columns('rbusermfa')
    assert list(found) == ['rbmfa_user_id', 'rbmfa_secret_enc', 'rbmfa_enabled_at',
                           'rbmfa_last_step', 'rbmfa_created_at']
    nullable = {name for name, c in found.items() if c['nullable']}
    assert nullable == {'rbmfa_enabled_at', 'rbmfa_last_step'}
    assert isinstance(found['rbmfa_secret_enc']['type'], sa.Text)
    assert isinstance(found['rbmfa_last_step']['type'], sa.BigInteger)
    assert isinstance(found['rbmfa_enabled_at']['type'], sa.DateTime)
    assert isinstance(found['rbmfa_created_at']['type'], sa.DateTime)


def test_the_recovery_code_table_columns(migration_app):
    upgrade(REVISION)
    found = columns('rbrecoverycodes')
    assert list(found) == ['rbrco_id', 'rbrco_user_id', 'rbrco_code_hash', 'rbrco_used_at']
    nullable = {name for name, c in found.items() if c['nullable']}
    assert nullable == {'rbrco_used_at'}
    assert isinstance(found['rbrco_code_hash']['type'], sa.CHAR)
    assert found['rbrco_code_hash']['type'].length == 64


def test_named_constraints_and_index(migration_app):
    upgrade(REVISION)
    insp = inspector()
    assert insp.get_pk_constraint('rbusermfa', schema='riftbound') == {
        'name': 'rbusermfa_pkey', 'constrained_columns': ['rbmfa_user_id']}
    assert insp.get_pk_constraint('rbrecoverycodes', schema='riftbound') == {
        'name': 'rbrecoverycodes_pkey', 'constrained_columns': ['rbrco_id']}

    def fks(table):
        return [(fk['name'], fk['referred_table'], fk['referred_columns'],
                 fk['constrained_columns'], fk['options'].get('ondelete'))
                for fk in insp.get_foreign_keys(table, schema='riftbound')]

    assert fks('rbusermfa') == [
        ('rbusermfa_user_fk', 'rbusers', ['id'], ['rbmfa_user_id'], 'CASCADE')]
    assert fks('rbrecoverycodes') == [
        ('rbrecoverycodes_user_fk', 'rbusers', ['id'], ['rbrco_user_id'], 'CASCADE')]
    indexes = {i['name']: i['column_names']
               for i in insp.get_indexes('rbrecoverycodes', schema='riftbound')}
    assert indexes == {'ix_rbrecoverycodes_user': ['rbrco_user_id']}


def test_one_mfa_row_per_user_and_ids_are_generated(migration_app):
    upgrade(REVISION)
    run(USER, id=1, name='ana')
    run(MFA, user=1)
    with pytest.raises(IntegrityError):
        run(MFA, user=1)
    run(CODE, user=1, hash='a' * 64)
    run(CODE, user=1, hash='b' * 64)
    assert rows('SELECT rbrco_id, rbrco_used_at FROM riftbound.rbrecoverycodes '
                'ORDER BY rbrco_id') == [(1, None), (2, None)]
    assert rows('SELECT rbmfa_enabled_at, rbmfa_last_step FROM riftbound.rbusermfa') == [
        (None, None)]


def test_deleting_a_user_deletes_the_2fa_rows(migration_app):
    from app import db
    upgrade(REVISION)
    with db.engine.begin() as conn:
        conn.exec_driver_sql('PRAGMA foreign_keys=ON')
        for user, name in ((1, 'ana'), (2, 'bo')):
            conn.execute(sa.text(USER), dict(id=user, name=name))
            conn.execute(sa.text(MFA), dict(user=user))
            conn.execute(sa.text(CODE), dict(user=user, hash=str(user) * 64))
        conn.execute(sa.text('DELETE FROM riftbound.rbusers WHERE id = 1'))
    assert rows('SELECT rbmfa_user_id FROM riftbound.rbusermfa') == [(2,)]
    assert rows('SELECT rbrco_user_id FROM riftbound.rbrecoverycodes') == [(2,)]


def test_round_trip_and_drift(migration_app):
    upgrade()
    assert drift() == []
    run(USER, id=1, name='ana')
    run(MFA, user=1)
    run(CODE, user=1, hash='a' * 64)
    downgrade(BEFORE)
    assert not {'rbusermfa', 'rbrecoverycodes'} & tables()
    assert rows('SELECT username FROM riftbound.rbusers') == [('ana',)]
    upgrade()
    assert {'rbusermfa', 'rbrecoverycodes'} <= tables()
    assert rows('SELECT COUNT(*) FROM riftbound.rbusermfa') == [(0,)]
    assert drift() == []


def _module():
    versions = Path(__file__).resolve().parents[1] / 'migrations' / 'versions'
    spec = importlib.util.spec_from_file_location('m_0031', versions / f'{REVISION}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_revision_chain_and_the_data_loss_note():
    module = _module()
    assert (module.revision, module.down_revision) == (REVISION, BEFORE)
    doc = ' '.join(module.__doc__.split())
    assert "every user's two-factor authentication is lost" in doc
