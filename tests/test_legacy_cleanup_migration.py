"""F11-f (D-F11-9): migration `0028_legacy_schema_cleanup` drops the legacy schema: the table
`rbdecks`, `rbcollection.rbcol_playset`, `rbcards.rbcar_banned`, `rbuserprefs.rbprf_lang` and
the decks v2 provenance fields `rbdeckheads.rbdkh_legacy_name` / `rbdeckversions.rbdkv_legacy_id`
(with their CHECKs and unique constraint). The downgrade re-creates the structure, empty. Every
other row is untouched; round trip and drift (SQLite; the `migrations-pg` CI job runs the same
revisions on PostgreSQL 18)."""
import importlib.util
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from tests.migration_helpers import downgrade, drift, inspector, rows, run, tables, upgrade

BEFORE = '0027_jobs_price_alerts'
REVISION = '0028_legacy_schema_cleanup'
NOW = "'2030-01-01 12:00:00'"
DROPPED_COLUMNS = {
    'rbcollection': 'rbcol_playset',
    'rbcards': 'rbcar_banned',
    'rbuserprefs': 'rbprf_lang',
    'rbdeckheads': 'rbdkh_legacy_name',
    'rbdeckversions': 'rbdkv_legacy_id',
}
USER = ("INSERT INTO riftbound.rbusers (id, username, email, password_hash, is_admin, is_blocked, "
        "failed_login_count) VALUES (:id, :name, :name || '@test.com', 'x', 0, 0, 0)")
CARD = ("INSERT INTO riftbound.rbcards (rbcar_rbset_id, rbcar_id, rbcar_name, rbcar_banned) "
        "VALUES ('OGN', '1', 'Ember Wisp', 'S')")
LINE = ("INSERT INTO riftbound.rbcollection (rbcol_id, rbcol_rbset_id, rbcol_rbcar_id, rbcol_foil, "
        "rbcol_user, rbcol_quantity, rbcol_selling, rbcol_playset, rbcol_sell_qty, rbcol_chadat) "
        f"VALUES (7, 'OGN', '1', 'N', 'ana', 4, 'Y', 3, 1, {NOW})")
PREFS = ("INSERT INTO riftbound.rbuserprefs (rbprf_user_id, rbprf_lang, rbprf_density, "
         f"rbprf_playset_size, rbprf_updated_at) VALUES (1, 'en', 'comfy', 4, {NOW})")
HEAD = ("INSERT INTO riftbound.rbdeckheads (rbdkh_id, rbdkh_user_id, rbdkh_name, rbdkh_mode, "
        "rbdkh_visibility, rbdkh_current_version_id, rbdkh_legacy_name, rbdkh_created_at, "
        f"rbdkh_updated_at) VALUES (5, 1, 'Azir', '1v1', 'private', 9, 'Old Azir', {NOW}, {NOW})")
VERSION = ("INSERT INTO riftbound.rbdeckversions (rbdkv_id, rbdkv_deck_id, rbdkv_seq, "
           "rbdkv_content, rbdkv_note, rbdkv_legacy_id, rbdkv_created_at) VALUES "
           f"(9, 5, 1, '{{\"v\": 2}}', 'Migrated from rbdecks #1.', 1, {NOW})")
LEGACY_DECK = ("INSERT INTO riftbound.rbdecks (id, rbdck_user, rbdck_name, rbdck_seq, "
               f"rbdck_snapshot, rbdck_mode, rbdck_cards) VALUES (1, 'ana', 'Old Azir', 1, {NOW}, "
               "'1v1', '{\"main\": [], \"sideboard\": []}')")

# What stays, read through the columns that survive the upgrade.
KEPT = {
    'user': 'SELECT id, username FROM riftbound.rbusers',
    'card': 'SELECT rbcar_rbset_id, rbcar_id, rbcar_name FROM riftbound.rbcards',
    'line': ('SELECT rbcol_id, rbcol_user, rbcol_quantity, rbcol_selling, rbcol_sell_qty '
             'FROM riftbound.rbcollection'),
    'prefs': ('SELECT rbprf_user_id, rbprf_density, rbprf_playset_size '
              'FROM riftbound.rbuserprefs'),
    'head': ('SELECT rbdkh_id, rbdkh_user_id, rbdkh_name, rbdkh_current_version_id '
             'FROM riftbound.rbdeckheads'),
    'version': ('SELECT rbdkv_id, rbdkv_deck_id, rbdkv_seq, rbdkv_note '
                'FROM riftbound.rbdeckversions'),
}


def _module():
    path = Path(__file__).resolve().parents[1] / 'migrations' / 'versions' / f'{REVISION}.py'
    spec = importlib.util.spec_from_file_location('m_0028', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _seed_before():
    """One row of everything at 0027: legacy values set everywhere."""
    upgrade(BEFORE)
    run(USER, id=1, name='ana')
    run("INSERT INTO riftbound.rbset (rbset_id, rbset_name) VALUES ('OGN', 'Origins')")
    for sql in (CARD, LINE, PREFS, HEAD, VERSION, LEGACY_DECK):
        run(sql)
    return {key: rows(sql) for key, sql in KEPT.items()}


def _columns(table):
    return {c['name']: c for c in inspector().get_columns(table, schema='riftbound')}


def _constraint_names(table):
    insp = inspector()
    return ({c['name'] for c in insp.get_check_constraints(table, schema='riftbound')}
            | {u['name'] for u in insp.get_unique_constraints(table, schema='riftbound')})


def test_the_revision_chains_and_states_the_data_loss():
    module = _module()
    assert (module.revision, module.down_revision) == (REVISION, BEFORE)
    doc = ' '.join(module.__doc__.split())
    assert 'Data loss on upgrade' in doc
    assert 'the downgrade restores the structure only' in doc


def test_the_upgrade_drops_the_legacy_schema_and_keeps_every_other_row(migration_app):
    kept = _seed_before()
    upgrade(REVISION)
    assert 'rbdecks' not in tables()
    for table, column in DROPPED_COLUMNS.items():
        assert column not in _columns(table), (table, column)
    assert 'rbcollection_playset_chk' not in _constraint_names('rbcollection')
    assert 'rbuserprefs_lang_chk' not in _constraint_names('rbuserprefs')
    assert 'rbdeckversions_legacy_uq' not in _constraint_names('rbdeckversions')
    # The constraints that are not legacy survive the table rebuilds.
    assert {'rbcollection_selling_chk', 'rbcollection_sell_qty_chk',
            'rbcollection_quantity_chk'} <= _constraint_names('rbcollection')
    assert {'rbuserprefs_density_chk',
            'rbuserprefs_playset_size_chk'} <= _constraint_names('rbuserprefs')
    assert {'rbdeckversions_deck_seq_uq',
            'rbdeckversions_seq_chk'} <= _constraint_names('rbdeckversions')
    assert {key: rows(sql) for key, sql in KEPT.items()} == kept
    assert rows("SELECT rbcol_selling FROM riftbound.rbcollection") == [('Y',)]   # kept
    assert _drift_before_later_revisions() == []


def _drift_before_later_revisions():
    """Drift at this revision, leaving out the tables later revisions add (0029: rbsessions)."""
    later = {'rbsessions'}
    ops = [op for entry in drift() for op in (entry if isinstance(entry, list) else [entry])]
    return [op for op in ops
            if getattr(op[1], 'name', None) not in later
            and getattr(getattr(op[1], 'table', None), 'name', None) not in later]


def test_the_downgrade_recreates_the_structure_empty(migration_app):
    kept = _seed_before()
    upgrade(REVISION)
    downgrade(BEFORE)
    assert 'rbdecks' in tables()
    assert rows('SELECT COUNT(*) FROM riftbound.rbdecks') == [(0,)]
    assert {'id', 'rbdck_user', 'rbdck_name', 'rbdck_seq', 'rbdck_snapshot',
            'rbdck_description', 'rbdck_mode', 'rbdck_format', 'rbdck_max_set',
            'rbdck_ncards', 'rbdck_orden', 'rbdck_cards'} == set(_columns('rbdecks'))
    insp = inspector()
    assert insp.get_pk_constraint('rbdecks', schema='riftbound')['name'] == 'rbdecks_pkey'
    assert [(fk['name'], fk['referred_table'], fk['referred_columns'])
            for fk in insp.get_foreign_keys('rbdecks', schema='riftbound')] == [
        ('fk_deck_user', 'rbusers', ['username'])]
    assert 'rbdecks_rbdck_user_rbdck_name_rbdck_seq_key' in _constraint_names('rbdecks')
    for table, column in DROPPED_COLUMNS.items():
        assert column in _columns(table), (table, column)
    assert _columns('rbuserprefs')['rbprf_lang']['type'].length == 2
    assert _columns('rbdeckheads')['rbdkh_legacy_name']['type'].length == 200
    assert 'rbcollection_playset_chk' in _constraint_names('rbcollection')
    assert 'rbuserprefs_lang_chk' in _constraint_names('rbuserprefs')
    assert 'rbdeckversions_legacy_uq' in _constraint_names('rbdeckversions')
    # Structure only: the dropped values do not come back.
    assert rows('SELECT rbcol_playset FROM riftbound.rbcollection') == [(None,)]
    assert rows('SELECT rbprf_lang FROM riftbound.rbuserprefs') == [(None,)]
    assert rows('SELECT rbdkh_legacy_name FROM riftbound.rbdeckheads') == [(None,)]
    assert rows('SELECT rbdkv_legacy_id FROM riftbound.rbdeckversions') == [(None,)]
    assert rows('SELECT rbcar_banned FROM riftbound.rbcards') == [('N',)]   # column default
    assert {key: rows(sql) for key, sql in KEPT.items()} == kept


def test_the_recreated_checks_and_unique_constraint_hold(migration_app):
    _seed_before()
    upgrade(REVISION)
    downgrade(BEFORE)
    for sql in ("UPDATE riftbound.rbcollection SET rbcol_playset = 4",
                "UPDATE riftbound.rbuserprefs SET rbprf_lang = 'fr'"):
        with pytest.raises(IntegrityError):
            run(sql)
    run('UPDATE riftbound.rbdeckversions SET rbdkv_legacy_id = 1')
    run("INSERT INTO riftbound.rbdeckversions (rbdkv_deck_id, rbdkv_seq, rbdkv_content, "
        f"rbdkv_legacy_id, rbdkv_created_at) VALUES (5, 2, '{{}}', 2, {NOW})")
    with pytest.raises(IntegrityError):
        run(f"INSERT INTO riftbound.rbdeckversions (rbdkv_deck_id, rbdkv_seq, rbdkv_content, "
            f"rbdkv_legacy_id, rbdkv_created_at) VALUES (5, 3, '{{}}', 1, {NOW})")
    run(LEGACY_DECK)
    with pytest.raises(IntegrityError):
        run(LEGACY_DECK.replace('VALUES (1,', 'VALUES (2,'))   # same user, name and seq


def test_round_trip_and_drift(migration_app):
    kept = _seed_before()
    upgrade()
    assert drift() == []
    downgrade(BEFORE)
    assert drift() != []      # the models are ahead of 0027
    upgrade()
    assert drift() == []
    assert 'rbdecks' not in tables()
    assert {key: rows(sql) for key, sql in KEPT.items()} == kept


def test_flask_decks_migrate_is_gone(app):
    result = app.test_cli_runner().invoke(args=['decks', 'migrate'])
    assert result.exit_code == 2
    assert "No such command 'decks'" in result.output
