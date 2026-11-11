"""
Authorization helpers (ACL-3, D11).

`require_admin` runs as a `before_request` hook
(`api_admin.before_request(require_admin)`), so every route of the admin
blueprint, including ones added later, is covered.

Order of the checks: not logged in -> the unauthorized handler (JSON 401, or a
redirect to the app's login screen; never 403); logged in but not admin -> 403,
rendered by the error handler as JSON for JSON clients and as the inline error
page for browsers.
"""
from flask import abort, current_app
from flask_login import current_user


def require_admin():
    """Return a response to stop the request, or None to let it through."""
    if not current_user.is_authenticated:
        return current_app.login_manager.unauthorized()
    if not current_user.is_admin:
        abort(403)
    return None
