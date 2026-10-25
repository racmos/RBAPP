"""F4-a S4: `flask jobs enqueue|run-pending|list`, exact output and exit codes;
F4-b S6: `enqueue --unless-succeeded-today`."""
from datetime import datetime

import pytest
import sqlalchemy as sa

from app import db
from app.models import RbJob
from app.services import jobs
from tests.test_jobs_service import extra_kinds  # noqa: F401  (fixture)

HEADER = 'ID  KIND  STATUS  REQUESTED (UTC)  FINISHED (UTC)  MESSAGE'


@pytest.fixture
def cli(app):
    runner = app.test_cli_runner(mix_stderr=False)

    def _invoke(*args):
        return runner.invoke(args=list(args))

    return _invoke


def _rows():
    db.session.expire_all()
    return [(j.rbjob_id, j.rbjob_kind, j.rbjob_status, j.rbjob_params)
            for j in db.session.execute(sa.select(RbJob).order_by(RbJob.rbjob_id)).scalars()]


def _assert(result, exit_code, stdout='', stderr=''):
    assert (result.exit_code, result.stdout, result.stderr) == (exit_code, stdout, stderr)


def test_jobs_group_help_lists_the_commands(cli):
    result = cli('jobs', '--help')
    assert result.exit_code == 0
    for command in ('enqueue', 'run-pending', 'list'):
        assert command in result.stdout


def test_users_group_is_still_registered(cli):
    _assert(cli('users', 'list'), 0, 'No users.\n')


# --- enqueue -----------------------------------------------------------------------

def test_enqueue(cli, frozen_clock):
    _assert(cli('jobs', 'enqueue', 'heartbeat'), 0, 'Queued job 1 (heartbeat).\n')
    assert _rows() == [(1, 'heartbeat', 'queued', {})]
    job = db.session.get(RbJob, 1)
    assert (job.rbjob_requested_by, job.rbjob_requested_at) == (None, frozen_clock())


def test_enqueue_params_are_strings(cli):
    result = cli('jobs', 'enqueue', 'heartbeat', '--param', 'n=5', '--param', 'expr=a=b',
                 '--param', 'empty=')
    _assert(result, 0, 'Queued job 1 (heartbeat).\n')
    assert _rows() == [(1, 'heartbeat', 'queued', {'n': '5', 'expr': 'a=b', 'empty': ''})]


def test_enqueue_unknown_kind(cli):
    _assert(cli('jobs', 'enqueue', 'nope'), 2,
            stderr="Error: unknown job kind 'nope'. Known kinds: daily_prices, heartbeat, riot_sync.\n")
    assert _rows() == []


def test_enqueue_lists_every_known_kind(cli, extra_kinds):
    extra_kinds('alpha', lambda params: {})
    _assert(cli('jobs', 'enqueue', 'nope'), 2,
            stderr="Error: unknown job kind 'nope'. Known kinds: alpha, daily_prices, heartbeat, riot_sync.\n")
    assert _rows() == []


@pytest.mark.parametrize('claimed', [False, True])
def test_enqueue_while_active(cli, claimed):
    cli('jobs', 'enqueue', 'heartbeat')
    if claimed:
        jobs.claim_next()
    before = _rows()
    _assert(cli('jobs', 'enqueue', 'heartbeat', '--param', 'a=1'), 1,
            stderr="Error: a 'heartbeat' job is already queued or running (job 1).\n")
    assert _rows() == before


@pytest.mark.parametrize('param', ['novalue', '=value'])
def test_enqueue_param_without_key_and_equals(cli, param):
    _assert(cli('jobs', 'enqueue', 'heartbeat', '--param', 'a=1', '--param', param), 2,
            stderr='Error: --param must be key=value.\n')
    assert _rows() == []


# --- enqueue --unless-succeeded-today (F4-b S6) -------------------------------------

UNLESS = '--unless-succeeded-today'


def _finished(kind, status, finished_at):
    db.session.add(RbJob(rbjob_kind=kind, rbjob_status=status, rbjob_finished_at=finished_at))
    db.session.commit()


def test_enqueue_help_documents_the_option(cli):
    result = cli('jobs', 'enqueue', '--help')
    assert result.exit_code == 0
    text = ' '.join(result.stdout.split())        # help text wraps at the terminal width
    assert UNLESS in text
    assert 'when a KIND job already succeeded today (UTC)' in text


@pytest.mark.parametrize('finished_at', [datetime(2030, 1, 1, 0, 0, 0),
                                         datetime(2030, 1, 1, 11, 59, 59)])
def test_unless_succeeded_today_skips_after_a_success_today(cli, frozen_clock, finished_at):
    _finished('heartbeat', 'success', finished_at)
    before = _rows()
    _assert(cli('jobs', 'enqueue', 'heartbeat', UNLESS), 0,
            "Skipped: a 'heartbeat' job already succeeded today (job 1).\n")
    assert _rows() == before


def test_unless_succeeded_today_names_the_latest_success(cli, frozen_clock):
    _finished('heartbeat', 'success', datetime(2030, 1, 1, 11, 0, 0))
    _finished('heartbeat', 'success', datetime(2030, 1, 1, 6, 0, 0))
    _assert(cli('jobs', 'enqueue', 'heartbeat', UNLESS), 0,
            "Skipped: a 'heartbeat' job already succeeded today (job 1).\n")


def test_unless_succeeded_today_skips_even_while_a_job_is_queued(cli, frozen_clock):
    _finished('heartbeat', 'success', datetime(2030, 1, 1, 6, 0, 0))
    cli('jobs', 'enqueue', 'heartbeat')
    before = _rows()
    _assert(cli('jobs', 'enqueue', 'heartbeat', UNLESS), 0,
            "Skipped: a 'heartbeat' job already succeeded today (job 1).\n")
    assert _rows() == before


@pytest.mark.parametrize('kind, status, finished_at', [
    ('heartbeat', 'success', datetime(2029, 12, 31, 23, 59, 59)),    # yesterday (UTC)
    ('heartbeat', 'error', datetime(2030, 1, 1, 6, 0, 0)),           # failed today
    ('daily_prices', 'success', datetime(2030, 1, 1, 6, 0, 0)),      # another kind
])
def test_unless_succeeded_today_enqueues_otherwise(cli, frozen_clock, kind, status,
                                                   finished_at):
    _finished(kind, status, finished_at)
    _assert(cli('jobs', 'enqueue', 'heartbeat', UNLESS, '--param', 'a=1'), 0,
            'Queued job 2 (heartbeat).\n')
    assert _rows()[-1] == (2, 'heartbeat', 'queued', {'a': '1'})


def test_unless_succeeded_today_with_nothing_before(cli, frozen_clock):
    _assert(cli('jobs', 'enqueue', 'daily_prices', UNLESS), 0,
            'Queued job 1 (daily_prices).\n')
    assert _rows() == [(1, 'daily_prices', 'queued', {})]


def test_unless_succeeded_today_while_active_is_the_enqueue_error(cli, frozen_clock):
    _finished('heartbeat', 'error', datetime(2030, 1, 1, 6, 0, 0))
    cli('jobs', 'enqueue', 'heartbeat')
    before = _rows()
    _assert(cli('jobs', 'enqueue', 'heartbeat', UNLESS), 1,
            stderr="Error: a 'heartbeat' job is already queued or running (job 2).\n")
    assert _rows() == before


def test_unless_succeeded_today_unknown_kind_and_bad_param(cli, frozen_clock):
    _assert(cli('jobs', 'enqueue', 'nope', UNLESS), 2,
            stderr="Error: unknown job kind 'nope'. Known kinds: daily_prices, heartbeat, riot_sync.\n")
    _assert(cli('jobs', 'enqueue', 'heartbeat', UNLESS, '--param', 'novalue'), 2,
            stderr='Error: --param must be key=value.\n')
    assert _rows() == []


def test_plain_enqueue_ignores_a_success_today(cli, frozen_clock):
    """Without the option, enqueue is unchanged (F4-a S4)."""
    _finished('heartbeat', 'success', datetime(2030, 1, 1, 6, 0, 0))
    _assert(cli('jobs', 'enqueue', 'heartbeat'), 0, 'Queued job 2 (heartbeat).\n')
    assert _rows() == [(1, 'heartbeat', 'success', {}), (2, 'heartbeat', 'queued', {})]


# --- run-pending -------------------------------------------------------------------

def test_run_pending_with_nothing_queued(cli):
    _assert(cli('jobs', 'run-pending'), 0, 'No pending jobs.\n')


def test_run_pending_runs_and_reports(cli):
    cli('jobs', 'enqueue', 'heartbeat')
    _assert(cli('jobs', 'run-pending'), 0, 'Job 1 (heartbeat): success\nRan 1 job(s).\n')
    assert _rows() == [(1, 'heartbeat', 'success', {})]
    _assert(cli('jobs', 'run-pending'), 0, 'No pending jobs.\n')


def test_run_pending_reports_a_failure_and_exits_0(cli, extra_kinds, frozen_clock):
    def boom(params):
        raise RuntimeError('kaput\nmore detail')

    extra_kinds('boom', boom)
    cli('jobs', 'enqueue', 'boom')
    frozen_clock.advance(seconds=1)
    cli('jobs', 'enqueue', 'heartbeat')
    _assert(cli('jobs', 'run-pending'), 0,
            'Job 1 (boom): error: RuntimeError: kaput\n'
            'Job 2 (heartbeat): success\n'
            'Ran 2 job(s).\n')
    assert [r[2] for r in _rows()] == ['error', 'success']


def test_run_pending_only_expiring_a_stale_job(cli, frozen_clock):
    cli('jobs', 'enqueue', 'heartbeat')
    jobs.claim_next()
    frozen_clock.advance(seconds=61)
    _assert(cli('jobs', 'run-pending'), 0, 'No pending jobs.\n')
    assert db.session.get(RbJob, 1).rbjob_message == 'Timed out after 60 s'


# --- list --------------------------------------------------------------------------

def test_list_with_no_jobs(cli):
    _assert(cli('jobs', 'list'), 0, 'No jobs.\n')


def test_list_newest_first_with_dashes_for_empty_cells(cli, extra_kinds, frozen_clock):
    extra_kinds('boom', lambda params: 1 / 0)
    cli('jobs', 'enqueue', 'boom')
    frozen_clock.advance(minutes=1)
    cli('jobs', 'run-pending')
    frozen_clock.advance(seconds=30)
    cli('jobs', 'enqueue', 'heartbeat')
    _assert(cli('jobs', 'list'), 0,
            f'{HEADER}\n'
            '2  heartbeat  queued  2030-01-01 12:01:30  -  -\n'
            '1  boom  error  2030-01-01 12:00:00  2030-01-01 12:01:00  '
            'ZeroDivisionError: division by zero\n')


def _finished_jobs(count, frozen_clock):
    for _ in range(count):
        db.session.add(RbJob(rbjob_kind='heartbeat', rbjob_status='success',
                             rbjob_finished_at=frozen_clock()))
        db.session.commit()
        frozen_clock.advance(seconds=1)


def test_list_default_limit_is_20(cli, frozen_clock):
    _finished_jobs(21, frozen_clock)
    lines = cli('jobs', 'list').stdout.splitlines()
    assert lines[0] == HEADER
    assert [int(line.split('  ')[0]) for line in lines[1:]] == list(range(21, 1, -1))


def test_list_limit(cli, frozen_clock):
    _finished_jobs(3, frozen_clock)
    _assert(cli('jobs', 'list', '--limit', '1'), 0,
            f'{HEADER}\n3  heartbeat  success  2030-01-01 12:00:02  2030-01-01 12:00:02  -\n')


@pytest.mark.parametrize('limit', ['0', '-1', 'x'])
def test_list_limit_below_1_is_a_usage_error(cli, frozen_clock, limit):
    _finished_jobs(1, frozen_clock)
    result = cli('jobs', 'list', '--limit', limit)
    assert result.exit_code == 2
    assert result.stdout == ''
    assert "Invalid value for '--limit'" in result.stderr
    assert len(_rows()) == 1
