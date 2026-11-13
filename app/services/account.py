"""Account changes of the signed-in user: email and password (PROF-1, PROF-2).

A password change ends every other active session of the user in the same transaction; the
session of the request stays (F9-a S9). An e-mail-only change ends nothing.

The rules of the old Jinja profile update: a new password needs the current one, the email is
unique ignoring case, and an email-only update does not need the password. Returns an
`AccountStatus`; the caller turns it into a response. Nothing is written unless it is `OK`.
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


class AccountStatus(StrEnum):
    OK = 'ok'
    WRONG_PASSWORD = 'wrong_password'
    EMAIL_TAKEN = 'email_taken'


def update_account(user, email=None, password=None, current_password=None):
    """Apply the changes that were sent and commit them in one transaction."""
    if password is not None and not user.check_password(current_password or ''):
        return AccountStatus.WRONG_PASSWORD

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
