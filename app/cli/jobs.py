"""`flask jobs ...`: queue, run and list background jobs (F4-a S4).

`enqueue --unless-succeeded-today` is the 08:00 retry of `daily_prices`
(docs/systemd/riftbound-daily-retry.service).
`run-pending` is what the systemd timer starts every minute
(docs/systemd/riftbound-jobs.service). It exits 0 even when a job failed: the
failure is recorded on the job, and the timer must not loop on it.
"""
import click
from flask.cli import AppGroup

from app.jobs import registry
from app.services import jobs

jobs_cli = AppGroup('jobs', help='Queue, run and list background jobs.')


class _UsageFailure(click.ClickException):
    """`Error: <message>` on stderr, exit 2 (bad input), without the usage text."""
    exit_code = 2


def _parse_params(items: tuple[str, ...]) -> dict[str, str]:
    params = {}
    for item in items:
        key, sep, value = item.partition('=')
        if not sep or not key:
            raise _UsageFailure('--param must be key=value.')
        params[key] = value
    return params


def _when(value) -> str:
    return value.strftime('%Y-%m-%d %H:%M:%S') if value else '-'


@jobs_cli.command('enqueue')
@click.argument('kind')
@click.option('--param', 'params', multiple=True, metavar='KEY=VALUE',
              help='Job parameter (repeatable); values are strings.')
@click.option('--unless-succeeded-today', is_flag=True,
              help='Do nothing (exit 0) when a KIND job already succeeded today (UTC).')
def enqueue(kind, params, unless_succeeded_today):
    """Queue a job of KIND."""
    parsed = _parse_params(params)
    if unless_succeeded_today and (done := jobs.last_success_today(kind)) is not None:
        click.echo(f"Skipped: a '{kind}' job already succeeded today (job {done.rbjob_id}).")
        return
    try:
        job = jobs.enqueue(kind, parsed)
    except jobs.UnknownJobKind:
        raise _UsageFailure(
            f"unknown job kind '{kind}'. Known kinds: {', '.join(registry.names())}.")
    except jobs.JobAlreadyActive as exc:
        raise click.ClickException(
            f"a '{kind}' job is already queued or running (job {exc.job_id}).")
    click.echo(f'Queued job {job.rbjob_id} ({kind}).')


@jobs_cli.command('run-pending')
def run_pending():
    """Expire stale jobs, then run every queued job."""
    ran = jobs.run_pending()
    if not ran:
        click.echo('No pending jobs.')
        return
    for job in ran:
        outcome = job.rbjob_status
        if outcome == 'error':
            outcome = f'error: {job.rbjob_message}'
        click.echo(f'Job {job.rbjob_id} ({job.rbjob_kind}): {outcome}')
    click.echo(f'Ran {len(ran)} job(s).')


@jobs_cli.command('list')
@click.option('--limit', default=20, show_default=True, type=click.IntRange(min=1),
              help='How many jobs to show, newest first.')
def list_jobs(limit):
    """List the latest jobs, newest first."""
    latest = jobs.list_jobs(limit)
    if not latest:
        click.echo('No jobs.')
        return
    click.echo('ID  KIND  STATUS  REQUESTED (UTC)  FINISHED (UTC)  MESSAGE')
    for job in latest:
        click.echo(f'{job.rbjob_id}  {job.rbjob_kind}  {job.rbjob_status}  '
                   f'{_when(job.rbjob_requested_at)}  {_when(job.rbjob_finished_at)}  '
                   f'{job.rbjob_message or "-"}')
