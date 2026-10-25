"""F2-a S4: migration `0009_card_bans` creates `rbcardbans` and seeds the official
ban list; round trip 0008 <-> 0009 and drift (SQLite; the `migrations-pg` CI job
runs the same revisions on PostgreSQL 18)."""
import importlib.util
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from app.services.bans import name_key
from tests.migration_helpers import downgrade, drift, inspector, rows, run, tables, upgrade

MIGRATION = Path(__file__).resolve().parents[1] / 'migrations' / 'versions' / '0009_card_bans.py'
REASON = 'Official ban list (riftbound.gg, read 2026-10-24)'
BOTH_MODES = (
    "Aspirant's Climb", 'Obelisk of Power', "Reaver's Row", "The Arena's Greatest",
    'The Dreaming Tree', 'Scrapheap', 'Called Shot', 'Fight or Flight', 'Stacked Deck',
    'Draven, Vanquisher', 'Ekko, Recurrent', 'Stealthy Pursuer',
)
ONLY_2V2 = ('Wuju Bladesman',)
SINCE = {'Ekko, Recurrent': '2026-09-18', 'Stacked Deck': '2026-09-18'}
SEED = sorted(
    [(name, mode, SINCE.get(name, '2026-10-24'), REASON)
     for name in BOTH_MODES for mode in ('1v1', '2v2')]
    + [(name, '2v2', '2026-10-24', REASON) for name in ONLY_2V2])
SELECT_SEED = ('SELECT rbban_name, rbban_mode, rbban_since, rbban_reason '
               'FROM riftbound.rbcardbans ORDER BY rbban_name, rbban_mode')
INSERT = ("INSERT INTO riftbound.rbcardbans (rbban_name_key, rbban_name, rbban_mode, rbban_since) "
          "VALUES (:key, :name, :mode, '2026-10-01')")
COUNT = 'SELECT COUNT(*) FROM riftbound.rbcardbans'


def _migration():
    spec = importlib.util.spec_from_file_location('migration_0009_card_bans', MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rejected(key, name, mode):
    before = rows(COUNT)
    with pytest.raises(IntegrityError):
        run(INSERT, key=key, name=name, mode=mode)
    assert rows(COUNT) == before


def test_revision_chains_after_0008():
    module = _migration()
    assert (module.revision, module.down_revision) == ('0009_card_bans', '0008_jobs_daily_prices')


def test_docstring_states_the_data_loss_rules():
    doc = ' '.join(_migration().__doc__.split())
    assert 'No data loss on upgrade' in doc
    assert 'downgrade loses every ban, including those added after' in doc


def test_0009_has_the_table(migration_app):
    upgrade('0009_card_bans')
    assert rows('SELECT version_num FROM riftbound.alembic_version') == [('0009_card_bans',)]
    assert 'rbcardbans' in tables()


def test_round_trip_and_no_drift(migration_app):
    upgrade('0008_jobs_daily_prices')
    assert 'rbcardbans' not in tables()
    upgrade()
    run(INSERT, key='jinx, loose cannon', name='Jinx, Loose Cannon', mode='1v1')
    downgrade('0008_jobs_daily_prices')
    assert 'rbcardbans' not in tables()
    assert {'rbjobs', 'rbcards'} <= tables()
    upgrade()
    # the ban added after the upgrade is gone; the seed is back
    assert rows(SELECT_SEED) == SEED
    assert drift() == []


def test_named_constraints(migration_app):
    upgrade()
    assert inspector().get_pk_constraint('rbcardbans', schema='riftbound') == {
        'name': 'rbcardbans_pkey', 'constrained_columns': ['rbban_id']}
    uniques = inspector().get_unique_constraints('rbcardbans', schema='riftbound')
    assert [(u['name'], u['column_names']) for u in uniques] == [
        ('rbcardbans_name_mode_key', ['rbban_name_key', 'rbban_mode'])]
    checks = inspector().get_check_constraints('rbcardbans', schema='riftbound')
    assert [c['name'] for c in checks] == ['rbcardbans_mode_chk']


def test_check_rejects_3v3(migration_app):
    upgrade()
    _rejected('jinx, loose cannon', 'Jinx, Loose Cannon', '3v3')


def test_unique_rejects_a_duplicate_key_and_mode(migration_app):
    upgrade()
    run(INSERT, key='jinx, loose cannon', name='Jinx, Loose Cannon', mode='1v1')
    _rejected('jinx, loose cannon', 'JINX, LOOSE CANNON', '1v1')
    run(INSERT, key='jinx, loose cannon', name='Jinx, Loose Cannon', mode='2v2')
    assert rows(COUNT) == [(27,)]


def test_seeds_exactly_the_official_list(migration_app):
    upgrade()
    assert len(SEED) == 25
    assert rows(SELECT_SEED) == SEED
    assert rows('SELECT rbban_mode, COUNT(*) FROM riftbound.rbcardbans '
                'GROUP BY rbban_mode ORDER BY rbban_mode') == [('1v1', 12), ('2v2', 13)]
    assert rows('SELECT COUNT(*) FROM riftbound.rbcardbans WHERE rbban_created_at IS NULL') == [
        (0,)]


def test_seeded_keys_are_the_name_key_of_the_names(migration_app):
    upgrade()
    for key, name in rows('SELECT rbban_name_key, rbban_name FROM riftbound.rbcardbans'):
        assert key == name_key(name)


def test_rbcar_banned_is_not_a_source_and_is_left_untouched(migration_app):
    upgrade('0008_jobs_daily_prices')
    run("INSERT INTO riftbound.rbset (rbset_id, rbset_name) VALUES ('OGN', 'Origins')")
    run("INSERT INTO riftbound.rbcards (rbcar_rbset_id, rbcar_id, rbcar_name, rbcar_banned) "
        "VALUES ('OGN', '79', 'Jinx, Loose Cannon', 'S'), ('OGN', '80', 'Called Shot', 'N')")
    upgrade()
    assert rows(SELECT_SEED) == SEED
    downgrade('0008_jobs_daily_prices')
    assert rows('SELECT rbcar_id, rbcar_banned FROM riftbound.rbcards ORDER BY rbcar_id') == [
        ('79', 'S'), ('80', 'N')]


@pytest.mark.parametrize('name', [
    '  Kai’Sa,   Daughter of the Void ', 'JINX, Loose Cannon', 'jinx, loose cannon',
    'Kai‘Sa', '\tTabs\nand  newlines ', '', *BOTH_MODES, *ONLY_2V2])
def test_frozen_name_key_matches_the_service(name):
    assert _migration().name_key(name) == name_key(name)
