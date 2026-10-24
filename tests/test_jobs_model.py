"""F4-a S1/S7: `rbjobs` constraints, through the `RbJob` model on the test schema
(`db.create_all()` builds it from the model, so the model declares what the
migration creates; `test_jobs_migration.py` checks the two agree)."""
import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import RbJob


def _count():
    return db.session.execute(sa.select(sa.func.count()).select_from(RbJob)).scalar_one()


def _add(**fields):
    job = RbJob(**{'rbjob_kind': 'heartbeat', **fields})
    db.session.add(job)
    db.session.commit()
    return job


def _rejected(**fields):
    before = _count()
    with pytest.raises(IntegrityError):
        _add(**fields)
    db.session.rollback()
    assert _count() == before


def test_defaults_of_a_new_job(app, frozen_clock):
    job = _add()
    db.session.refresh(job)
    assert job.rbjob_id is not None
    assert job.rbjob_params == {}
    assert job.rbjob_status == 'queued'
    assert job.rbjob_requested_at == frozen_clock()
    assert job.rbjob_requested_by is None
    assert (job.rbjob_started_at, job.rbjob_finished_at, job.rbjob_message) == (None, None, None)
    # SQL NULL, not the JSON literal 'null'
    assert db.session.execute(
        sa.text('SELECT rbjob_result IS NULL FROM riftbound.rbjobs')).scalar_one() == 1


def test_ids_autoincrement(app):
    first = _add(rbjob_status='success')
    second = _add()
    assert second.rbjob_id == first.rbjob_id + 1


def test_unknown_kind_is_rejected(app):
    _rejected(rbjob_kind='nope')


def test_unknown_status_is_rejected(app):
    _rejected(rbjob_status='paused')


@pytest.mark.parametrize('active', ['queued', 'running'])
def test_a_second_active_job_of_the_same_kind_is_rejected(app, active):
    _add(rbjob_status=active)
    _rejected(rbjob_status='queued')
    _rejected(rbjob_status='running')


@pytest.mark.parametrize('finished', ['success', 'error'])
def test_a_new_queued_job_is_accepted_once_the_previous_one_finished(app, finished):
    first = _add()
    first.rbjob_status = finished
    db.session.commit()
    _add()
    _add(rbjob_status=finished)
    assert _count() == 3


def test_message_holds_300_characters(app):
    job = _add(rbjob_status='error', rbjob_message='x' * 300)
    db.session.refresh(job)
    assert len(job.rbjob_message) == 300
