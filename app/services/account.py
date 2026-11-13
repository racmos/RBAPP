"""Account changes of the signed-in user: email and password (PROF-1, PROF-2, F9-b S5).

A password change ends every other active session of the user in the same transaction; the
session of the request stays (F9-a S9). An e-mail-only change ends nothing.

Rules: the e-mail is optional (`None` removes it; F9-b S5) and unique ignoring case; an
e-mail change or removal needs neither the password nor a re-authentication. A new password
needs the current one when the account has a password; an account without one (OAuth-only)
sets its first password after a recent re-authentication instead, which the route checks
(`app.security.reauth_required`) before calling `update_account`. `set_password` stamps
`password_changed_at` (S3). Returns an `AccountStatus`; the caller turns it into a response.
Nothing is written unless it is `OK`.
"""
from enum import StrEnum

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import User
from app.services import sessions

ACCOUNT_RATE_LIMIT = '10/hour'
CURRENT_PASSWORD_INCORRECT = 'The current password is incorrect'
EMAIL_IN_USE = 'That email address is already in use'

# `email` default of `update_account`: leave the e-mail as it is (the key was not sent).
UNCHANGED = object()


class AccountStatus(StrEnum):
    OK = 'ok'
    CURRENT_PASSWORD_REQUIRED = 'current_password_required'
    WRONG_PASSWORD = 'wrong_password'
    EMAIL_TAKEN = 'email_taken'


def update_account(user, email=UNCHANGED, password=None, current_password=None):
    """Apply the changes that were sent and commit them in one transaction.

    `email`: `UNCHANGED` (default), `None` (remove it) or the new address.
    """
    if password is not None and user.has_password:
        if not current_password:
            return AccountStatus.CURRENT_PASSWORD_REQUIRED
        if not user.check_password(current_password):
            return AccountStatus.WRONG_PASSWORD

    if email is not UNCHANGED:
        if email is not None:
            taken = User.query.filter(func.lower(User.email) == email.lower(),
                                      User.id != user.id).first()
            if taken:
                return AccountStatus.EMAIL_TAKEN
        user.email = email

    if password is not None:
        user.set_password(password)

    try:
        if password is not None:
            # Inside the try: this UPDATE autoflushes the e-mail, which may lose the race.
            sessions.revoke_others(user.id, sessions.current_id(), commit=False)
        db.session.commit()
    except IntegrityError:
        # Lost a race against another account taking the address.
        db.session.rollback()
        return AccountStatus.EMAIL_TAKEN
    return AccountStatus.OK


# --- Re-authentication (F9-b S11) -------------------------------------------------------------

REAUTH_RATE_LIMIT = '20/hour'
NO_PASSWORD = 'This account has no password'
NO_TWO_FACTOR = 'Two-factor authentication is not enabled'


class ReauthStatus(StrEnum):
    OK = 'ok'
    WRONG_PASSWORD = 'wrong_password'
    NO_PASSWORD = 'no_password'
    NO_TWO_FACTOR = 'no_two_factor'


def reauthenticate(user, password=None, code=None):
    """Check the password (or, from F9-d, a TOTP `code`) of `user` and, when it is right, set
    `reauth_at = now` on the CURRENT session only. Returns `(status, reauth_at or None)`.

    A wrong password writes nothing and never touches `failed_login_count` (the route is
    rate limited instead)."""
    if code is not None:
        return ReauthStatus.NO_TWO_FACTOR, None
    if not user.has_password:
        return ReauthStatus.NO_PASSWORD, None
    if not user.check_password(password):
        return ReauthStatus.WRONG_PASSWORD, None
    return ReauthStatus.OK, sessions.mark_reauth(sessions.current_id())
