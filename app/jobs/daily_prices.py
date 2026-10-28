"""`daily_prices`: the daily Cardmarket load (F4-b, D-F4-1).

Queued at 06:30 Europe/Madrid by riftbound-daily.timer (and again at 08:00
when it did not succeed). It loads the three Cardmarket files with the
default allow-listed URLs, validates what was loaded, links the clear
auto-match cases and lists the doubtful ones for review (D-F4-2, D-F4-10).
Any failure is a `JobFailed`, so the job ends `error` (nothing is linked) and
the retry fires. On success its last step queues `value_snapshot` (F4-c, F4-R4)
and then `products_refresh` (F14-a).
"""
import logging

from app.jobs.registry import JobFailed, JobKind, register
from app.services import daily_prices
from app.services.cardmarket_loader import CardmarketLoader


logger = logging.getLogger(__name__)


# Queued in this order after a successful load (F4-c S4, F14-a S5).
FOLLOW_UPS = ('value_snapshot', 'products_refresh')


def _queue_follow_ups() -> list[str]:
    """Queue the jobs that follow a successful load, each on its own: one that is
    already active or cannot be queued is skipped and the next is still tried. Never
    raises (a follow-up that cannot be queued must not fail the price load)."""
    from app.services import jobs  # imported here: app.services.jobs imports this package
    queued = []
    for kind in FOLLOW_UPS:
        try:
            jobs.enqueue(kind)
        except jobs.JobAlreadyActive as exc:
            logger.info('%s not queued: %s', kind, exc)
            continue
        except Exception:
            logger.exception('%s could not be queued', kind)
            try:
                from app import db
                db.session.rollback()
            except Exception:
                logger.exception('rollback after a failed enqueue also failed')
            continue
        queued.append(kind)
    return queued


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
