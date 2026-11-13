"""F9-b S1 (AC1): migration `0030_user_profile`: the `rbuserprofile` table with its named
constraints, `rbusers.email` / `password_hash` nullable, `rbusers.password_changed_at`, the
guarded downgrade and the drift check (SQLite; the `migrations-pg` CI job runs migrations on
PostgreSQL 18)."""
import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from tests.migration_helpers import downgrade, drift, inspector, rows, run, tables, upgrade

BEFORE = '0029_sessions'
REVISION = '0030_user_profile'
USER = ("INSERT INTO riftbound.rbusers (id, username, email, password_hash, is_admin, is_blocked, "
        "failed_login_count) VALUES (:id, :name, :email, :hash, 0, 0, 0)")
PROFILE = ("INSERT INTO riftbound.rbuserprofile (rbupf_user_id, rbupf_display_name, "
           "rbupf_updated_at) VALUES (:user, :name, '2030-01-01 12:00:00')")


def add_user(user_id, name, email='', hash_='x'):
    run(USER, id=user_id, name=name,
        email=f'{name}@test.com' if email == '' else email, hash=hash_)


def columns(table):
    return {c['name']: c for c in inspector().get_columns(table, schema='riftbound')}


def test_the_profile_table_columns(migration_app):
    upgrade(REVISION)
    assert 'rbuserprofile' in tables()
    found = columns('rbuserprofile')
    assert list(found) == [
        'rbupf_user_id', 'rbupf_display_name', 'rbupf_bio', 'rbupf_country', 'rbupf_city',
        'rbupf_avatar_file', 'rbupf_avatar_version', 'rbupf_updated_at']
    nullable = {name for name, c in found.items() if c['nullable']}
    assert nullable == {'rbupf_display_name', 'rbupf_bio', 'rbupf_country', 'rbupf_city',
                        'rbupf_avatar_file'}
    assert found['rbupf_display_name']['type'].length == 40
    assert found['rbupf_bio']['type'].length == 240
    assert found['rbupf_country']['type'].length == 2
    assert isinstance(found['rbupf_country']['type'], sa.CHAR)
    assert found['rbupf_city']['type'].length == 80
    assert found['rbupf_avatar_file']['type'].length == 64


def test_the_user_columns(migration_app):
    upgrade(BEFORE)
    before = columns('rbusers')
    assert not before['email']['nullable'] and not before['password_hash']['nullable']
    assert 'password_changed_at' not in before
    upgrade(REVISION)
    after = columns('rbusers')
    assert after['email']['nullable'] and after['password_hash']['nullable']
    assert after['password_changed_at']['nullable']
    assert isinstance(after['password_changed_at']['type'], sa.DateTime)
    uniques = {u['name']: u['column_names']
               for u in inspector().get_unique_constraints('rbusers', schema='riftbound')}
    assert uniques['rbusers_email_key'] == ['email']
    assert uniques['rbusers_username_key'] == ['username']


def test_named_constraints(migration_app):
    upgrade(REVISION)
    insp = inspector()
    assert insp.get_pk_constraint('rbuserprofile', schema='riftbound') == {
        'name': 'rbuserprofile_pkey', 'constrained_columns': ['rbupf_user_id']}
    fks = [(fk['name'], fk['referred_table'], fk['constrained_columns'],
            fk['options'].get('ondelete'))
           for fk in insp.get_foreign_keys('rbuserprofile', schema='riftbound')]
    assert fks == [('rbuserprofile_user_fk', 'rbusers', ['rbupf_user_id'], 'CASCADE')]


def test_existing_users_keep_their_data_and_get_no_backfill(migration_app):
    upgrade(BEFORE)
    add_user(1, 'ana')
    upgrade(REVISION)
    assert rows('SELECT username, email, password_hash, password_changed_at '
                'FROM riftbound.rbusers') == [('ana', 'ana@test.com', 'x', None)]
    assert rows('SELECT COUNT(*) FROM riftbound.rbuserprofile') == [(0,)]


def test_several_users_without_email_or_password_coexist(migration_app):
    upgrade(REVISION)
    add_user(1, 'ana', email=None, hash_=None)
    add_user(2, 'bo', email=None, hash_=None)
    add_user(3, 'cy', email='same@test.com')
    with pytest.raises(IntegrityError):
        add_user(4, 'di', email='same@test.com')
    assert rows('SELECT username FROM riftbound.rbusers ORDER BY id') == [
        ('ana',), ('bo',), ('cy',)]


def test_the_avatar_version_defaults_to_zero(migration_app):
    upgrade(REVISION)
    add_user(1, 'ana')
    run(PROFILE, user=1, name='Ana')
    assert rows('SELECT rbupf_display_name, rbupf_avatar_version, rbupf_bio '
                'FROM riftbound.rbuserprofile') == [('Ana', 0, None)]
    with pytest.raises(IntegrityError):
        run(PROFILE, user=1, name='Again')


def test_deleting_a_user_deletes_the_profile(migration_app):
    from app import db
    upgrade(REVISION)
    with db.engine.begin() as conn:
        conn.exec_driver_sql('PRAGMA foreign_keys=ON')
        for user, name in ((1, 'ana'), (2, 'bo')):
            conn.execute(sa.text(USER), dict(id=user, name=name, email=f'{name}@test.com',
                                             hash='x'))
            conn.execute(sa.text(PROFILE), dict(user=user, name=name))
        conn.execute(sa.text('DELETE FROM riftbound.rbusers WHERE id = 1'))
    assert rows('SELECT rbupf_user_id FROM riftbound.rbuserprofile') == [(2,)]


def test_round_trip_and_drift(migration_app):
    upgrade()
    assert drift() == []
    downgrade(BEFORE)
    assert 'rbuserprofile' not in tables()
    assert 'password_changed_at' not in columns('rbusers')
    assert not columns('rbusers')['email']['nullable']
    assert not columns('rbusers')['password_hash']['nullable']
    upgrade()
    assert 'rbuserprofile' in tables()
    assert drift() == []


def test_the_downgrade_keeps_complete_accounts(migration_app):
    upgrade(REVISION)
    add_user(1, 'ana')
    run("UPDATE riftbound.rbusers SET password_changed_at = '2030-01-01 12:00:00'")
    run(PROFILE, user=1, name='Ana')
    downgrade(BEFORE)
    assert rows('SELECT username, email, password_hash FROM riftbound.rbusers') == [
        ('ana', 'ana@test.com', 'x')]
    with pytest.raises(IntegrityError):
        add_user(2, 'bo', email=None)


@pytest.mark.parametrize('email, hash_', [(None, 'x'), ('bo@test.com', None), (None, None)])
def test_the_downgrade_refuses_accounts_without_email_or_password(migration_app, email, hash_):
    upgrade(REVISION)
    add_user(1, 'ana')
    add_user(2, 'bo', email=email, hash_=hash_)
    run(PROFILE, user=2, name='Bo')
    with pytest.raises(RuntimeError) as caught:
        downgrade(BEFORE)
    message = str(caught.value)
    assert '1 account(s) without an e-mail or a password' in message
    assert ': bo.' in message
    assert 'ana' not in message
    assert 'Nothing was changed' in message
    # Nothing changed: the table, its row, the new column and the nullability are all there.
    assert 'rbuserprofile' in tables()
    assert rows('SELECT rbupf_display_name FROM riftbound.rbuserprofile') == [('Bo',)]
    assert 'password_changed_at' in columns('rbusers')
    assert columns('rbusers')['email']['nullable']
    assert rows('SELECT version_num FROM riftbound.alembic_version') == [(REVISION,)]


def test_the_refusal_lists_at_most_20_usernames(migration_app):
    upgrade(REVISION)
    for n in range(1, 23):
        add_user(n, f'user{n:02d}', email=None)
    with pytest.raises(RuntimeError) as caught:
        downgrade(BEFORE)
    message = str(caught.value)
    assert '22 account(s)' in message
    listed = ', '.join(f'user{n:02d}' for n in range(1, 21))
    assert f': {listed} and 2 more.' in message
    assert 'user21' not in message


def _module():
    versions = Path(__file__).resolve().parents[1] / 'migrations' / 'versions'
    spec = importlib.util.spec_from_file_location('m_0030', versions / f'{REVISION}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_revision_chain_and_the_data_loss_note():
    module = _module()
    assert (module.revision, module.down_revision) == (REVISION, BEFORE)
    doc = ' '.join(module.__doc__.split())
    assert 'deletes every profile' in doc
    assert 'password_changed_at' in doc


def test_the_downgrade_refuses_offline_mode(monkeypatch):
    module = _module()
    monkeypatch.setattr(module.context, 'is_offline_mode', lambda: True)
    with pytest.raises(RuntimeError) as caught:
        module.downgrade()
    assert 'offline' in str(caught.value)
