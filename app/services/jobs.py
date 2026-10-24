"""Job queue and runner (F4-a S3). No Flask request objects: called by
`flask jobs ...` (app/cli/jobs.py), timers and, later, admin endpoints.

Overlap safety: the partial unique index `ux_rbjobs_active_kind` allows one
active job per kind, `claim_next` claims with a conditional UPDATE so two
runners never get the same job, and the systemd unit wraps the runner in
`flock -n`. Every timestamp comes from `clock.utcnow()`.
"""
import logging
from datetime import datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from app import db
from app.jobs import registry
from app.models.job import ACTIVE_STATUSES, MESSAGE_MAX_LENGTH, RbJob
from app.utils import clock

logger = logging.getLogger(__name__)

# Timeout of a running job whose kind is no longer registered.
UNKNOWN_KIND_TIMEOUT_SECONDS = 3600


class UnknownJobKind(Exception):
    def __init__(self, kind: str):
        super().__init__(f"Unknown job kind '{kind}'")
        self.kind = kind


class JobAlreadyActive(Exception):
    def __init__(self, job_id: int):
        super().__init__(f'Job {job_id} of the same kind is already queued or running')
        self.job_id = job_id


def enqueue(kind: str, params: dict | None = None, requested_by: int | None = None) -> RbJob:
    """Queue a job. The unique index, not a prior SELECT, detects an active job
    of the same kind, so two concurrent enqueues cannot both succeed."""
    if registry.get(kind) is None:
        raise UnknownJobKind(kind)
    job = RbJob(rbjob_kind=kind, rbjob_params=dict(params or {}),
                rbjob_requested_by=requested_by)
    db.session.add(job)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        active_id = db.session.execute(
            sa.select(RbJob.rbjob_id).where(RbJob.rbjob_kind == kind,
                                            RbJob.rbjob_status.in_(ACTIVE_STATUSES))
        ).scalar()
        if active_id is None:
            raise
        raise JobAlreadyActive(active_id) from None
    return job


def _queued_ids() -> list[int]:
    return db.session.execute(
        sa.select(RbJob.rbjob_id).where(RbJob.rbjob_status == 'queued')
        .order_by(RbJob.rbjob_requested_at, RbJob.rbjob_id)
    ).scalars().all()


def claim_next() -> RbJob | None:
    """Claim the oldest queued job, or None. The UPDATE only matches a job that
    is still queued; 0 rows means another runner won it, so try the next one."""
    for job_id in _queued_ids():
        claimed = db.session.execute(
            sa.update(RbJob)
            .where(RbJob.rbjob_id == job_id, RbJob.rbjob_status == 'queued')
            .values(rbjob_status='running', rbjob_started_at=clock.utcnow())
            .execution_options(synchronize_session=False))
        db.session.commit()
        if claimed.rowcount == 1:
            return db.session.get(RbJob, job_id, populate_existing=True)
    return None


def _timeout(kind: str) -> int:
    known = registry.get(kind)
    return known.timeout_seconds if known else UNKNOWN_KIND_TIMEOUT_SECONDS


def expire_stale(now: datetime) -> list[int]:
    """Mark as `error` every running job past its kind's timeout; returns their ids."""
    expired = []
    running = db.session.execute(
        sa.select(RbJob.rbjob_id, RbJob.rbjob_kind, RbJob.rbjob_started_at)
        .where(RbJob.rbjob_status == 'running')).all()
    for job_id, kind, started_at in running:
        timeout = _timeout(kind)
        if started_at is not None and started_at + timedelta(seconds=timeout) >= now:
            continue
        done = db.session.execute(
            sa.update(RbJob)
            .where(RbJob.rbjob_id == job_id, RbJob.rbjob_status == 'running')
            .values(rbjob_status='error', rbjob_finished_at=now,
                    rbjob_message=f'Timed out after {timeout} s')
            .execution_options(synchronize_session=False))
        if done.rowcount == 1:
            expired.append(job_id)
    db.session.commit()
    return expired


def _error_message(exc: BaseException) -> str:
    """`<ExceptionClass>: <first line of the text>`, cut to the column size."""
    text = str(exc)
    first_line = text.splitlines()[0] if text else ''
    message = f'{type(exc).__name__}: {first_line}' if first_line else type(exc).__name__
    return message[:MESSAGE_MAX_LENGTH]


def _finish(job: RbJob, status: str, result: dict | None = None,
            message: str | None = None) -> None:
    job.rbjob_status = status
    job.rbjob_finished_at = clock.utcnow()
    job.rbjob_result = result
    job.rbjob_message = message
    db.session.commit()


def _fail(job_id: int, kind: str, exc: Exception) -> None:
    db.session.rollback()
    logger.exception('Job %s (%s) failed', job_id, kind)
    _finish(db.session.get(RbJob, job_id), 'error', message=_error_message(exc))


def _run(job: RbJob) -> None:
    job_id, kind_name, params = job.rbjob_id, job.rbjob_kind, dict(job.rbjob_params or {})
    kind = registry.get(kind_name)
    if kind is None:
        _finish(job, 'error', message='Unknown job kind')
        return
    try:
        result = kind.handler(params)
    except Exception as exc:
        _fail(job_id, kind_name, exc)
        return
    try:
        _finish(job, 'success', result=result)
    except Exception as exc:            # e.g. a result that is not JSON
        _fail(job_id, kind_name, exc)


def run_pending() -> list[RbJob]:
    """Expire stale jobs, then claim and run queued jobs one by one until none
    is left. A failing job is recorded and the runner goes on with the next."""
    expire_stale(clock.utcnow())
    ran = []
    while (job := claim_next()) is not None:
        _run(job)
        ran.append(job)
    return ran


def list_jobs(limit: int = 20) -> list[RbJob]:
    """The latest `limit` jobs, newest first."""
    return db.session.execute(
        sa.select(RbJob).order_by(RbJob.rbjob_requested_at.desc(), RbJob.rbjob_id.desc())
        .limit(limit)).scalars().all()
