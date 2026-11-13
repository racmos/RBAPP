"""Server-side sessions (F9-a): one `rbsessions` row per sign-in.

Identity format (S2): the cookie value Flask-Login stores (`_user_id` in the Flask session and
the remember cookie) is `s:<token>`, with `token = secrets.token_urlsafe(32)`; only
`sha256(token)` is stored. A pre-F9 cookie (a plain user id) never matches and loads as
anonymous.

A session is active while it is not revoked and
- remembered: before its absolute `expires_at` (30 days from sign-in, never extended);
- not remembered: within `IDLE_TIMEOUT` (12 h) of `last_seen_at`.
`last_seen_at` is written at most once every `TOUCH_INTERVAL` (5 min) per session.

`sign_in` is the one function that creates a row and calls `login_user` (F9-e adds the second
factor to it). The revocation helpers below are used by logout, the device list, a password
change and `flask users block|set-password`. Time comes from `clock.utcnow()` (freezable).
"""
from __future__ import annotations

import hashlib
import ipaddress
import secrets
from datetime import timedelta
from typing import Optional

import sqlalchemy as sa
from flask import current_app, has_request_context, request
from flask_login import current_user, login_user

from app import db
from app.models import RbSession, User
from app.utils import clock

TOKEN_PREFIX = 's:'
IDLE_TIMEOUT = timedelta(hours=12)
TOUCH_INTERVAL = timedelta(minutes=5)
USER_AGENT_MAX = 255
IPV4_PREFIX = 24
IPV6_PREFIX = 48
UNKNOWN_DEVICE = 'Unknown device'

# First match wins (S7). Edge and Opera also say `Chrome/`; Chrome also says `Safari/`.
_BROWSERS = ((('Edg/',), 'Edge'), (('OPR/', 'Opera'), 'Opera'), (('Firefox/',), 'Firefox'),
             (('Chrome/', 'CriOS/'), 'Chrome'), (('Safari/',), 'Safari'))
# iOS and Android user agents also say `Mac OS X` and `Linux`.
_SYSTEMS = ((('Windows',), 'Windows'), (('iPhone', 'iPad'), 'iOS'), (('Android',), 'Android'),
            (('CrOS',), 'ChromeOS'), (('Mac OS X', 'Macintosh'), 'macOS'), (('Linux',), 'Linux'))


def hash_token(token: str) -> str:
    """64 lowercase hex characters: what `rbses_token_hash` stores."""
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def ip_prefix(address: Optional[str]) -> Optional[str]:
    """The /24 (IPv4) or /48 (IPv6) network of `address` in CIDR text; None when it cannot be
    read. An IPv4-mapped IPv6 address counts as IPv4. The address itself is never kept (S6)."""
    if not address:
        return None
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return None
    if parsed.version == 6 and parsed.ipv4_mapped is not None:
        parsed = parsed.ipv4_mapped
    if parsed.version == 4:
        return str(ipaddress.IPv4Network((int(parsed), IPV4_PREFIX), strict=False))
    return ipaddress.IPv6Network((int(parsed), IPV6_PREFIX), strict=False).compressed


def device_label(user_agent: Optional[str]) -> str:
    """`"<browser> on <OS>"`, `"<browser>"` without a known OS, `"Unknown device"` without a
    User-Agent (S7). Computed on read; no parsing library."""
    if not user_agent:
        return UNKNOWN_DEVICE
    browser = next((name for needles, name in _BROWSERS
                    if any(n in user_agent for n in needles)), 'Browser')
    system = next((name for needles, name in _SYSTEMS
                   if any(n in user_agent for n in needles)), None)
    return f'{browser} on {system}' if system else browser


def active_clause(now):
    """SQL condition of an active session at `now` (the loader rule, S3)."""
    return sa.and_(
        RbSession.rbses_revoked_at.is_(None),
        sa.or_(
            sa.and_(RbSession.rbses_remember.is_(True), RbSession.rbses_expires_at > now),
            sa.and_(RbSession.rbses_remember.is_(False),
                    RbSession.rbses_last_seen_at > now - IDLE_TIMEOUT)))


def _is_active(row: RbSession, now) -> bool:
    if row.rbses_revoked_at is not None:
        return False
    if row.rbses_remember:
        return row.rbses_expires_at is not None and row.rbses_expires_at > now
    return row.rbses_last_seen_at > now - IDLE_TIMEOUT


def _attach(user: User, token: str, row_id: int) -> None:
    """Give `user` its session for this request: `get_id()` returns `s:<token>`."""
    user.session_token = token
    user.session_id = row_id


def sign_in(user: User, *, remember: bool, auth_method: str = 'password') -> RbSession:
    """Create the session row of a successful sign-in, then `login_user` (S5).

    Needs a request context (User-Agent, client address). Commits the row.
    """
    now = clock.utcnow()
    token = secrets.token_urlsafe(32)
    agent = request.headers.get('User-Agent') or None
    row = RbSession(
        rbses_user_id=user.id,
        rbses_token_hash=hash_token(token),
        rbses_created_at=now,
        rbses_last_seen_at=now,
        rbses_expires_at=(now + current_app.config['REMEMBER_COOKIE_DURATION']
                          if remember else None),
        rbses_remember=bool(remember),
        rbses_auth_method=auth_method,
        rbses_mfa=False,
        rbses_reauth_at=now,
        rbses_user_agent=agent[:USER_AGENT_MAX] if agent else None,
        rbses_ip_prefix=ip_prefix(request.remote_addr),
    )
    db.session.add(row)
    db.session.commit()
    _attach(user, token, row.rbses_id)
    login_user(user, remember=remember)
    return row


def load_identity(raw_id) -> Optional[User]:
    """The Flask-Login user loader (S3): the user of an active session, or None.

    A value without the `s:` prefix (every pre-F9 cookie) is anonymous without a query.
    Otherwise ONE select (session joined with its user); `last_seen_at` is written only when
    it is at least 5 minutes old (S4).
    """
    if not isinstance(raw_id, str) or not raw_id.startswith(TOKEN_PREFIX):
        return None
    token = raw_id[len(TOKEN_PREFIX):]
    if not token:
        return None
    found = db.session.execute(
        sa.select(RbSession, User)
        .join(User, User.id == RbSession.rbses_user_id)
        .where(RbSession.rbses_token_hash == hash_token(token))
    ).first()
    if found is None:
        return None
    row, user = found
    now = clock.utcnow()
    if user.is_blocked or not _is_active(row, now):
        return None
    row_id = row.rbses_id
    if now - row.rbses_last_seen_at >= TOUCH_INTERVAL:
        db.session.execute(sa.update(RbSession).where(RbSession.rbses_id == row_id)
                           .values(rbses_last_seen_at=now))
        db.session.commit()
    _attach(user, token, row_id)
    return user


def current_id() -> Optional[int]:
    """Id of the session behind the current request; None when anonymous or outside one."""
    if not has_request_context() or not current_user.is_authenticated:
        return None
    return getattr(current_user._get_current_object(), 'session_id', None)


def current() -> Optional[RbSession]:
    """The session row behind the current request (None when anonymous)."""
    row_id = current_id()
    return db.session.get(RbSession, row_id) if row_id is not None else None


def _revoke(*conditions, commit: bool) -> int:
    """Set `revoked_at` on the active sessions that match; returns how many."""
    now = clock.utcnow()
    result = db.session.execute(
        sa.update(RbSession).where(active_clause(now), *conditions)
        .values(rbses_revoked_at=now)
        .execution_options(synchronize_session=False))
    if commit:
        db.session.commit()
    return result.rowcount


def revoke(user_id: int, session_id: int) -> int:
    """End one active session of `user_id` (1) or nothing (0: not theirs, unknown, ended)."""
    return _revoke(RbSession.rbses_user_id == user_id, RbSession.rbses_id == session_id,
                   commit=True)


def revoke_others(user_id: int, keep_id: Optional[int], *, commit: bool = True) -> int:
    """End every active session of `user_id` except `keep_id`. `commit=False` leaves the
    change in the caller's transaction (a password change)."""
    conditions = [RbSession.rbses_user_id == user_id]
    if keep_id is not None:
        conditions.append(RbSession.rbses_id != keep_id)
    return _revoke(*conditions, commit=commit)


def revoke_all(user_id: int, *, commit: bool = True) -> int:
    """End every active session of `user_id` (`flask users block|set-password`)."""
    return revoke_others(user_id, None, commit=commit)


def list_active(user_id: int, current: Optional[int]) -> list[RbSession]:
    """The active sessions of `user_id`: `current` first, then the most recently used."""
    now = clock.utcnow()
    rows = db.session.execute(
        sa.select(RbSession)
        .where(RbSession.rbses_user_id == user_id, active_clause(now))
        .order_by(RbSession.rbses_last_seen_at.desc(), RbSession.rbses_id.desc())
    ).scalars().all()
    return sorted(rows, key=lambda r: r.rbses_id != current)


def _expired_clause(now):
    """Rows `purge` deletes: revoked, or ended per the rules above (S13)."""
    return sa.or_(
        RbSession.rbses_revoked_at.is_not(None),
        sa.and_(RbSession.rbses_remember.is_(True), RbSession.rbses_expires_at <= now),
        sa.and_(RbSession.rbses_remember.is_(False),
                RbSession.rbses_last_seen_at <= now - IDLE_TIMEOUT))


def purge(*, dry_run: bool = False) -> int:
    """Delete every ended session (`flask sessions purge`, job `sessions_purge`). Active ones
    are never touched. With `dry_run` only counts them."""
    condition = _expired_clause(clock.utcnow())
    if dry_run:
        return db.session.execute(
            sa.select(sa.func.count()).select_from(RbSession).where(condition)).scalar_one()
    result = db.session.execute(sa.delete(RbSession).where(condition)
                                .execution_options(synchronize_session=False))
    db.session.commit()
    return result.rowcount


def _iso(moment) -> Optional[str]:
    return moment.strftime('%Y-%m-%dT%H:%M:%SZ') if moment is not None else None


def session_payload(row: RbSession, current: Optional[int]) -> dict:
    """The `Session` shape of the API (S10). Never the token or its hash."""
    return {
        'id': row.rbses_id,
        'current': row.rbses_id == current,
        'device': device_label(row.rbses_user_agent),
        'user_agent': row.rbses_user_agent,
        'ip_prefix': row.rbses_ip_prefix,
        'created_at': _iso(row.rbses_created_at),
        'last_seen_at': _iso(row.rbses_last_seen_at),
        'expires_at': _iso(row.rbses_expires_at),
        'remember': bool(row.rbses_remember),
        'auth_method': row.rbses_auth_method,
        'mfa': bool(row.rbses_mfa),
    }


def mark_reauth(session_id: int):
    """Set `reauth_at = now` on one session (POST /me/reauth, F9-b S11) and commit; returns
    the time written. Only that session: the user's other sessions keep their own."""
    now = clock.utcnow()
    db.session.execute(sa.update(RbSession).where(RbSession.rbses_id == session_id)
                       .values(rbses_reauth_at=now)
                       .execution_options(synchronize_session='fetch'))
    db.session.commit()
    return now


def count_active(user_id: int) -> int:
    """How many active sessions `user_id` has (the `GET /me` security summary, F9-b S7)."""
    return db.session.execute(
        sa.select(sa.func.count()).select_from(RbSession)
        .where(RbSession.rbses_user_id == user_id, active_clause(clock.utcnow()))).scalar_one()
