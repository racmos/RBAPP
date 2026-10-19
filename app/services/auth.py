"""Login, lockout and registration (LOGIN-2..6, LOGIN-9, R3, R4, D15).

Shared by the Jinja forms and (unit e) the JSON API, so both behave the same.

`authenticate` is a small state machine:

    unknown user ............ dummy hash check ........ INVALID
    lock still running ...... dummy hash check ........ LOCKED(retry_after)
    wrong password .......... count + 1; from the 5th failure on, lock ... INVALID
    blocked, right password . nothing changes .......... INVALID  (R4)
    right password .......... reset count and lock ..... OK(user)

Exactly ONE password-hash verification happens on every path, so the work
(and the timing) does not tell an unknown name from a known one (LOGIN-5).
A blocked account looks exactly like a wrong password (R4). Only a running lock
answers differently; that is the spec'd trade-off (the user must be told to
wait) and unknown names never get it.

Lock length (R3) depends only on `failed_login_count` (it is never reset by a
lock, only by a successful login): the n-th failure, n >= LOGIN_MAX_FAILURES,
locks for min(BASE * 2**(n - MAX), CAP) minutes (15, 30, 60 ... 24 h).

Time comes from `app.utils.clock` so tests can move it (D17).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from datetime import timedelta
from typing import Optional

from flask import current_app
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from app import db
from app.models import User
from app.schemas.validators import RegisterRequest
from app.utils import clock

# Per-IP request limits of the login and register endpoints (LOGIN-7, D15). The Jinja
# forms and the JSON API share ONE budget each (same `scope`), so switching front door
# does not reset the count.
LOGIN_RATE_LIMIT = '10/minute;50/hour'
REGISTER_RATE_LIMIT = '5/hour'

USERNAME_TAKEN = 'Username already exists'
EMAIL_TAKEN = 'Email already registered'


class AuthStatus(StrEnum):
    OK = 'ok'
    INVALID = 'invalid'
    LOCKED = 'locked'
    BLOCKED = 'blocked'      # reserved: R4 makes a blocked user come back as INVALID


@dataclass(frozen=True)
class AuthResult:
    status: AuthStatus
    user: Optional[User] = None
    retry_after: Optional[int] = None      # seconds, only for LOCKED


class DuplicateUserError(Exception):
    """The username or the e-mail is already taken. `message` is the user-facing text."""

    def __init__(self, field: str):
        self.field = field
        self.message = USERNAME_TAKEN if field == 'username' else EMAIL_TAKEN
        super().__init__(self.message)


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    """A hash made with the same method as real passwords, for users that don't exist."""
    return generate_password_hash('dummy-password-for-timing-only')


def lock_minutes(failures: int, *, max_failures: int, base: int, cap: int) -> int:
    """Minutes the `failures`-th consecutive failure locks the account (0 below the threshold)."""
    if failures < max_failures:
        return 0
    return min(base * 2 ** min(failures - max_failures, 32), cap)


def _seconds_left(locked_until, now) -> int:
    return max(1, math.ceil((locked_until - now).total_seconds()))


def authenticate(username: str, password: str) -> AuthResult:
    """Check credentials and update the lockout state. Commits on every path that writes."""
    now = clock.utcnow()
    user = User.query.filter_by(username=username).first()

    if user is None:
        check_password_hash(_dummy_hash(), password)
        return AuthResult(AuthStatus.INVALID)

    if user.locked_until is not None and user.locked_until > now:
        check_password_hash(_dummy_hash(), password)
        return AuthResult(AuthStatus.LOCKED, retry_after=_seconds_left(user.locked_until, now))

    if not check_password_hash(user.password_hash, password):
        if user.is_active:                      # a blocked account keeps no failure history
            _register_failure(user, now)
        return AuthResult(AuthStatus.INVALID)

    if not user.is_active:
        return AuthResult(AuthStatus.INVALID)   # R4: same answer as a wrong password

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    db.session.commit()
    return AuthResult(AuthStatus.OK, user=user)


def _register_failure(user: User, now) -> None:
    """Count one failure atomically and start or lengthen the lock when due."""
    config = current_app.config
    # SQL-side increment: two simultaneous failures both count.
    user.failed_login_count = User.failed_login_count + 1
    db.session.flush()
    db.session.refresh(user, ['failed_login_count'])
    minutes = lock_minutes(
        user.failed_login_count,
        max_failures=config['LOGIN_MAX_FAILURES'],
        base=config['LOGIN_LOCK_BASE_MINUTES'],
        cap=config['LOGIN_LOCK_MAX_MINUTES'],
    )
    if minutes:
        user.locked_until = now + timedelta(minutes=minutes)
    db.session.commit()


def unlock_user(username: str) -> bool:
    """Clear the failure count and the lock (`flask users unlock`). False if no such user."""
    user = User.query.filter_by(username=username).first()
    if user is None:
        return False
    user.failed_login_count = 0
    user.locked_until = None
    db.session.commit()
    return True


def register_user(data: RegisterRequest) -> User:
    """Create a plain (never admin) account. Raises DuplicateUserError.

    The username is unique as typed (that is the database rule); the e-mail is
    compared ignoring case, like the profile page does. Registering does NOT log
    the user in.
    """
    if User.query.filter_by(username=data.username).first():
        raise DuplicateUserError('username')
    if User.query.filter(func.lower(User.email) == data.email.lower()).first():
        raise DuplicateUserError('email')

    user = User(username=data.username, email=data.email)
    user.set_password(data.password)
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        # Lost a race with a simultaneous registration: report what is taken now.
        db.session.rollback()
        taken = User.query.filter_by(username=data.username).first() is not None
        raise DuplicateUserError('username' if taken else 'email') from None
    return user
