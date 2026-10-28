"""F3-a S3 (AC2): `0015_playset` seeds `rbkeepplayset` from the collection rows that have a playset
(D-F3-12): one row per user and normalized card name, duplicates collapsed."""
import importlib.util
from pathlib import Path

import pytest

from app.services.bans import name_key
from tests.migration_helpers import downgrade, rows, run, upgrade

MIGRATION = Path(__file__).resolve().parents[1] / 'migrations' / 'versions' / '0015_playset.py'
USER = ("INSERT INTO riftbound.rbusers (id, username, email, password_hash, is_admin, is_blocked, "
        "failed_login_count) VALUES (:id, :name, :name || '@test.com', 'x', 0, 0, 0)")
CARD = ("INSERT INTO riftbound.rbcards (rbcar_rbset_id, rbcar_id, rbcar_name) "
        "VALUES (:set, :card, :name)")
LINE = ("INSERT INTO riftbound.rbcollection (rbcol_rbset_id, rbcol_rbcar_id, rbcol_foil, rbcol_user, "
        "rbcol_quantity, rbcol_selling, rbcol_playset, rbcol_chadat) "
        "VALUES (:set, :card, :foil, :user, 3, 'N', :playset, '2026-10-01 10:00:00')")
SEEDED = 'SELECT rbkps_user_id, rbkps_name_key FROM riftbound.rbkeepplayset ORDER BY 1, 2'


def _migration():
    spec = importlib.util.spec_from_file_location('migration_0015_playset', MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _catalog():
    run(USER, id=1, name='ana')
    run(USER, id=2, name='bo')
    run("INSERT INTO riftbound.rbset (rbset_id, rbset_name) VALUES ('OGN', 'Origins'), "
        "('SFD', 'Spiritforged')")
    for set_id, card, name in (('OGN', '1', 'Ember Wisp'), ('SFD', '1', 'Ember  Wisp '),
                               ('OGN', '2', "Kai’Sa, Daughter"), ('OGN', '3', 'Fury Rune')):
        run(CARD, set=set_id, card=card, name=name)


def _line(set_id, card, user, playset, foil='N'):
    run(LINE, set=set_id, card=card, user=user, playset=playset, foil=foil)


def test_one_row_per_user_and_name_with_duplicates_collapsed(migration_app):
    upgrade('0014_collection_selling')
    _catalog()
    _line('OGN', '1', 'ana', 3)
    _line('OGN', '1', 'ana', 2, foil='S')      # same printing, foil
    _line('SFD', '1', 'ana', 1)                # another printing of the same name
    _line('OGN', '2', 'ana', 3)
    _line('OGN', '1', 'bo', 3)
    _line('OGN', '3', 'ana', None)             # no playset: not a mark
    _line('OGN', '3', 'bo', None)
    upgrade()
    assert rows(SEEDED) == [(1, 'ember wisp'), (1, "kai'sa, daughter"), (2, 'ember wisp')]


def test_seeded_keys_are_the_name_key_of_the_names(migration_app):
    upgrade('0014_collection_selling')
    _catalog()
    _line('OGN', '2', 'ana', 3)
    upgrade()
    assert rows(SEEDED) == [(1, name_key("Kai’Sa, Daughter"))]


def test_no_playsets_means_an_empty_table(migration_app):
    upgrade('0014_collection_selling')
    _catalog()
    _line('OGN', '3', 'ana', None)
    upgrade()
    assert rows(SEEDED) == []


def test_the_collection_is_left_alone(migration_app):
    upgrade('0014_collection_selling')
    _catalog()
    _line('OGN', '1', 'ana', 3)
    before = rows('SELECT rbcol_id, rbcol_playset, rbcol_selling, rbcol_sell_qty '
                  'FROM riftbound.rbcollection')
    upgrade()
    assert rows('SELECT rbcol_id, rbcol_playset, rbcol_selling, rbcol_sell_qty '
                'FROM riftbound.rbcollection') == before


def test_a_mark_gets_its_creation_time_from_the_database(migration_app):
    upgrade()
    run(USER, id=1, name='ana')
    run("INSERT INTO riftbound.rbkeepplayset (rbkps_user_id, rbkps_name_key) "
        "VALUES (1, 'ember wisp')")
    assert rows('SELECT rbkps_created_at IS NOT NULL FROM riftbound.rbkeepplayset') == [(True,)]


def test_downgrade_drops_the_table(migration_app):
    upgrade('0014_collection_selling')
    _catalog()
    _line('OGN', '1', 'ana', 3)
    upgrade()
    downgrade('0014_collection_selling')
    from tests.migration_helpers import tables
    assert 'rbkeepplayset' not in tables()
    upgrade()
    assert rows(SEEDED) == [(1, 'ember wisp')]


@pytest.mark.parametrize('name', [
    '  Kai’Sa,   Daughter of the Void ', 'JINX, Loose Cannon', 'Kai‘Sa', '\tTabs\nand  newlines ',
    '', 'Ember Wisp'])
def test_frozen_name_key_matches_the_service(name):
    assert _migration().name_key(name) == name_key(name)
