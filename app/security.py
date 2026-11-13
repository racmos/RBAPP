"""
Authorization helpers (ACL-3, D11).

`require_admin` runs as a `before_request` hook
(`api_admin.before_request(require_admin)`), so every route of the admin
blueprint, including ones added later, is covered.

Order of the checks: not logged in -> the unauthorized handler (JSON 401, or a
redirect to the app's login screen; never 403); logged in but not admin -> 403,
rendered by the error handler as JSON for JSON clients and as the inline error
page for browsers.

Re-authentication (F9-b S9, S10): `reauth_required` lets a sensitive request through only
when the CURRENT session re-authenticated (signed in, or `POST /me/reauth`) within
`REAUTH_WINDOW`; otherwise a 403 `reauth_required` with the methods the caller can use.
It goes under `login_required` (and under `validate_json` when `when` reads the body).
"""
from datetime import timedelta
from functools import wraps
from typing import Optional

from flask import abort, current_app
from flask_login import current_user

from app.api.error_codes import ErrorCode
from app.api.responses import fail
from app.services import mfa, sessions
from app.utils import clock

REAUTH_WINDOW = timedelta(minutes=10)
REAUTH_MESSAGE = 'Confirm your identity to continue'


def require_admin():
    """Return a response to stop the request, or None to let it through."""
    if not current_user.is_authenticated:
        return current_app.login_manager.unauthorized()
    if not current_user.is_admin:
        abort(403)
    return None


def reauth_until(row) -> Optional[object]:
    """End of the re-authentication window of session `row` when it is still open, else None."""
    if row is None or row.rbses_reauth_at is None:
        return None
    until = row.rbses_reauth_at + REAUTH_WINDOW
    return until if until > clock.utcnow() else None


def reauth_methods(user) -> list[str]:
    """What `user` can re-authenticate with, in the S9 order: `password` (when the account has
    one), `totp` (when 2FA is on, F9-d S13), then `discord`, `google` (F9-f) once that unit
    adds them."""
    methods = ['password'] if user.has_password else []
    if mfa.is_enabled(user.id):
        methods.append('totp')
    return methods


def reauth_failure():
    """None when the current session re-authenticated within the window; otherwise the 403
    `reauth_required` response (F9-b S9)."""
    if reauth_until(sessions.current()) is not None:
        return None
    return fail('Forbidden', REAUTH_MESSAGE, 403, code=ErrorCode.REAUTH_REQUIRED,
                params={'methods': reauth_methods(current_user)})


def reauth_required(view=None, *, when=None):
    """Decorator of a sensitive route (S10). `@reauth_required` always applies the rule;
    `@reauth_required(when=predicate)` only when `predicate()` is true for the request (the
    first password of an account without one, S5). Nothing of a refused request is applied."""
    def decorate(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if when is None or when():
                refused = reauth_failure()
                if refused is not None:
                    return refused
            return func(*args, **kwargs)
        return wrapper
    return decorate(view) if view is not None else decorate
