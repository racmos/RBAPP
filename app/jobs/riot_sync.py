"""`riot_sync`: keep the catalog in line with the Riot gallery (F13-c, D-F13-5).

Manual runs queue `trigger=manual` (the legacy Jinja button, F13-e later);
the F13-d timers queue `trigger=schedule` with `--param slot=am|pm` (the slot
is accepted and ignored here). Any failure is a `JobFailed`, so the job ends
`error` and nothing half-written stays (one transaction per set).
"""
from app.jobs.registry import JobFailed, JobKind, register
from app.services import riot_sync
from app.utils import clock

VALID_TRIGGERS = ('schedule', 'manual')
VALID_SLOTS = ('am', 'pm')
KNOWN_PARAMS = {'trigger', 'sets', 'slot'}


def run(params: dict) -> dict:
    unknown = set(params) - KNOWN_PARAMS
    trigger = params.get('trigger', 'manual')
    slot = params.get('slot')
    sets = params.get('sets')
    if unknown or trigger not in VALID_TRIGGERS or (slot is not None and slot not in VALID_SLOTS):
        raise JobFailed('riot_sync: invalid params')
    set_codes = None
    if sets is not None:
        set_codes = [code for code in (part.strip() for part in sets.split(',')) if code]
        if not set_codes:
            raise JobFailed('riot_sync: invalid params')
    return riot_sync.sync(set_codes, trigger, clock.utcnow(), job_id=_running_job_id())


def _running_job_id() -> int | None:
    """Id of the `riot_sync` job currently running, if it can be found."""
    from app import db
    from app.models.job import ACTIVE_STATUSES, RbJob
    return db.session.scalar(
        db.session.query(RbJob.rbjob_id)
        .filter_by(rbjob_kind='riot_sync', rbjob_status='running')
        .order_by(RbJob.rbjob_started_at.desc()))


register(JobKind('riot_sync', run, timeout_seconds=1800))
