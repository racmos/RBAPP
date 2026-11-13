"""`sessions_purge`: delete the ended server-side sessions (F9-a S14).

Queued daily by `riftbound-sessions-purge.timer` (`flask jobs enqueue sessions_purge
--unless-succeeded-today`) and by hand. Same rule as `flask sessions purge`: revoked rows,
remembered ones past `expires_at` and the others idle for 12 hours
(`app/services/sessions.py`); active sessions are never touched.
"""
from app.jobs.registry import JobFailed, JobKind, register
from app.services import sessions

NAME = 'sessions_purge'


def run(params: dict) -> dict:
    if params:
        raise JobFailed(f'{NAME} takes no params')
    return {'purged': sessions.purge()}


register(JobKind(NAME, run, timeout_seconds=300))
