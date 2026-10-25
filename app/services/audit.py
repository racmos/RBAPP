"""Audit trail of admin writes (F13-R2).

`record` adds one `RbAdminAudit` row to the CURRENT session without
committing: the admin change and its audit row land in one transaction, so a
rolled-back change leaves no trace and a committed one always has its row.

Actor: `None` (default) is the signed-in `current_user`; `SYSTEM` is a job or
the CLI (no user). Every later admin unit (F13-b on, F14-d, F10) writes
through this function.
"""
import json
import re

from flask_login import current_user

from app import db
from app.models.audit import RbAdminAudit

SYSTEM = object()

ACTION_RE = re.compile(r'^[a-z_]+(\.[a-z_]+)+$')
DETAILS_MAX_BYTES = 4096


def record(action, target_type, target_id=None, details=None, actor=None):
    """Build (and `db.session.add`, never commit) one audit row.

    `action` is dotted lowercase (`set.create`, `riot.apply`); `details` is a
    JSON-serialisable object of at most 4096 bytes once serialised. Raises
    ValueError on bad input and RuntimeError when no actor can be resolved.
    """
    if not isinstance(action, str) or not ACTION_RE.match(action):
        raise ValueError('action must be dotted lowercase, like "set.create"')
    if details is not None:
        try:
            text = json.dumps(details, ensure_ascii=False)
        except (TypeError, ValueError) as error:
            raise ValueError('details must be JSON serialisable') from error
        if len(text.encode('utf-8')) > DETAILS_MAX_BYTES:
            raise ValueError(f'details must be at most {DETAILS_MAX_BYTES} bytes serialised')
    if actor is None:
        if not current_user.is_authenticated:
            raise RuntimeError('record() needs a signed-in user, or an explicit actor')
        actor_id, username = current_user.id, current_user.username
    elif actor is SYSTEM:
        actor_id, username = None, 'system'
    else:
        actor_id, username = actor.id, actor.username
    row = RbAdminAudit(
        rbaud_actor_id=actor_id,
        rbaud_actor_username=username,
        rbaud_action=action,
        rbaud_target_type=target_type,
        rbaud_target_id=target_id,
        rbaud_details=details,
    )
    db.session.add(row)
    return row
