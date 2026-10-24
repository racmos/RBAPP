"""F4-a S3/S7: `app.services.jobs` (enqueue, claim, timeout, run)."""
import logging
from datetime import timedelta

import pytest
import sqlalchemy as sa

from app import db
from app.jobs import registry
from app.jobs.registry import JobKind
from app.models import RbJob
from app.services import jobs
from app.utils import clock


def _all():
    db.session.expire_all()
    return db.session.execute(sa.select(RbJob).order_by(RbJob.rbjob_id)).scalars().all()


@pytest.fixture
def extra_kinds(app, monkeypatch):
    """Register test-only kinds. The database CHECK accepts only the real kinds,
    so CHECK enforcement is switched off on the (single) in-memory SQLite
    connection; the partial unique index still applies."""
    monkeypatch.setattr(registry, '_KINDS', dict(registry._KINDS))
    db.session.execute(sa.text('PRAGMA ignore_check_constraints = ON'))
    db.session.commit()

    def _register(name, handler, timeout_seconds=30):
        registry.register(JobKind(name, handler, timeout_seconds))

    yield _register
    db.session.rollback()
    db.session.execute(sa.text('PRAGMA ignore_check_constraints = OFF'))
    db.session.commit()


# --- enqueue ---------------------------------------------------------------------

def test_enqueue_creates_a_queued_job(app, make_user, frozen_clock):
    user = make_user('queuer')
    job = jobs.enqueue('heartbeat', {'a': '1'}, requested_by=user.id)
    [stored] = _all()
    assert stored.rbjob_id == job.rbjob_id
    assert (stored.rbjob_kind, stored.rbjob_status, stored.rbjob_params) == (
        'heartbeat', 'queued', {'a': '1'})
    assert stored.rbjob_requested_by == user.id
    assert stored.rbjob_requested_at == frozen_clock()
    assert stored.rbjob_started_at is None


def test_enqueue_without_params_stores_an_empty_dict(app):
    jobs.enqueue('heartbeat')
    [stored] = _all()
    assert stored.rbjob_params == {}
    assert stored.rbjob_requested_by is None


def test_enqueue_unknown_kind_raises_and_writes_nothing(app):
    with pytest.raises(jobs.UnknownJobKind) as caught:
        jobs.enqueue('nope')
    assert caught.value.kind == 'nope'
    assert _all() == []


@pytest.mark.parametrize('claimed', [False, True])
def test_enqueue_while_a_job_of_the_kind_is_active_raises(app, claimed):
    first = jobs.enqueue('heartbeat')
    if claimed:
        jobs.claim_next()
    with pytest.raises(jobs.JobAlreadyActive) as caught:
        jobs.enqueue('heartbeat', {'b': '2'})
    assert caught.value.job_id == first.rbjob_id
    assert [j.rbjob_id for j in _all()] == [first.rbjob_id]
    # the failed insert was rolled back: the session still works
    expected = None if claimed else first.rbjob_id
    assert getattr(jobs.claim_next(), 'rbjob_id', None) == expected


def test_enqueue_again_once_the_previous_job_finished(app):
    jobs.enqueue('heartbeat')
    jobs.run_pending()
    second = jobs.enqueue('heartbeat')
    assert [(j.rbjob_id, j.rbjob_status) for j in _all()] == [
        (second.rbjob_id - 1, 'success'), (second.rbjob_id, 'queued')]


# --- claim_next --------------------------------------------------------------------

def test_claim_next_with_nothing_queued(app):
    assert jobs.claim_next() is None


def test_claim_next_returns_one_queued_job_exactly_once(app, frozen_clock):
    queued = jobs.enqueue('heartbeat')
    frozen_clock.advance(seconds=5)
    claimed = jobs.claim_next()
    assert claimed.rbjob_id == queued.rbjob_id
    assert claimed.rbjob_status == 'running'
    assert claimed.rbjob_started_at == frozen_clock()
    assert jobs.claim_next() is None
    [stored] = _all()
    assert (stored.rbjob_status, stored.rbjob_started_at) == ('running', frozen_clock())


def test_claim_next_takes_the_oldest_queued_job(app, extra_kinds, frozen_clock):
    extra_kinds('other', lambda params: {})
    older = jobs.enqueue('other')
    frozen_clock.advance(seconds=1)
    newer = jobs.enqueue('heartbeat')
    assert jobs.claim_next().rbjob_id == older.rbjob_id
    assert jobs.claim_next().rbjob_id == newer.rbjob_id
    assert jobs.claim_next() is None


def test_claim_next_skips_a_job_another_runner_claimed_first(app, extra_kinds, frozen_clock,
                                                             monkeypatch):
    extra_kinds('other', lambda params: {})
    contested = jobs.enqueue('other')
    frozen_clock.advance(seconds=1)
    free = jobs.enqueue('heartbeat')
    other_runner_at = frozen_clock() - timedelta(seconds=30)
    original = jobs._queued_ids

    def select_then_lose_the_race():
        ids = original()
        # another runner claims the oldest job between our SELECT and our UPDATE
        with db.engine.begin() as conn:
            conn.execute(sa.text(
                "UPDATE riftbound.rbjobs SET rbjob_status = 'running', rbjob_started_at = :at "
                "WHERE rbjob_id = :id"), {'at': other_runner_at, 'id': contested.rbjob_id})
        return ids

    monkeypatch.setattr(jobs, '_queued_ids', select_then_lose_the_race)
    claimed = jobs.claim_next()
    assert claimed.rbjob_id == free.rbjob_id
    stored = {j.rbjob_id: j for j in _all()}
    assert stored[contested.rbjob_id].rbjob_started_at == other_runner_at
    assert stored[free.rbjob_id].rbjob_started_at == frozen_clock()


# --- expire_stale ------------------------------------------------------------------

def _running(kind='heartbeat'):
    job = jobs.enqueue(kind)
    assert jobs.claim_next().rbjob_id == job.rbjob_id
    return job.rbjob_id


def test_a_job_running_past_its_timeout_becomes_error(app, frozen_clock):
    job_id = _running()
    now = frozen_clock.advance(seconds=61)
    jobs.expire_stale(now)
    [stored] = _all()
    assert stored.rbjob_id == job_id
    assert (stored.rbjob_status, stored.rbjob_message) == ('error', 'Timed out after 60 s')
    assert stored.rbjob_finished_at == now


@pytest.mark.parametrize('seconds', [59, 60])
def test_a_job_within_its_timeout_keeps_running(app, frozen_clock, seconds):
    started = frozen_clock()
    _running()
    jobs.expire_stale(frozen_clock.advance(seconds=seconds))
    [stored] = _all()
    assert (stored.rbjob_status, stored.rbjob_started_at) == ('running', started)
    assert (stored.rbjob_finished_at, stored.rbjob_message) == (None, None)


@pytest.mark.parametrize('seconds, status', [(3599, 'running'), (3601, 'error')])
def test_an_unregistered_kind_times_out_after_an_hour(app, extra_kinds, frozen_clock,
                                                      seconds, status):
    extra_kinds('gone', lambda params: {})
    _running('gone')
    registry._KINDS.pop('gone')          # the kind was removed after the job started
    jobs.expire_stale(frozen_clock.advance(seconds=seconds))
    [stored] = _all()
    assert stored.rbjob_status == status
    if status == 'error':
        assert stored.rbjob_message == 'Timed out after 3600 s'


def test_queued_jobs_never_time_out(app, frozen_clock):
    jobs.enqueue('heartbeat')
    jobs.expire_stale(frozen_clock.advance(days=2))
    [stored] = _all()
    assert stored.rbjob_status == 'queued'


def test_run_pending_expires_stale_jobs_first(app, frozen_clock):
    _running()
    frozen_clock.advance(seconds=61)
    assert jobs.run_pending() == []
    [stored] = _all()
    assert (stored.rbjob_status, stored.rbjob_message) == ('error', 'Timed out after 60 s')


# --- run_pending -------------------------------------------------------------------

def test_run_pending_with_nothing_queued(app):
    assert jobs.run_pending() == []
    assert _all() == []


def test_run_pending_runs_a_job_and_records_success(app, frozen_clock):
    queued = jobs.enqueue('heartbeat')
    now = frozen_clock.advance(minutes=1)
    ran = jobs.run_pending()
    assert [j.rbjob_id for j in ran] == [queued.rbjob_id]
    [stored] = _all()
    assert stored.rbjob_status == 'success'
    assert stored.rbjob_result == {'ok': True, 'at': '2030-01-01T12:01:00+00:00'}
    assert (stored.rbjob_started_at, stored.rbjob_finished_at) == (now, now)
    assert stored.rbjob_message is None


def test_the_handler_receives_the_params(app, extra_kinds):
    extra_kinds('echo', lambda params: {'got': params})
    jobs.enqueue('echo', {'k': 'v'})
    jobs.run_pending()
    [stored] = _all()
    assert stored.rbjob_result == {'got': {'k': 'v'}}


def test_a_failing_handler_is_recorded_and_the_runner_continues(app, extra_kinds,
                                                                frozen_clock, caplog):
    def boom(params):
        raise RuntimeError('a' * 400 + '\nsecond line')

    extra_kinds('boom', boom)
    failing = jobs.enqueue('boom')
    frozen_clock.advance(seconds=1)
    healthy = jobs.enqueue('heartbeat')
    with caplog.at_level(logging.ERROR, logger='app.services.jobs'):
        ran = jobs.run_pending()
    assert [j.rbjob_id for j in ran] == [failing.rbjob_id, healthy.rbjob_id]
    stored = {j.rbjob_id: j for j in _all()}
    message = stored[failing.rbjob_id].rbjob_message
    assert message == 'RuntimeError: ' + 'a' * 286
    assert len(message) == 300
    assert stored[failing.rbjob_id].rbjob_status == 'error'
    assert stored[failing.rbjob_id].rbjob_result is None
    assert stored[failing.rbjob_id].rbjob_finished_at == frozen_clock()
    assert stored[healthy.rbjob_id].rbjob_status == 'success'
    [record] = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert record.exc_info and record.exc_info[0] is RuntimeError


@pytest.mark.parametrize('error, message', [
    (ValueError('first\nsecond'), 'ValueError: first'),
    (KeyError('k'), "KeyError: 'k'"),
    (RuntimeError(), 'RuntimeError'),
])
def test_error_message_is_the_class_and_the_first_line(app, extra_kinds, error, message):
    def fail(params):
        raise error

    extra_kinds('fail', fail)
    jobs.enqueue('fail')
    jobs.run_pending()
    [stored] = _all()
    assert (stored.rbjob_status, stored.rbjob_message) == ('error', message)


def test_a_job_of_an_unregistered_kind_is_an_error(app, extra_kinds, frozen_clock):
    extra_kinds('gone', lambda params: {})
    gone = jobs.enqueue('gone')
    registry._KINDS.pop('gone')
    frozen_clock.advance(seconds=1)
    healthy = jobs.enqueue('heartbeat')
    ran = jobs.run_pending()
    assert [j.rbjob_id for j in ran] == [gone.rbjob_id, healthy.rbjob_id]
    stored = {j.rbjob_id: j for j in _all()}
    assert (stored[gone.rbjob_id].rbjob_status, stored[gone.rbjob_id].rbjob_message) == (
        'error', 'Unknown job kind')
    assert stored[gone.rbjob_id].rbjob_finished_at == frozen_clock()
    assert stored[healthy.rbjob_id].rbjob_status == 'success'


def test_a_result_that_cannot_be_stored_is_an_error(app, extra_kinds, frozen_clock):
    extra_kinds('opaque', lambda params: {'x': object()})
    opaque = jobs.enqueue('opaque')
    frozen_clock.advance(seconds=1)
    healthy = jobs.enqueue('heartbeat')
    jobs.run_pending()
    stored = {j.rbjob_id: j for j in _all()}
    assert stored[opaque.rbjob_id].rbjob_status == 'error'
    assert stored[opaque.rbjob_id].rbjob_message == (
        'StatementError: (builtins.TypeError) Object of type object is not JSON serializable')
    assert stored[opaque.rbjob_id].rbjob_result is None
    assert stored[healthy.rbjob_id].rbjob_status == 'success'
