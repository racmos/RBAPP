"""F9-a S14 (AC6): the `sessions_purge` job kind runs the purge through the job runner."""
import pytest
import sqlalchemy as sa

from app import db
from app.jobs import registry
from app.jobs.registry import JobFailed
from app.models import RbJob, RbSession
from app.services import jobs as jobs_service
from tests.test_sessions_cli import names, seeded  # noqa: F401  (fixture)


def test_kind_is_registered_with_a_300_second_timeout():
    kind = registry.get('sessions_purge')
    assert kind is not None and kind.timeout_seconds == 300


def test_params_fail(app):
    with pytest.raises(JobFailed) as caught:
        registry.get('sessions_purge').handler({'dry_run': 'true'})
    assert str(caught.value) == 'sessions_purge takes no params'


def test_the_runner_purges_the_ended_sessions(app, seeded):
    job = jobs_service.enqueue('sessions_purge')
    jobs_service.run_pending()
    db.session.expire_all()
    done = db.session.get(RbJob, job.rbjob_id)
    assert (done.rbjob_status, done.rbjob_result) == ('success', {'purged': 4})
    assert names() == ['active', 'remembered', 'fresh']


def test_a_second_run_purges_nothing(app, seeded):
    for _ in range(2):
        job = jobs_service.enqueue('sessions_purge')
        jobs_service.run_pending()
    db.session.expire_all()
    assert db.session.get(RbJob, job.rbjob_id).rbjob_result == {'purged': 0}
    assert db.session.execute(sa.select(sa.func.count()).select_from(
        RbSession)).scalar_one() == 3


def test_the_cli_queues_it(app):
    runner = app.test_cli_runner(mix_stderr=False)
    result = runner.invoke(args=['jobs', 'enqueue', 'sessions_purge',
                                 '--unless-succeeded-today'])
    assert (result.exit_code, result.stdout, result.stderr) == (
        0, 'Queued job 1 (sessions_purge).\n', '')
