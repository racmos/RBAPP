"""F5-c S1 (AC1): migration `0025_decks_v2`: `rbdeckheads` and `rbdeckversions` with their
named constraints, the cascade from user to head to versions, `rbdecks` untouched, round trip
and drift."""
import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from tests.migration_helpers import downgrade, drift, inspector, rows, run, tables, upgrade

BEFORE = '0024_locations'
REVISION = '0025_decks_v2'
NEW_TABLES = {'rbdeckheads', 'rbdeckversions'}
USER = ("INSERT INTO riftbound.rbusers (id, username, email, password_hash, is_admin, is_blocked, "
        "failed_login_count) VALUES (:id, :name, :name || '@test.com', 'x', 0, 0, 0)")
HEAD = ("INSERT INTO riftbound.rbdeckheads (rbdkh_id, rbdkh_user_id, rbdkh_name, rbdkh_mode, "
        "rbdkh_visibility, rbdkh_share_slug, rbdkh_created_at, rbdkh_updated_at) VALUES "
        "(:id, :user, :name, :mode, :visibility, :slug, '2030-01-01 12:00:00', "
        "'2030-01-01 12:00:00')")
VERSION = ("INSERT INTO riftbound.rbdeckversions (rbdkv_deck_id, rbdkv_seq, rbdkv_content, "
           "rbdkv_note, rbdkv_legacy_id, rbdkv_created_at) VALUES (:deck, :seq, '{\"v\": 2}', "
           "NULL, :legacy, '2030-01-01 12:00:00')")
LEGACY = ("INSERT INTO riftbound.rbdecks (id, rbdck_user, rbdck_name, rbdck_seq, rbdck_snapshot, "
          "rbdck_mode, rbdck_cards) VALUES (1, 'ana', 'Azir', 1, '2030-01-01 12:00:00', '1v1', "
          "'{\"main\": [{\"set\": \"OGN\", \"id\": \"1\", \"qty\": 1}]}')")


def _head(id=1, user=1, name='Azir', mode='1v1', visibility='private', slug=None):
    return dict(id=id, user=user, name=name, mode=mode, visibility=visibility, slug=slug)


def test_the_tables_have_their_named_constraints(migration_app):
    upgrade(REVISION)
    assert NEW_TABLES <= tables()
    insp = inspector()
    assert insp.get_pk_constraint('rbdeckheads', schema='riftbound') == {
        'name': 'rbdeckheads_pkey', 'constrained_columns': ['rbdkh_id']}
    assert insp.get_pk_constraint('rbdeckversions', schema='riftbound') == {
        'name': 'rbdeckversions_pkey', 'constrained_columns': ['rbdkv_id']}
    fks = sorted((fk['name'], fk['referred_table'], tuple(fk['referred_columns']),
                  fk['options'].get('ondelete'))
                 for table in NEW_TABLES
                 for fk in insp.get_foreign_keys(table, schema='riftbound'))
    assert fks == [('rbdeckheads_user_fk', 'rbusers', ('id',), 'CASCADE'),
                   ('rbdeckversions_deck_fk', 'rbdeckheads', ('rbdkh_id',), 'CASCADE')]
    assert {c['name'] for c in insp.get_check_constraints('rbdeckheads', schema='riftbound')} == {
        'rbdeckheads_mode_chk', 'rbdeckheads_visibility_chk'}
    assert {c['name'] for c in insp.get_check_constraints(
        'rbdeckversions', schema='riftbound')} == {'rbdeckversions_seq_chk'}
    uniques = {u['name']: u['column_names'] for table in NEW_TABLES
               for u in insp.get_unique_constraints(table, schema='riftbound')}
    assert uniques == {'rbdeckheads_user_name_uq': ['rbdkh_user_id', 'rbdkh_name'],
                       'rbdeckheads_share_slug_uq': ['rbdkh_share_slug'],
                       'rbdeckversions_deck_seq_uq': ['rbdkv_deck_id', 'rbdkv_seq'],
                       'rbdeckversions_legacy_uq': ['rbdkv_legacy_id']}
    columns = {c['name']: c for c in insp.get_columns('rbdeckheads', schema='riftbound')}
    assert columns['rbdkh_name']['type'].length == 80
    assert columns['rbdkh_share_slug']['type'].length == 24
    assert columns['rbdkh_share_slug']['nullable'] is True
    assert columns['rbdkh_current_version_id']['nullable'] is True
    assert columns['rbdkh_legacy_name']['type'].length == 200
    note = next(c for c in insp.get_columns('rbdeckversions', schema='riftbound')
                if c['name'] == 'rbdkv_note')
    assert note['type'].length == 200


def test_defaults_and_value_checks(migration_app):
    upgrade(REVISION)
    run(USER, id=1, name='ana')
    run("INSERT INTO riftbound.rbdeckheads (rbdkh_user_id, rbdkh_name, rbdkh_mode, "
        "rbdkh_created_at, rbdkh_updated_at) VALUES (1, 'Azir', '2v2', "
        "'2030-01-01 12:00:00', '2030-01-01 12:00:00')")
    assert rows('SELECT rbdkh_visibility, rbdkh_share_slug, rbdkh_current_version_id '
                'FROM riftbound.rbdeckheads') == [('private', None, None)]
    for params in (_head(id=2, name='B', mode='3v3'), _head(id=3, name='C', mode='Standard'),
                   _head(id=4, name='D', visibility='shared')):
        with pytest.raises(IntegrityError):
            run(HEAD, **params)
    with pytest.raises(IntegrityError):
        run(VERSION, deck=1, seq=0, legacy=None)
    run(HEAD, **_head(id=5, name='E', visibility='public'))
    assert rows('SELECT rbdkh_name FROM riftbound.rbdeckheads ORDER BY rbdkh_id') == [
        ('Azir',), ('E',)]


def test_names_seqs_slugs_and_legacy_ids_are_unique(migration_app):
    upgrade(REVISION)
    run(USER, id=1, name='ana')
    run(USER, id=2, name='bo')
    run(HEAD, **_head(id=1, slug='abc'))
    run(HEAD, **_head(id=2, user=2, slug=None))           # same name, other user
    run(HEAD, **_head(id=3, name='Other', slug=None))      # several NULL slugs
    run(VERSION, deck=1, seq=1, legacy=7)
    run(VERSION, deck=2, seq=1, legacy=None)
    run(VERSION, deck=3, seq=1, legacy=None)
    for sql, params in ((HEAD, _head(id=4)),
                        (HEAD, _head(id=5, name='Slug', slug='abc')),
                        (VERSION, dict(deck=1, seq=1, legacy=None)),
                        (VERSION, dict(deck=1, seq=2, legacy=7))):
        with pytest.raises(IntegrityError):
            run(sql, **params)
    assert rows('SELECT COUNT(*) FROM riftbound.rbdeckversions') == [(3,)]


def test_deleting_a_user_deletes_their_decks_and_versions(migration_app):
    from app import db
    upgrade(REVISION)
    with db.engine.begin() as conn:
        conn.exec_driver_sql('PRAGMA foreign_keys=ON')   # SQLite enforces FKs only when asked
        for sql, params in ((USER, dict(id=1, name='ana')), (USER, dict(id=2, name='bo')),
                            (HEAD, _head(id=1)), (HEAD, _head(id=2, user=2)),
                            (VERSION, dict(deck=1, seq=1, legacy=None)),
                            (VERSION, dict(deck=2, seq=1, legacy=None))):
            conn.execute(sa.text(sql), params)
        conn.execute(sa.text('DELETE FROM riftbound.rbusers WHERE id = 1'))
    assert rows('SELECT rbdkh_user_id FROM riftbound.rbdeckheads') == [(2,)]
    assert rows('SELECT rbdkv_deck_id FROM riftbound.rbdeckversions') == [(2,)]


def test_round_trip_and_drift_leave_rbdecks_untouched(migration_app):
    upgrade(BEFORE)
    run(USER, id=1, name='ana')
    run("INSERT INTO riftbound.rbset (rbset_id, rbset_name) VALUES ('OGN', 'Origins')")
    run(LEGACY)
    legacy = rows('SELECT * FROM riftbound.rbdecks')
    upgrade()
    assert drift() == []
    assert rows('SELECT * FROM riftbound.rbdecks') == legacy
    assert rows('SELECT COUNT(*) FROM riftbound.rbdeckheads') == [(0,)]   # tables only
    run(HEAD, **_head())
    run(VERSION, deck=1, seq=1, legacy=1)
    downgrade(BEFORE)
    assert not NEW_TABLES & tables()
    assert rows('SELECT * FROM riftbound.rbdecks') == legacy
    upgrade()
    assert NEW_TABLES <= tables()
    assert rows('SELECT COUNT(*) FROM riftbound.rbdeckheads') == [(0,)]
    assert drift() == []


def test_the_revision_chains_and_states_the_data_loss():
    versions = Path(__file__).resolve().parents[1] / 'migrations' / 'versions'
    spec = importlib.util.spec_from_file_location('m_0025', versions / f'{REVISION}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert (module.revision, module.down_revision) == (REVISION, BEFORE)
    doc = ' '.join(module.__doc__.split())
    assert 'drops every v2 deck and version' in doc
    assert 'rbdecks is not modified' in doc
