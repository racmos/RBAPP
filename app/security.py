"""
Authorization helpers (ACL-3, D11).

`admin_required` guards single views; `require_admin` is the same check as a
`before_request` hook (`price_bp.before_request(require_admin)`), so every
route of a blueprint, including ones added later, is covered.

Order of the checks: not logged in -> the usual login redirect (never 403);
logged in but not admin -> 403, rendered by the error handler as JSON for JSON
clients and as `errors/403.html` for browsers.
"""
from functools import wraps

from flask import abort, current_app
from flask_login import current_user


def require_admin():
    """Return a response to stop the request, or None to let it through."""
    if not current_user.is_authenticated:
        return current_app.login_manager.unauthorized()
    if not current_user.is_admin:
        abort(403)
    return None


def admin_required(view):
    """Decorator form of `require_admin`; replaces `@login_required`."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        denied = require_admin()
        if denied is not None:
            return denied
        return view(*args, **kwargs)
    return wrapped
