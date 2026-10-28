"""`daily_prices`: the daily Cardmarket load (F4-b, D-F4-1).

Queued at 06:30 Europe/Madrid by riftbound-daily.timer (and again at 08:00
when it did not succeed). It loads the three Cardmarket files with the
default allow-listed URLs, validates what was loaded, links the clear
auto-match cases and lists the doubtful ones for review (D-F4-2, D-F4-10).
Any failure is a `JobFailed`, so the job ends `error` (nothing is linked) and
the retry fires. On success its last step queues `value_snapshot` (F4-c, F4-R4).
"""
import logging

from app.jobs.registry import JobFailed, JobKind, register
from app.services import daily_prices
from app.services.cardmarket_loader import CardmarketLoader


logger = logging.getLogger(__name__)


def _queue_follow_ups() -> list[str]:
    """Queue the jobs that follow a successful load; never raises (a snapshot that
    cannot be queued must not fail the price load)."""
    from app.services import jobs  # imported here: app.services.jobs imports this package
    try:
        jobs.enqueue('value_snapshot')
    except jobs.JobAlreadyActive as exc:
        logger.info('value_snapshot not queued: %s', exc)
        return []
    except Exception:
        logger.exception('value_snapshot could not be queued')
        try:
            from app import db
            db.session.rollback()
        except Exception:
            logger.exception('rollback after a failed enqueue also failed')
        return []
    return ['value_snapshot']


def run(params: dict) -> dict:
    if params:
        raise JobFailed('daily_prices takes no params')

    loaded = CardmarketLoader().run()
    if not loaded['success']:
        errors = loaded.get('errors') or ['Cardmarket load failed']
        raise JobFailed(errors[0])

    try:
        validation = daily_prices.validate_load(loaded['date'])
    except daily_prices.ValidationFailed as exc:
        raise JobFailed(str(exc)) from None
    result = {'validation': validation, **daily_prices.match_clear_cases(loaded['date'])}
    result['queued'] = _queue_follow_ups()
    return result


register(JobKind('daily_prices', run, timeout_seconds=1800))
