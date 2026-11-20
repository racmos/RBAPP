"""Bans effective date (owner request 2026-11-19): a ban is IN EFFECT when
`since <= today`, today being the UTC date of `app.utils.clock.utcnow()`.

Bans dated in the future are UPCOMING: shown (GET /bans, card detail `ban_info`, `flask bans
list`) but never applied (deck legality, the `banned_in` filter of GET /cards, the `bans`
flags of every card summary)."""
from datetime import date, datetime

import pytest
import sqlalchemy as sa

from app import db
from app.models import RbCard, RbCardBan, RbSet
from app.services import bans
from tests.deck_api_helpers import AZIR, BASE, data, make_deck, seed_catalog

JINX = 'Jinx, Loose Cannon'
CARDS_URL = '/riftbound/api/v1/cards'
BANS_URL = '/riftbound/api/v1/bans'
RADIANCE = date(2026, 11, 23)
INVALID_STATUS = {
    'success': False, 'error': 'Validation Error', 'message': 'Invalid query parameters',
    'code': 'validation_error',
    'details': [{'field': 'status', 'message': 'status must be active, upcoming or all',
                 'type': 'literal_error', 'code': 'invalid_value'}],
}


@pytest.fixture
def at(frozen_clock):
    """Move the frozen clock to a UTC moment: `at(2026, 11, 22, 23, 59, 59)`."""
    def move(*parts):
        frozen_clock.now = datetime(*parts)
        return frozen_clock
    move(2026, 11, 19, 12, 0, 0)
    return move


def _catalog():
    db.session.add_all([RbSet(rbset_id='OGN', rbset_name='Origins'),
                        RbSet(rbset_id='OGNX', rbset_name='Origins promos')])
    db.session.add_all([
        RbCard(rbcar_rbset_id='OGN', rbcar_id='79', rbcar_name=JINX, rbcar_type='Unit'),
        RbCard(rbcar_rbset_id='OGNX', rbcar_id='257', rbcar_name=JINX, rbcar_type='Unit'),
        RbCard(rbcar_rbset_id='OGN', rbcar_id='1', rbcar_name='Called Shot', rbcar_type='Spell'),
    ])
    db.session.commit()


def _ban(name, mode, since, reason=None):
    db.session.add(RbCardBan(rbban_name_key=bans.name_key(name), rbban_name=name,
                             rbban_mode=mode, rbban_since=since, rbban_reason=reason))
    db.session.commit()


def _rows():
    db.session.expire_all()
    return [(b.rbban_name, b.rbban_mode, b.rbban_since, b.rbban_reason)
            for b in db.session.execute(
                sa.select(RbCardBan).order_by(RbCardBan.rbban_id)).scalars()]


# --- service: in effect vs upcoming --------------------------------------------------

def test_today_is_the_utc_date_of_the_clock(app, at):
    at(2026, 11, 22, 23, 59, 59)
    assert bans.today() == date(2026, 11, 22)
    at(2026, 11, 23, 0, 0, 0)
    assert bans.today() == RADIANCE


@pytest.mark.parametrize('moment, active', [
    ((2026, 11, 19, 12, 0, 0), False),
    ((2026, 11, 22, 23, 59, 59), False),    # the day before, last second (UTC)
    ((2026, 11, 23, 0, 0, 0), True),        # the day itself, first second (UTC)
    ((2026, 12, 1, 9, 0, 0), True),
])
def test_a_ban_is_in_effect_from_its_date(app, at, moment, active):
    _ban(JINX, '1v1', RADIANCE)
    at(*moment)
    entry = bans.BanEntry(JINX, '1v1', RADIANCE, None)
    assert bans.in_effect(entry) is active
    assert bans.in_effect(entry, on=RADIANCE) is True
    assert bans.in_effect(entry, on=date(2026, 11, 22)) is False
    assert bans.ban_map() == ({'jinx, loose cannon': {'1v1': entry}} if active else {})
    assert bans.ban_map(include_upcoming=True) == {'jinx, loose cannon': {'1v1': entry}}
    assert bans.card_bans(JINX) == {'1v1': active, '2v2': False}
    assert bans.ban_info(JINX) == [
        {'mode': '1v1', 'since': '2026-11-23', 'reason': None, 'active': active}]


def test_card_bans_stays_active_only_even_with_a_map_holding_upcoming_bans(app, at):
    _ban(JINX, '1v1', RADIANCE)
    _ban(JINX, '2v2', date(2026, 9, 18))
    everything = bans.ban_map(include_upcoming=True)
    assert bans.card_bans(JINX, everything) == {'1v1': False, '2v2': True}
    assert bans.ban_info(JINX, everything) == [
        {'mode': '1v1', 'since': '2026-11-23', 'reason': None, 'active': False},
        {'mode': '2v2', 'since': '2026-09-18', 'reason': None, 'active': True}]


def test_the_existing_bans_dated_in_the_past_behave_as_before(app, at):
    """Regression: every ban stored before this change is dated 2026-09-18 or 2026-10-24."""
    _ban(JINX, '1v1', date(2026, 9, 18), 'Wave 1')
    _ban(JINX, '2v2', date(2026, 10, 24))
    _ban('Called Shot', '2v2', date(2026, 10, 24))
    everything = bans.ban_map(include_upcoming=True)
    assert bans.ban_map() == everything
    assert set(everything) == {'jinx, loose cannon', 'called shot'}
    assert bans.card_bans(JINX) == {'1v1': True, '2v2': True}
    assert bans.card_bans('Called Shot') == {'1v1': False, '2v2': True}
    assert [entry['active'] for entry in bans.ban_info(JINX)] == [True, True]
    assert [(b.mode, b.name) for b in bans.list_bans()] == [
        ('1v1', JINX), ('2v2', 'Called Shot'), ('2v2', JINX)]
    assert bans.list_bans(status='upcoming') == []


def test_a_ban_dated_today_is_in_effect(app, at):
    _ban(JINX, '1v1', date(2026, 11, 19))
    assert bans.card_bans(JINX) == {'1v1': True, '2v2': False}


def test_list_bans_status_filter(app, at):
    _ban(JINX, '1v1', RADIANCE)
    _ban(JINX, '2v2', date(2026, 9, 18))
    _ban('Called Shot', '1v1', date(2026, 10, 24))
    assert [(b.mode, b.name) for b in bans.list_bans()] == [
        ('1v1', 'Called Shot'), ('1v1', JINX), ('2v2', JINX)]
    assert [(b.mode, b.name) for b in bans.list_bans(status='all')] == [
        ('1v1', 'Called Shot'), ('1v1', JINX), ('2v2', JINX)]
    assert [(b.mode, b.name) for b in bans.list_bans(status='active')] == [
        ('1v1', 'Called Shot'), ('2v2', JINX)]
    assert [(b.mode, b.name) for b in bans.list_bans(status='upcoming')] == [('1v1', JINX)]
    assert [(b.mode, b.name) for b in bans.list_bans('1v1', status='active')] == [
        ('1v1', 'Called Shot')]
    with pytest.raises(ValueError):
        bans.list_bans(status='soon')


# --- GET /bans -----------------------------------------------------------------------

@pytest.fixture
def seeded_bans(app, at):
    _catalog()
    _ban(JINX, '1v1', RADIANCE, 'Radiance update')
    _ban('Called Shot', '2v2', date(2026, 10, 24))


UPCOMING_JINX = {'name': JINX, 'mode': '1v1', 'since': '2026-11-23', 'reason': 'Radiance update',
                 'active': False, 'printings': [{'set_id': 'OGN', 'card_id': '79'},
                                                {'set_id': 'OGNX', 'card_id': '257'}]}
ACTIVE_SHOT = {'name': 'Called Shot', 'mode': '2v2', 'since': '2026-10-24', 'reason': None,
               'active': True, 'printings': [{'set_id': 'OGN', 'card_id': '1'}]}


@pytest.mark.parametrize('query, items', [
    ({}, [UPCOMING_JINX, ACTIVE_SHOT]),
    ({'status': 'all'}, [UPCOMING_JINX, ACTIVE_SHOT]),
    ({'status': ''}, [UPCOMING_JINX, ACTIVE_SHOT]),
    ({'status': 'active'}, [ACTIVE_SHOT]),
    ({'status': 'upcoming'}, [UPCOMING_JINX]),
    ({'status': 'upcoming', 'mode': '2v2'}, []),
    ({'status': 'active', 'mode': '2v2'}, [ACTIVE_SHOT]),
])
def test_get_bans_carries_active_and_filters_by_status(authenticated_client, seeded_bans,
                                                       query, items):
    resp = authenticated_client.get(BANS_URL, query_string=query)
    assert (resp.status_code, resp.get_json()) == (200, {'success': True,
                                                         'data': {'items': items}})


def test_get_bans_after_the_date_marks_the_ban_active(authenticated_client, seeded_bans, at):
    at(2026, 11, 23, 0, 0, 0)
    items = authenticated_client.get(BANS_URL).get_json()['data']['items']
    assert [(i['name'], i['active']) for i in items] == [(JINX, True), ('Called Shot', True)]


@pytest.mark.parametrize('status', ['soon', 'ALL', ' active', 'true'])
def test_get_bans_bad_status_is_a_400(authenticated_client, seeded_bans, status):
    resp = authenticated_client.get(BANS_URL, query_string={'status': status})
    assert (resp.status_code, resp.get_json()) == (400, INVALID_STATUS)


# --- consumers: GET /cards (bans flags, banned_in) and the card detail ----------------

def test_cards_list_flags_and_banned_in_use_bans_in_effect_only(authenticated_client,
                                                                 seeded_bans, at):
    def page(**query):
        items = authenticated_client.get(CARDS_URL, query_string=query).get_json()['data']['items']
        return {item['key']: item['bans'] for item in items}

    assert page() == {'OGN-1': {'1v1': False, '2v2': True},
                      'OGN-79': {'1v1': False, '2v2': False},
                      'OGNX-257': {'1v1': False, '2v2': False}}
    assert page(banned_in='1v1') == {}
    assert list(page(banned_in='any')) == ['OGN-1']
    at(2026, 11, 23, 0, 0, 0)
    assert page()['OGN-79'] == {'1v1': True, '2v2': False}
    assert list(page(banned_in='1v1')) == ['OGN-79', 'OGNX-257']
    assert list(page(banned_in='any')) == ['OGN-1', 'OGN-79', 'OGNX-257']


def test_card_detail_shows_the_upcoming_ban_but_the_flags_stay_active_only(
        authenticated_client, seeded_bans, at):
    detail = authenticated_client.get(f'{CARDS_URL}/OGN/79').get_json()['data']
    assert detail['bans'] == {'1v1': False, '2v2': False}
    assert detail['ban_info'] == [{'mode': '1v1', 'since': '2026-11-23',
                                   'reason': 'Radiance update', 'active': False}]
    assert all(p.get('bans', {}).get('1v1') in (None, False) for p in detail['printings'])
    at(2026, 11, 23, 0, 0, 0)
    detail = authenticated_client.get(f'{CARDS_URL}/OGN/79').get_json()['data']
    assert detail['bans'] == {'1v1': True, '2v2': False}
    assert detail['ban_info'] == [{'mode': '1v1', 'since': '2026-11-23',
                                   'reason': 'Radiance update', 'active': True}]


# --- consumers: deck legality (list, detail, public deck) -----------------------------

@pytest.fixture
def deck_api(app, authenticated_client, at):
    seed_catalog()
    _ban('Azir, Emperor', '1v1', RADIANCE)
    return authenticated_client


def test_deck_legality_ignores_an_upcoming_ban_until_its_date(deck_api, at):
    deck_id = make_deck('Azir', AZIR)
    share = data(deck_api.post(f'{BASE}/{deck_id}/share'))

    def codes():
        listed = data(deck_api.get(BASE))['items'][0]['issues']['1v1']
        detail = data(deck_api.get(f'{BASE}/{deck_id}'))['legality']['1v1']['issues']
        public = data(deck_api.get(f"/riftbound/api/v1/public/decks/{share['slug']}"))
        return listed, [i['code'] for i in detail], [
            i['code'] for i in public['legality']['1v1']['issues']]

    assert codes() == (['main_size', 'battlefields_count', 'sideboard_size'],) * 3
    at(2026, 11, 23, 0, 0, 0)
    assert codes() == (['main_size', 'battlefields_count', 'sideboard_size', 'banned'],) * 3


# --- CLI -----------------------------------------------------------------------------

@pytest.fixture
def cli(app):
    runner = app.test_cli_runner(mix_stderr=False)
    return lambda *args: runner.invoke(args=list(args))


def _assert(result, exit_code, stdout='', stderr=''):
    assert (result.exit_code, result.stdout, result.stderr) == (exit_code, stdout, stderr)


def test_cli_add_with_a_future_since_says_it_is_not_yet_in_effect(cli, app, at):
    _catalog()
    _assert(cli('bans', 'add', JINX, '--mode', '1v1', '--since', '2026-11-23',
                '--reason', 'Radiance update'), 0,
            f"Banned '{JINX}' in 1v1 from 2026-11-23, not yet in effect.\n")
    assert _rows() == [(JINX, '1v1', RADIANCE, 'Radiance update')]
    _assert(cli('bans', 'add', JINX, '--mode', '1v1', '--since', '2026-11-23'), 0,
            f"'{JINX}' is already banned in 1v1 from 2026-11-23, not yet in effect.\n")
    _assert(cli('bans', 'add', JINX, '--mode', '1v1', '--since', '2026-11-24'), 0,
            f"Updated the ban of '{JINX}' in 1v1: from 2026-11-24, not yet in effect.\n")
    assert _rows() == [(JINX, '1v1', date(2026, 11, 24), 'Radiance update')]


def test_cli_add_dated_today_or_earlier_prints_as_before(cli, app, at):
    _catalog()
    _assert(cli('bans', 'add', JINX, '--mode', '1v1', '--since', '2026-11-19'), 0,
            f"Banned '{JINX}' in 1v1 since 2026-11-19.\n")
    _assert(cli('bans', 'add', JINX, '--mode', '1v1'), 0,
            f"'{JINX}' is already banned in 1v1.\n")
    _assert(cli('bans', 'add', JINX, '--mode', '1v1', '--since', '2026-09-18'), 0,
            f"Updated the ban of '{JINX}' in 1v1.\n")


def test_cli_add_moving_a_future_ban_to_the_past_prints_the_plain_update(cli, app, at):
    _catalog()
    cli('bans', 'add', JINX, '--mode', '1v1', '--since', '2026-11-23')
    _assert(cli('bans', 'add', JINX, '--mode', '1v1', '--since', '2026-11-19'), 0,
            f"Updated the ban of '{JINX}' in 1v1.\n")


@pytest.mark.parametrize('since', ['2026-11-31', '23/11/2026', '2026-11-23T00:00:00'])
def test_cli_add_still_validates_the_date(cli, app, at, since):
    _catalog()
    result = cli('bans', 'add', JINX, '--mode', '1v1', '--since', since)
    assert (result.exit_code, result.stdout) == (2, '')
    assert "Invalid value for '--since'" in result.stderr
    assert _rows() == []


def test_cli_list_marks_upcoming_rows(cli, app, at):
    _catalog()
    cli('bans', 'add', JINX, '--mode', '1v1', '--since', '2026-11-23', '--reason', 'Radiance')
    cli('bans', 'add', 'Called Shot', '--mode', 'all', '--since', '2026-10-24')
    _assert(cli('bans', 'list'), 0,
            '1v1  2026-10-24  Called Shot\n'
            f'1v1  2026-11-23  {JINX}  — Radiance  (from 2026-11-23, not yet in effect)\n'
            '2v2  2026-10-24  Called Shot\n')
    at(2026, 11, 23, 0, 0, 0)
    _assert(cli('bans', 'list', '--mode', '1v1'), 0,
            '1v1  2026-10-24  Called Shot\n'
            f'1v1  2026-11-23  {JINX}  — Radiance\n')


def test_cli_remove_an_upcoming_ban(cli, app, at):
    _catalog()
    cli('bans', 'add', JINX, '--mode', '1v1', '--since', '2026-11-23')
    _assert(cli('bans', 'remove', JINX, '--mode', 'all'), 0,
            f"Unbanned '{JINX}' in 1v1.\n"
            f"'{JINX}' was not banned in 2v2.\n")
    assert _rows() == []
