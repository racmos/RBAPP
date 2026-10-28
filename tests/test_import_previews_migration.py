"""F3-e S1 (AC4): migration `0018_import_previews`: round trip, drift, constraints, cascade."""
import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from tests.migration_helpers import downgrade, drift, inspector, rows, run, tables, upgrade

BEFORE = '0017_jobs_value_snapshot'
USER = ("INSERT INTO riftbound.rbusers (id, username, email, password_hash, is_admin, is_blocked, "
        "failed_login_count) VALUES (:id, :name, :name || '@test.com', 'x', 0, 0, 0)")
PREVIEW = ("INSERT INTO riftbound.rbimportpreviews (rbimp_id, rbimp_user_id, rbimp_format, "
           "rbimp_rows, rbimp_created_at, rbimp_expires_at) VALUES (:id, :user, 'rbapp', '[]', "
           "'2030-01-01 12:00:00', '2030-01-01 12:30:00')")


def test_the_table_has_its_named_constraints_and_index(migration_app):
    upgrade()
    assert 'rbimportpreviews' in tables()
    assert inspector().get_pk_constraint('rbimportpreviews', schema='riftbound') == {
        'name': 'rbimportpreviews_pkey', 'constrained_columns': ['rbimp_id']}
    fks = inspector().get_foreign_keys('rbimportpreviews', schema='riftbound')
    assert [(fk['name'], fk['referred_table']) for fk in fks] == [
        ('rbimportpreviews_user_fk', 'rbusers')]
    assert 'ix_rbimportpreviews_expires' in {
        i['name'] for i in inspector().get_indexes('rbimportpreviews', schema='riftbound')}


def test_round_trip_and_no_drift(migration_app):
    upgrade()
    assert drift() == []
    downgrade(BEFORE)
    assert 'rbimportpreviews' not in tables()
    upgrade()
    assert 'rbimportpreviews' in tables() and drift() == []


def test_the_id_is_unique_and_the_user_is_required(migration_app):
    upgrade()
    run(USER, id=1, name='ana')
    run(PREVIEW, id='a' * 36, user=1)
    with pytest.raises(IntegrityError):
        run(PREVIEW, id='a' * 36, user=1)
    with pytest.raises(IntegrityError):
        run("INSERT INTO riftbound.rbimportpreviews (rbimp_id, rbimp_format, rbimp_rows, "
            "rbimp_created_at, rbimp_expires_at) VALUES ('b', 'rbapp', '[]', '2030-01-01', "
            "'2030-01-01')")


def test_deleting_a_user_deletes_their_previews(migration_app):
    from app import db
    upgrade()
    with db.engine.begin() as conn:
        conn.exec_driver_sql('PRAGMA foreign_keys=ON')
        for user in (1, 2):
            conn.execute(sa.text(USER), dict(id=user, name=f'u{user}'))
            conn.execute(sa.text(PREVIEW), dict(id=str(user) * 36, user=user))
        conn.execute(sa.text('DELETE FROM riftbound.rbusers WHERE id = 1'))
    assert rows('SELECT rbimp_user_id FROM riftbound.rbimportpreviews') == [(2,)]


def test_revision_chains():
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / 'migrations' / 'versions' / '0018_import_previews.py'
    spec = importlib.util.spec_from_file_location('m0018', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert (module.revision, module.down_revision) == ('0018_import_previews', BEFORE)
    assert 'downgrade drops the table' in ' '.join(module.__doc__.split())
