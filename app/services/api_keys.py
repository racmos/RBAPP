"""Personal read-only API keys (F9-h): one per user, shown once, stored as sha256.

Format (S2): `rb_live_` + 40 lower-case hex characters (`secrets.token_hex(20)`, 160 bits).
Stored: `sha256(key)` (hex) and the first 14 characters (`rb_live_` + 6 hex). The key itself is
never stored or logged.

Bearer authentication (S7-S12). A request whose path starts with `/riftbound/api/v1/` and whose
`Authorization` header uses the `Bearer` scheme (any case) is authenticated ONLY by its key:

- `BearerCookieGuard` (WSGI, around the whole app) removes its `Cookie` header before Flask sees
  it, so neither the session cookie nor the remember cookie can identify it, and
  `gate` replaces its Flask session with the null session, which is never saved: no
  `Set-Cookie`, no session row, `rbses_last_seen_at` untouched (S9).
- Flask-Login then finds no session and no remember cookie and asks the request loader
  (`request_user`), which answers the key's user (one SELECT, key joined with its user; cached
  in the request's WSGI environ, which never outlives the request).
- `gate` runs as the FIRST `before_request` hook, before the CSRF check, so a refused key never
  reaches it (S8): an invalid key or a blocked user → 401 `api_key_invalid`; then the
  60/minute limit per key (S11); then `last_used_at` (S12); then any method but GET/HEAD →
  403 `api_key_read_only`; then the deny list → 403 `api_key_read_only`. There is no CSRF
  exemption: no unsafe request is ever accepted with a key.
- A key never grants admin rights: the deny list refuses `/admin/` and `require_admin` refuses
  any key request (`via_key`).

Two-factor authentication does not apply to key requests; password changes and session
revocation leave the key alone; a blocked user's key is invalid until unblocked (S10).
"""
from __future__ import annotations

import hashlib
import math
import re
import secrets
import time
from datetime import timedelta
from typing import Optional

import sqlalchemy as sa
from flask import current_app, g, request
from flask.globals import request_ctx
from flask_login import current_user
from limits import parse

from app import db, limiter
from app.api.error_codes import ErrorCode
from app.errors import json_error, rate_limited_response
from app.models import RbApiKey, User
from app.utils import clock

KEY_PREFIX = 'rb_live_'
KEY_FORMAT = re.compile(r'rb_live_[0-9a-f]{40}')
PREFIX_LENGTH = 14
API_PATH = '/riftbound/api/v1'
READ_METHODS = frozenset({'GET', 'HEAD'})
# S8.3: refused even for GET (prefix match on the path after `/riftbound/api/v1`), and
# exactly `/me`.
DENIED_PREFIXES = ('/auth/', '/admin/', '/me/account', '/me/reauth', '/me/sessions', '/me/2fa',
                   '/me/api-key', '/me/avatar', '/me/connections')
DENIED_EXACT = ('/me',)
RATE_LIMIT = '60/minute'
RATE_SCOPE = 'api_key'
TOUCH_INTERVAL = timedelta(minutes=1)

INVALID_MESSAGE = 'The API key is not valid'
READ_ONLY_MESSAGE = 'API keys can only read data'

_LIMIT = parse(RATE_LIMIT)
_BEARER = 'bearer'
# Environ key of what `request_user` found for this request: (key id, last_used_at, user) or None.
_ENVIRON_KEY = 'riftbound.api_key'


# --- Keys --------------------------------------------------------------------------------

def new_key() -> str:
    """A new key: `rb_live_` + 40 lower-case hex characters (160 bits)."""
    return KEY_PREFIX + secrets.token_hex(20)


def hash_key(key: str) -> str:
    """64 lower-case hex characters: what `rbapk_key_hash` stores."""
    return hashlib.sha256(key.encode('utf-8')).hexdigest()


def key_prefix(key: str) -> str:
    """The first 14 characters (`rb_live_` + 6 hex): what the user sees to recognise it."""
    return key[:PREFIX_LENGTH]


def _iso(moment) -> Optional[str]:
    return moment.strftime('%Y-%m-%dT%H:%M:%SZ') if moment is not None else None


def info(row: Optional[RbApiKey]) -> Optional[dict]:
    """The `ApiKeyInfo` shape (S3): `{prefix, created_at, last_used_at}`, or None. Never the
    key or its hash."""
    if row is None:
        return None
    return {'prefix': row.rbapk_prefix, 'created_at': _iso(row.rbapk_created_at),
            'last_used_at': _iso(row.rbapk_last_used_at)}


def get_info(user_id: int) -> Optional[dict]:
    """The key info of `user_id` or None (`GET /me/api-key`, `GET /me` `security.api_key`).
    One statement."""
    return info(db.session.execute(
        sa.select(RbApiKey).where(RbApiKey.rbapk_user_id == user_id)).scalar_one_or_none())


def create(user_id: int) -> tuple[str, dict]:
    """Create the key of `user_id`, replacing the existing one in the same transaction (the old
    key stops working at once, S4); commits. Returns `(key, info)`: the only time the key
    exists outside the caller's hands."""
    key = new_key()
    db.session.execute(sa.delete(RbApiKey).where(RbApiKey.rbapk_user_id == user_id)
                       .execution_options(synchronize_session=False))
    row = RbApiKey(rbapk_user_id=user_id, rbapk_prefix=key_prefix(key),
                   rbapk_key_hash=hash_key(key), rbapk_created_at=clock.utcnow(),
                   rbapk_last_used_at=None)
    db.session.add(row)
    db.session.commit()
    return key, info(row)


def revoke(user_id: int) -> None:
    """Delete the key of `user_id` (none: nothing happens) and commit (S5)."""
    db.session.execute(sa.delete(RbApiKey).where(RbApiKey.rbapk_user_id == user_id)
                       .execution_options(synchronize_session=False))
    db.session.commit()


# --- Bearer requests ---------------------------------------------------------------------

def _bearer_value(path: str, authorization: Optional[str]) -> Optional[str]:
    """The credential of a bearer request under the API prefix, else None (S7)."""
    if not path.startswith(API_PATH + '/') or not authorization:
        return None
    scheme, _, value = authorization.strip().partition(' ')
    if scheme.lower() != _BEARER:
        return None
    return value.strip()


def is_bearer_request() -> bool:
    """True for a request authenticated (or refused) by an API key."""
    return _bearer_value(request.path, request.headers.get('Authorization')) is not None


def via_key() -> bool:
    """True when the current request runs as an API key's user (never admin, S9)."""
    return is_bearer_request()


class BearerCookieGuard:
    """WSGI middleware: a bearer request under the API prefix loses its `Cookie` header, so no
    cookie (session, remember) can identify it or be refreshed (S7, S9). It reads the same path
    as `request.path` (`PATH_INFO`), so it and `gate` always agree on what a bearer request is."""

    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO') or ''
        if _bearer_value(path, environ.get('HTTP_AUTHORIZATION')) is not None:
            environ.pop('HTTP_COOKIE', None)
        return self.wsgi_app(environ, start_response)


def _authenticate(value: str):
    """`(key id, last_used_at, user)` of a well-formed key of an unblocked user, else None.
    A malformed value costs no statement; otherwise ONE select (key joined with its user)."""
    if not KEY_FORMAT.fullmatch(value):
        return None
    found = db.session.execute(
        sa.select(RbApiKey.rbapk_id, RbApiKey.rbapk_last_used_at, User)
        .join(User, User.id == RbApiKey.rbapk_user_id)
        .where(RbApiKey.rbapk_key_hash == hash_key(value))
    ).first()
    if found is None or found[2].is_blocked:
        return None
    return tuple(found)


def request_user() -> Optional[User]:
    """The Flask-Login request loader: the key's user for a bearer request, else None. Loaded
    once per request (cached in the WSGI environ)."""
    found = _request_key()
    return found[2] if found is not None else None


def _request_key():
    """`(key id, last_used_at, user)` of this bearer request, or None; one lookup per request."""
    if not is_bearer_request():
        return None
    if _ENVIRON_KEY not in request.environ:
        value = _bearer_value(request.path, request.headers.get('Authorization'))
        request.environ[_ENVIRON_KEY] = _authenticate(value)
    return request.environ[_ENVIRON_KEY]


def _normalised_rest(path: str) -> str:
    """The path after `/riftbound/api/v1`, with runs of `/` collapsed."""
    return re.sub(r'/{2,}', '/', path[len(API_PATH):])


def is_denied(path: str, rule: Optional[str] = None) -> bool:
    """True when the request path (or the URL rule it matched) is on the deny list (S8.3)."""
    for candidate in (path, rule):
        if not candidate or not candidate.startswith(API_PATH + '/'):
            continue
        rest = _normalised_rest(candidate)
        if rest.rstrip('/') in DENIED_EXACT or rest.startswith(DENIED_PREFIXES):
            return True
    return False


def _rate_limited(key_id: int) -> Optional[int]:
    """Count one request of key `key_id` (60/minute, scope `api_key`, Flask-Limiter's storage);
    the seconds until the window resets when the limit is exceeded, else None. Off with the
    limiter (`RATELIMIT_ENABLED`)."""
    if not limiter.enabled:
        return None
    strategy = limiter.limiter
    if strategy.hit(_LIMIT, RATE_SCOPE, str(key_id)):
        return None
    reset_at = strategy.get_window_stats(_LIMIT, RATE_SCOPE, str(key_id)).reset_time
    return max(1, math.ceil(reset_at - time.time()))


def _touch(key_id: int, last_used_at) -> None:
    """S12: write `last_used_at` when it is null or at least a minute old (one UPDATE)."""
    now = clock.utcnow()
    if last_used_at is not None and now - last_used_at < TOUCH_INTERVAL:
        return
    db.session.execute(sa.update(RbApiKey).where(RbApiKey.rbapk_id == key_id)
                       .values(rbapk_last_used_at=now)
                       .execution_options(synchronize_session=False))
    db.session.commit()


def gate():
    """The first `before_request` hook (before CSRF): the S8 checks of a bearer request.
    Returns the refusal, or None to let it run as the key's user."""
    if not is_bearer_request():
        return None
    # A null session is never saved: nothing of this request can reach a cookie.
    request_ctx.session = current_app.session_interface.make_null_session(current_app)
    # The identity of this request comes from its key only: drop any user Flask-Login cached
    # in the application context, so `current_user` is loaded again (through `request_user`).
    g.pop('_login_user', None)
    found = _request_key()
    if found is None or not current_user.is_authenticated:          # S8.1
        return json_error('Unauthorized', INVALID_MESSAGE, 401, code=ErrorCode.API_KEY_INVALID)
    key_id, last_used_at, _user = found
    retry_after = _rate_limited(key_id)
    if retry_after is not None:
        return rate_limited_response(retry_after)
    _touch(key_id, last_used_at)
    rule = request.url_rule.rule if request.url_rule is not None else None
    if request.method not in READ_METHODS or is_denied(request.path, rule):
        return json_error('Forbidden', READ_ONLY_MESSAGE, 403, code=ErrorCode.API_KEY_READ_ONLY)
    return None
