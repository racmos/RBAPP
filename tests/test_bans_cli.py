"""F2-a S7: `flask bans list|add|remove`, exact output, exit codes and the rows
they leave."""
from datetime import date, datetime

import pytest
import sqlalchemy as sa

from app import db
from app.models import RbCard, RbCardBan, RbSet

JINX = 'Jinx, Loose Cannon'
UNKNOWN = "Error: No card named '{}' in the catalog (use --force to ban it anyway).\n"


@pytest.fixture
def cli(app):
    runner = app.test_cli_runner(mix_stderr=False)

    def _invoke(*args):
        return runner.invoke(args=list(args))

    return _invoke


@pytest.fixture
def catalog(app):
    db.session.add_all([RbSet(rbset_id='OGN', rbset_name='Origins'),
                        RbSet(rbset_id='OGNX', rbset_name='Origins promos')])
    db.session.add_all([
        RbCard(rbcar_rbset_id='OGN', rbcar_id='79', rbcar_name=JINX),
        RbCard(rbcar_rbset_id='OGNX', rbcar_id='257', rbcar_name=JINX),
        RbCard(rbcar_rbset_id='OGN', rbcar_id='1', rbcar_name='Called Shot'),
    ])
    db.session.commit()


@pytest.fixture
def today(frozen_clock):
    frozen_clock.now = datetime(2026, 10, 21, 9, 30, 0)
    return frozen_clock


def _rows():
    db.session.expire_all()
    return [(b.rbban_name, b.rbban_mode, b.rbban_since, b.rbban_reason)
            for b in db.session.execute(
                sa.select(RbCardBan).order_by(RbCardBan.rbban_id)).scalars()]


def _assert(result, exit_code, stdout='', stderr=''):
    assert (result.exit_code, result.stdout, result.stderr) == (exit_code, stdout, stderr)


# --- group -------------------------------------------------------------------------

def test_bans_group_help(cli):
    result = cli('bans', '--help')
    assert result.exit_code == 0
    assert 'Manage card bans per game mode (1v1, 2v2).' in result.stdout
    for command in ('list', 'add', 'remove'):
        assert command in result.stdout


def test_other_groups_are_still_registered(cli):
    _assert(cli('users', 'list'), 0, 'No users.\n')
    _assert(cli('jobs', 'list'), 0, 'No jobs.\n')


# --- add ---------------------------------------------------------------------------

def test_add_all_modes_then_again_is_idempotent(cli, catalog, today):
    _assert(cli('bans', 'add', 'jinx, loose cannon', '--mode', 'all', '--reason', 'Too strong'), 0,
            f"Banned '{JINX}' in 1v1 since 2026-10-21.\n"
            f"Banned '{JINX}' in 2v2 since 2026-10-21.\n")
    after = [(JINX, '1v1', date(2026, 10, 21), 'Too strong'),
             (JINX, '2v2', date(2026, 10, 21), 'Too strong')]
    assert _rows() == after
    _assert(cli('bans', 'add', 'jinx, loose cannon', '--mode', 'all', '--reason', 'Too strong'), 0,
            f"'{JINX}' is already banned in 1v1.\n"
            f"'{JINX}' is already banned in 2v2.\n")
    assert _rows() == after


def test_add_one_mode_with_since(cli, catalog):
    _assert(cli('bans', 'add', 'CALLED SHOT', '--mode', '2v2', '--since', '2026-09-18'), 0,
            "Banned 'Called Shot' in 2v2 since 2026-09-18.\n")
    assert _rows() == [('Called Shot', '2v2', date(2026, 9, 18), None)]


def test_add_updates_and_adds_in_one_run(cli, catalog, today):
    cli('bans', 'add', JINX, '--mode', '1v1', '--since', '2026-09-01')
    _assert(cli('bans', 'add', JINX, '--mode', 'all', '--reason', 'Too strong'), 0,
            f"Updated the ban of '{JINX}' in 1v1.\n"
            f"Banned '{JINX}' in 2v2 since 2026-10-21.\n")
    assert _rows() == [(JINX, '1v1', date(2026, 9, 1), 'Too strong'),
                       (JINX, '2v2', date(2026, 10, 21), 'Too strong')]


def test_add_unknown_name_fails_and_writes_nothing(cli, catalog):
    cli('bans', 'add', JINX, '--mode', '1v1', '--since', '2026-09-01')
    before = _rows()
    _assert(cli('bans', 'add', 'Jinx', '--mode', 'all'), 1, stderr=UNKNOWN.format('Jinx'))
    assert _rows() == before


def test_add_force_bans_a_name_outside_the_catalog(cli, today):
    _assert(cli('bans', 'add', ' Future Card ', '--mode', '2v2', '--force'), 0,
            "Banned 'Future Card' in 2v2 since 2026-10-21.\n")
    assert _rows() == [('Future Card', '2v2', date(2026, 10, 21), None)]


def test_add_reason_over_500_characters(cli, catalog):
    _assert(cli('bans', 'add', JINX, '--mode', '1v1', '--reason', 'x' * 501), 1,
            stderr='Error: The reason must be at most 500 characters.\n')
    assert _rows() == []
    _assert(cli('bans', 'add', JINX, '--mode', '1v1', '--since', '2026-09-01',
                '--reason', 'x' * 500), 0,
            f"Banned '{JINX}' in 1v1 since 2026-09-01.\n")


@pytest.mark.parametrize('since', ['2026-13-01', '21/10/2026', 'yesterday'])
def test_add_bad_date_is_a_usage_error(cli, catalog, since):
    result = cli('bans', 'add', JINX, '--mode', '1v1', '--since', since)
    assert (result.exit_code, result.stdout) == (2, '')
    assert "Invalid value for '--since'" in result.stderr
    assert _rows() == []


@pytest.mark.parametrize('command', ['add', 'remove'])
def test_mode_is_required_and_checked(cli, catalog, command):
    missing = cli('bans', command, JINX)
    assert (missing.exit_code, missing.stdout) == (2, '')
    assert "Missing option '--mode'" in missing.stderr
    bad = cli('bans', command, JINX, '--mode', '3v3')
    assert (bad.exit_code, bad.stdout) == (2, '')
    assert "Invalid value for '--mode'" in bad.stderr
    assert _rows() == []


# --- remove ------------------------------------------------------------------------

def test_remove(cli, catalog):
    cli('bans', 'add', JINX, '--mode', 'all', '--since', '2026-09-01')
    _assert(cli('bans', 'remove', 'JINX, LOOSE CANNON', '--mode', '1v1'), 0,
            f"Unbanned '{JINX}' in 1v1.\n")
    assert _rows() == [(JINX, '2v2', date(2026, 9, 1), None)]
    _assert(cli('bans', 'remove', 'JINX, LOOSE CANNON', '--mode', 'all'), 0,
            "'JINX, LOOSE CANNON' was not banned in 1v1.\n"
            f"Unbanned '{JINX}' in 2v2.\n")
    assert _rows() == []
    _assert(cli('bans', 'remove', 'Nobody', '--mode', '2v2'), 0,
            "'Nobody' was not banned in 2v2.\n")


def test_remove_a_forced_name(cli):
    cli('bans', 'add', 'Future Card', '--mode', '1v1', '--since', '2026-09-01', '--force')
    _assert(cli('bans', 'remove', 'future card', '--mode', '1v1'), 0,
            "Unbanned 'Future Card' in 1v1.\n")
    assert _rows() == []


# --- list --------------------------------------------------------------------------

def test_list_with_no_bans(cli):
    _assert(cli('bans', 'list'), 0, 'No bans.\n')
    _assert(cli('bans', 'list', '--mode', '2v2'), 0, 'No bans.\n')


def test_list_ordered_with_reasons_and_mode_filter(cli, catalog):
    cli('bans', 'add', JINX, '--mode', '2v2', '--since', '2026-09-01', '--reason', 'Too strong')
    cli('bans', 'add', 'Called Shot', '--mode', 'all', '--since', '2026-09-18')
    _assert(cli('bans', 'list'), 0,
            '1v1  2026-09-18  Called Shot\n'
            '2v2  2026-09-18  Called Shot\n'
            f'2v2  2026-09-01  {JINX}  — Too strong\n')
    _assert(cli('bans', 'list', '--mode', '1v1'), 0, '1v1  2026-09-18  Called Shot\n')
    bad = cli('bans', 'list', '--mode', 'all')
    assert (bad.exit_code, bad.stdout) == (2, '')
    assert "Invalid value for '--mode'" in bad.stderr
