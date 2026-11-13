"""The caller's signed-in devices (F9-a S10-S12): list them, end one, end all the others.

Only the caller's active sessions are ever listed or ended (another user's id, an unknown,
revoked or expired one is a 404). Logic in `app/services/sessions.py`.
"""
from flask import abort
from flask_login import current_user, login_required, logout_user

from app.api.responses import ok
from app.api.v1 import api_v1
from app.services import sessions as sessions_service


@api_v1.get('/me/sessions')
@login_required
def list_my_sessions():
    """Active sessions: the current one first, then the most recently used."""
    current = sessions_service.current_id()
    rows = sessions_service.list_active(current_user.id, current)
    return ok({'items': [sessions_service.session_payload(row, current) for row in rows]})


@api_v1.delete('/me/sessions/<int:session_id>')
@login_required
def revoke_my_session(session_id):
    """End one session; ending the current one signs the caller out like logout (S8)."""
    current = sessions_service.current_id()
    if not sessions_service.revoke(current_user.id, session_id):
        abort(404)
    is_current = session_id == current
    if is_current:
        logout_user()
    return ok({'revoked': 1, 'current': is_current})


@api_v1.delete('/me/sessions')
@login_required
def revoke_my_other_sessions():
    """End every other active session of the caller; this one stays."""
    count = sessions_service.revoke_others(current_user.id, sessions_service.current_id())
    return ok({'revoked': count})
