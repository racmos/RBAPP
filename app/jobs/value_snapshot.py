"""`value_snapshot`: the daily collection value snapshots (F4-c).

Queued by `daily_prices` when it succeeds (and by hand with
`flask jobs enqueue value_snapshot`). It stores one row per user with a collection
for today's UTC date.
"""
from app.jobs.registry import JobFailed, JobKind, register
from app.services import snapshots
from app.utils import clock


def run(params: dict) -> dict:
    if params:
        raise JobFailed('value_snapshot takes no params')
    return snapshots.take_snapshots(clock.utcnow().date())


register(JobKind('value_snapshot', run, timeout_seconds=900))
