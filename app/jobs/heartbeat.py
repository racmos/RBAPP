"""`heartbeat`: a diagnostic job that only proves the runner works."""
from datetime import timezone

from app.jobs.registry import JobKind, register
from app.utils import clock


def run(params: dict) -> dict:
    return {'ok': True, 'at': clock.utcnow().replace(tzinfo=timezone.utc).isoformat()}


register(JobKind('heartbeat', run, timeout_seconds=60))
