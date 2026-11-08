"""The admin audit log (CM-e), read-only: the `rbadminaudit` rows every admin write
records (`app/services/audit.py`). No Flask request objects.

`details` are passed through as stored: `audit.record` writes small summaries of the
change (names, ids, old/new values, counts) and no admin action stores a password, a hash
or a token, so nothing is filtered here.
"""
from datetime import timedelta

import sqlalchemy as sa

from app import db
from app.models.audit import RbAdminAudit

SYSTEM_USERNAME = 'system'


def _filters(params) -> list:
    where = []
    if params.actor:
        where.append(RbAdminAudit.rbaud_actor_username.icontains(params.actor, autoescape=True))
    if params.action:
        where.append(RbAdminAudit.rbaud_action == params.action)
    if params.target_type:
        where.append(RbAdminAudit.rbaud_target_type == params.target_type)
    if params.target_id:
        where.append(RbAdminAudit.rbaud_target_id == params.target_id)
    start, end = getattr(params, 'from'), params.to
    if start is not None:
        where.append(RbAdminAudit.rbaud_created_at >= start)
    if end is not None:
        where.append(RbAdminAudit.rbaud_created_at < end + timedelta(days=1))
    return where


def _actor(row) -> dict | None:
    """None for a job or the CLI; a deleted user keeps the stored username (id null)."""
    if row.rbaud_actor_id is None and row.rbaud_actor_username == SYSTEM_USERNAME:
        return None
    return {'id': row.rbaud_actor_id, 'username': row.rbaud_actor_username}


def audit_item(row) -> dict:
    return {
        'id': row.rbaud_id,
        'created_at': row.rbaud_created_at.isoformat() if row.rbaud_created_at else None,
        'actor': _actor(row),
        'action': row.rbaud_action,
        'target_type': row.rbaud_target_type,
        'target_id': row.rbaud_target_id,
        'detail': row.rbaud_details,
    }


def list_audit(params) -> tuple[list[dict], int]:
    """One page of the filtered rows, newest first (id breaks ties), and their total. Two
    statements whatever the page: the dates use `idx_rbadminaudit_created`, a target type
    with an id `idx_rbadminaudit_target`; actor and action filters scan the dated range."""
    where = _filters(params)
    total = db.session.execute(
        sa.select(sa.func.count()).select_from(RbAdminAudit).where(*where)).scalar_one()
    rows = db.session.execute(
        sa.select(RbAdminAudit).where(*where)
        .order_by(RbAdminAudit.rbaud_created_at.desc(), RbAdminAudit.rbaud_id.desc())
        .offset((params.page - 1) * params.per_page).limit(params.per_page)).scalars()
    return [audit_item(row) for row in rows], total


def facets() -> dict:
    """The actions and target types present, with their counts, by name: two statements
    (GROUP BY over the table; both lists are as long as the distinct values, a few dozen)."""
    actions = db.session.execute(
        sa.select(RbAdminAudit.rbaud_action, sa.func.count())
        .group_by(RbAdminAudit.rbaud_action).order_by(RbAdminAudit.rbaud_action)).all()
    types = db.session.execute(
        sa.select(RbAdminAudit.rbaud_target_type, sa.func.count())
        .group_by(RbAdminAudit.rbaud_target_type)
        .order_by(RbAdminAudit.rbaud_target_type)).all()
    return {'actions': [{'action': action, 'count': count} for action, count in actions],
            'target_types': [{'target_type': target_type, 'count': count}
                             for target_type, count in types]}
