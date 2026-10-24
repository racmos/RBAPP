"""F2-a S2/S5/S6: the ban service `app/services/bans.py` (normalization, reads,
add/remove), through its public functions and the rows they leave."""
import dataclasses
from datetime import date

import pytest
import sqlalchemy as sa

from app import db
from app.models import RbCard, RbCardBan, RbSet
from app.services import bans
from app.services.bans import name_key


# --- S2 name_key ---------------------------------------------------------------------

def test_name_key_trims_casefolds_unifies_apostrophes_and_spaces():
    assert name_key("  Kai’Sa,   Daughter of the Void ") == "kai'sa, daughter of the void"


def test_name_key_ignores_case():
    assert name_key('JINX, Loose Cannon') == name_key('jinx, loose cannon')


@pytest.mark.parametrize('raw, key', [
    ('Kai‘Sa', "kai'sa"),                       # U+2018 too
    ("Kai'Sa", "kai'sa"),
    ('Straße', 'strasse'),                      # casefold, not lower
    ('\tTabs\nand  newlines ', 'tabs and newlines'),
    (' \t\n ', ''),
])
def test_name_key_rules(raw, key):
    assert name_key(raw) == key


# --- helpers -------------------------------------------------------------------------

def _catalog(*cards):
    """Add (set_id, card_id, name) cards; sets are created as needed."""
    for set_id in dict.fromkeys(set_id for set_id, _, _ in cards):
        if db.session.get(RbSet, set_id) is None:
            db.session.add(RbSet(rbset_id=set_id, rbset_name=f'Set {set_id}'))
    for set_id, card_id, name in cards:
        db.session.add(RbCard(rbcar_rbset_id=set_id, rbcar_id=card_id, rbcar_name=name))
    db.session.commit()


def _rows():
    db.session.expire_all()
    return [(b.rbban_name_key, b.rbban_name, b.rbban_mode, b.rbban_since, b.rbban_reason)
            for b in db.session.execute(
                sa.select(RbCardBan).order_by(RbCardBan.rbban_id)).scalars()]


@pytest.fixture
def queries(app):
    """Count the SQL statements run while the test body executes."""
    seen = []

    def count(*args):
        seen.append(args[2])

    sa.event.listen(db.engine, 'before_cursor_execute', count)
    yield seen
    sa.event.remove(db.engine, 'before_cursor_execute', count)


JINX = 'Jinx, Loose Cannon'
SEP1 = date(2026, 9, 1)


# --- S5 reads ------------------------------------------------------------------------

def test_reads_with_no_bans(app):
    assert bans.ban_map() == {}
    assert bans.list_bans() == []
    assert bans.card_bans(JINX) == {'1v1': False, '2v2': False}
    assert bans.ban_info(JINX) == []


def test_ban_map_is_keyed_by_name_key_then_mode(app):
    bans.add_ban(JINX, ['2v2', '1v1'], since=SEP1, reason='Too strong', force=True)
    bans.add_ban('Called Shot', ['2v2'], since=SEP1, force=True)
    assert bans.ban_map() == {
        'jinx, loose cannon': {
            '1v1': bans.BanEntry(JINX, '1v1', SEP1, 'Too strong'),
            '2v2': bans.BanEntry(JINX, '2v2', SEP1, 'Too strong'),
        },
        'called shot': {'2v2': bans.BanEntry('Called Shot', '2v2', SEP1, None)},
    }


def test_ban_entry_is_a_frozen_dataclass():
    entry = bans.BanEntry(name=JINX, mode='1v1', since=SEP1, reason=None)
    assert dataclasses.is_dataclass(entry)
    assert [f.name for f in dataclasses.fields(entry)] == ['name', 'mode', 'since', 'reason']
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.mode = '2v2'


def test_card_bans_always_has_both_modes_and_matches_by_name_key(app):
    bans.add_ban(JINX, ['2v2'], since=SEP1, force=True)
    assert bans.card_bans(JINX) == {'1v1': False, '2v2': True}
    assert bans.card_bans('  jinx,   LOOSE cannon ') == {'1v1': False, '2v2': True}
    assert list(bans.card_bans(JINX)) == ['1v1', '2v2']
    assert bans.card_bans('Called Shot') == {'1v1': False, '2v2': False}


def test_preloaded_ban_map_means_no_query(app, queries):
    bans.add_ban(JINX, ['1v1'], since=SEP1, force=True)
    preloaded = bans.ban_map()
    queries.clear()
    assert bans.card_bans(JINX, preloaded) == {'1v1': True, '2v2': False}
    assert bans.card_bans('Other', bans=preloaded) == {'1v1': False, '2v2': False}
    assert bans.ban_info(JINX, bans=preloaded) == [
        {'mode': '1v1', 'since': '2026-09-01', 'reason': None}]
    assert queries == []


def test_ban_info_is_in_game_modes_order_with_iso_dates(app):
    bans.add_ban(JINX, ['2v2'], since=date(2026, 9, 18), reason='Wave 2', force=True)
    bans.add_ban(JINX, ['1v1'], since=SEP1, force=True)
    assert bans.ban_info(JINX.upper()) == [
        {'mode': '1v1', 'since': '2026-09-01', 'reason': None},
        {'mode': '2v2', 'since': '2026-09-18', 'reason': 'Wave 2'},
    ]


def test_list_bans_orders_by_mode_then_name_key(app):
    bans.add_ban('zed', ['2v2', '1v1'], since=SEP1, force=True)
    bans.add_ban('Ahri', ['2v2'], since=SEP1, force=True)
    bans.add_ban('called shot', ['1v1'], since=SEP1, force=True)
    bans.add_ban('Bard', ['1v1'], since=SEP1, force=True)
    listed = [(b.mode, b.name) for b in bans.list_bans()]
    assert listed == [('1v1', 'Bard'), ('1v1', 'called shot'), ('1v1', 'zed'),
                      ('2v2', 'Ahri'), ('2v2', 'zed')]
    assert [(b.mode, b.name) for b in bans.list_bans('2v2')] == [('2v2', 'Ahri'), ('2v2', 'zed')]
    assert [(b.mode, b.name) for b in bans.list_bans(mode='1v1')] == listed[:3]
    assert all(isinstance(b, bans.BanEntry) for b in bans.list_bans())


# --- S6 add_ban ----------------------------------------------------------------------

def test_add_ban_uses_the_catalog_spelling_of_the_first_match(app):
    _catalog(('OGNX', '257', 'jinx,  LOOSE cannon'), ('OGN', '79', JINX),
             ('OGN', '1', 'Called Shot'))
    assert bans.add_ban('JINX, loose cannon', ['1v1'], since=SEP1) == [('1v1', 'added')]
    assert _rows() == [('jinx, loose cannon', JINX, '1v1', SEP1, None)]


def test_add_ban_first_match_orders_by_card_id_within_a_set(app):
    _catalog(('OGN', '80', 'Called  Shot'), ('OGN', '100', 'CALLED SHOT'))
    bans.add_ban('called shot', ['2v2'], since=SEP1)
    assert _rows() == [('called shot', 'CALLED SHOT', '2v2', SEP1, None)]   # '100' < '80'


def test_add_ban_defaults_since_to_today(app, frozen_clock):
    _catalog(('OGN', '79', JINX))
    assert bans.add_ban(JINX, ['1v1', '2v2'], reason='Too strong') == [
        ('1v1', 'added'), ('2v2', 'added')]
    assert _rows() == [('jinx, loose cannon', JINX, '1v1', date(2030, 1, 1), 'Too strong'),
                       ('jinx, loose cannon', JINX, '2v2', date(2030, 1, 1), 'Too strong')]
    ban = db.session.execute(sa.select(RbCardBan).limit(1)).scalar_one()
    assert ban.rbban_created_at == frozen_clock()


def test_add_ban_again_is_unchanged(app):
    _catalog(('OGN', '79', JINX))
    bans.add_ban(JINX, ['1v1'], since=SEP1, reason='Too strong')
    before = _rows()
    assert bans.add_ban(JINX, ['1v1']) == [('1v1', 'unchanged')]
    assert bans.add_ban(JINX, ['1v1'], since=SEP1, reason='Too strong') == [('1v1', 'unchanged')]
    assert bans.add_ban(JINX, ['1v1'], reason='   ') == [('1v1', 'unchanged')]
    assert _rows() == before


def test_add_ban_updates_since_or_reason_when_they_differ(app):
    _catalog(('OGN', '79', JINX))
    bans.add_ban(JINX, ['1v1'], since=SEP1)
    assert bans.add_ban(JINX, ['1v1', '2v2'], reason='Too strong') == [
        ('1v1', 'updated'), ('2v2', 'added')]
    assert bans.add_ban(JINX, ['1v1'], since=date(2026, 9, 18)) == [('1v1', 'updated')]
    assert _rows()[0] == ('jinx, loose cannon', JINX, '1v1', date(2026, 9, 18), 'Too strong')


def test_add_ban_unknown_name_raises_and_writes_nothing(app):
    _catalog(('OGN', '79', JINX))
    with pytest.raises(bans.UnknownCardName) as caught:
        bans.add_ban('Jinx', ['1v1', '2v2'])
    assert caught.value.args == ('Jinx',)
    assert _rows() == []


def test_add_ban_force_bans_a_name_outside_the_catalog(app, frozen_clock):
    assert bans.add_ban('  Future   Card ', ['2v2'], force=True) == [('2v2', 'added')]
    assert _rows() == [('future card', 'Future   Card', '2v2', date(2030, 1, 1), None)]


def test_add_ban_force_still_uses_the_catalog_spelling(app):
    _catalog(('OGN', '79', JINX))
    bans.add_ban('jinx, loose cannon', ['1v1'], since=SEP1, force=True)
    assert _rows() == [('jinx, loose cannon', JINX, '1v1', SEP1, None)]


def test_add_ban_reason_limits(app):
    _catalog(('OGN', '79', JINX), ('OGN', '1', 'Called Shot'))
    with pytest.raises(ValueError) as caught:
        bans.add_ban(JINX, ['1v1'], reason='x' * 501)
    assert str(caught.value) == 'reason too long'
    assert _rows() == []
    bans.add_ban(JINX, ['1v1'], since=SEP1, reason='x' * 500)
    bans.add_ban('Called Shot', ['1v1'], since=SEP1, reason='')
    bans.add_ban('Called Shot', ['2v2'], since=SEP1, reason=' \t ')
    assert [r[4] for r in _rows()] == ['x' * 500, None, None]


def test_add_ban_reason_too_long_on_an_existing_ban_changes_nothing(app):
    _catalog(('OGN', '79', JINX))
    bans.add_ban(JINX, ['1v1'], since=SEP1, reason='Too strong')
    before = _rows()
    with pytest.raises(ValueError):
        bans.add_ban(JINX, ['1v1'], reason='y' * 501)
    assert _rows() == before


# --- S6 remove_ban -------------------------------------------------------------------

def test_remove_ban_statuses_and_the_other_mode_stays(app):
    _catalog(('OGN', '79', JINX))
    bans.add_ban(JINX, ['1v1', '2v2'], since=SEP1)
    assert bans.remove_ban('JINX, LOOSE CANNON', ['1v1']) == [('1v1', 'removed')]
    assert _rows() == [('jinx, loose cannon', JINX, '2v2', SEP1, None)]
    assert bans.remove_ban(JINX, ['1v1', '2v2']) == [('1v1', 'absent'), ('2v2', 'removed')]
    assert _rows() == []
    assert bans.remove_ban(JINX, ['1v1', '2v2']) == [('1v1', 'absent'), ('2v2', 'absent')]


def test_remove_ban_works_for_a_forced_name(app):
    bans.add_ban('Future Card', ['1v1'], since=SEP1, force=True)
    assert bans.remove_ban('future  card', ['1v1']) == [('1v1', 'removed')]
    assert _rows() == []
