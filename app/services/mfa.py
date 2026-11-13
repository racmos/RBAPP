"""TOTP two-factor authentication (F9-d S4-S6, S8-S11, S14, S15).

Secret: `pyotp.random_base32()` (32 characters, 160 bits), stored only as
`Fernet(TOTP_ENCRYPTION_KEY).encrypt(...)` in `rbusermfa.rbmfa_secret_enc`. The clear secret
leaves this module once, in the `setup` answer, and is never logged. Codes: SHA-1, 6 digits,
30-second steps (the authenticator-app defaults).

Check (`verify_totp`): spaces removed, exactly 6 ASCII digits, equal (constant time) to the
code of a step `s` in `current - 1 .. current + 1` with `s > last_step`; on success
`last_step = s` is set on the row and the CALLER commits it with the rest of its change, so a
code is never accepted twice.

Recovery codes: 10 per generation, 10 characters of `RECOVERY_ALPHABET` shown as
`xxxxx-xxxxx`; only `sha256` of the normalised code (lower case, no spaces or hyphens) is
stored. A code matches an unused row of the user (constant time, every row compared) and is
marked used; regenerating deletes every previous row.

2FA is unavailable (`available()` is False, `MfaUnavailable` raised) without a valid key (a
development app without `TOTP_ENCRYPTION_KEY`) and when a stored secret cannot be decrypted
(the key changed): that is logged with the user id, never the secret. Time comes from
`clock.utcnow()`. Nothing here reads the request; the routes pass the session to keep.
"""
from __future__ import annotations

import calendar
import hashlib
import hmac
import logging
import re
import secrets
from enum import StrEnum
from typing import Optional
from urllib.parse import quote

import pyotp
import segno
import sqlalchemy as sa
from cryptography.fernet import Fernet, InvalidToken
from flask import current_app

from app import db
from app.models import RbRecoveryCode, RbSession, RbUserMfa
from app.services import sessions
from app.utils import clock

logger = logging.getLogger(__name__)

ISSUER = 'Rift Manager'
PERIOD = 30                     # seconds per TOTP step
DIGITS = 6
WINDOW = 1                      # steps accepted on each side of the current one
RECOVERY_ALPHABET = 'abcdefghjkmnpqrstuvwxyz23456789'
RECOVERY_COUNT = 10
RECOVERY_LENGTH = 10
MFA_RATE_LIMIT = '20/hour'
QR_ERROR_LEVEL = 'm'

CODE_INVALID = 'The code is not valid'
ALREADY_ON = 'Two-factor authentication is already on'
NOT_SET_UP = 'Two-factor authentication is not set up'
NOT_ON = 'Two-factor authentication is not on'
NOT_AVAILABLE = 'Two-factor authentication is not available'

_SIX_DIGITS = re.compile(r'[0-9]{6}')
_RECOVERY_NOISE = re.compile(r'[\s-]+')


class MfaUnavailable(RuntimeError):
    """No usable key, or a stored secret that the key cannot decrypt (S11)."""


class AlreadyEnabled(Exception):
    """`setup` of a user whose 2FA is already on (S7)."""


class MfaStatus(StrEnum):
    OK = 'ok'
    NOT_FOUND = 'not_found'             # no pending setup (enable) / 2FA not on (disable, codes)
    ALREADY_ENABLED = 'already_enabled'
    INVALID = 'invalid'                 # wrong or replayed code


# --- The key and the secret at rest (S2, S4, S11) -------------------------------------------

def _fernet() -> Fernet:
    key = current_app.config.get('TOTP_ENCRYPTION_KEY')
    if not key:
        raise MfaUnavailable('TOTP_ENCRYPTION_KEY is not set')
    try:
        return Fernet(key)
    except (ValueError, TypeError):
        raise MfaUnavailable('TOTP_ENCRYPTION_KEY is not a valid key') from None


def available() -> bool:
    """True when the app has a valid TOTP_ENCRYPTION_KEY."""
    try:
        _fernet()
    except MfaUnavailable:
        return False
    return True


def encrypt_secret(secret: str) -> str:
    """The Fernet token (text) of `secret`; a new random IV every time."""
    return _fernet().encrypt(secret.encode('ascii')).decode('ascii')


def decrypt_secret(token: str, *, user_id: int) -> str:
    """The clear secret of `token`; `MfaUnavailable` (logged without the secret) when the key
    cannot decrypt it."""
    fernet = _fernet()
    try:
        return fernet.decrypt(token.encode('ascii')).decode('ascii')
    except (InvalidToken, ValueError, UnicodeError):
        logger.error('The TOTP secret of user %s cannot be decrypted '
                     '(was TOTP_ENCRYPTION_KEY changed?)', user_id)
        raise MfaUnavailable('the stored secret cannot be decrypted') from None


# --- Rows and status (S14) -----------------------------------------------------------------

def get_row(user_id: int) -> Optional[RbUserMfa]:
    return db.session.get(RbUserMfa, user_id)


def is_enabled(user_id: int) -> bool:
    """True when `user_id` has 2FA on (a pending setup is not on). One statement."""
    return db.session.execute(
        sa.select(RbUserMfa.rbmfa_user_id).where(RbUserMfa.rbmfa_user_id == user_id,
                                                 RbUserMfa.rbmfa_enabled_at.is_not(None))
    ).first() is not None


def status(user_id: int) -> dict:
    """`security.mfa` of `GET /me`: `{available, enabled, pending, recovery_codes_left}`
    (unused codes; 0 when off). One statement."""
    left = (sa.select(sa.func.count()).select_from(RbRecoveryCode)
            .where(RbRecoveryCode.rbrco_user_id == user_id,
                   RbRecoveryCode.rbrco_used_at.is_(None))
            .scalar_subquery())
    found = db.session.execute(
        sa.select(RbUserMfa.rbmfa_enabled_at, left)
        .where(RbUserMfa.rbmfa_user_id == user_id)).first()
    enabled = found is not None and found[0] is not None
    return {'available': available(), 'enabled': enabled,
            'pending': found is not None and found[0] is None,
            'recovery_codes_left': int(found[1]) if enabled else 0}


# --- TOTP (S4, S5) -------------------------------------------------------------------------

def current_step() -> int:
    """`unix_time // 30` of `clock.utcnow()` (naive UTC)."""
    return calendar.timegm(clock.utcnow().utctimetuple()) // PERIOD


def _clean_totp(code: str) -> Optional[str]:
    """`code` without whitespace when it is then exactly 6 ASCII digits, else None."""
    text = ''.join(str(code).split())
    return text if _SIX_DIGITS.fullmatch(text) else None


def verify_totp(user, code: str, *, row: Optional[RbUserMfa] = None) -> bool:
    """S5. True when `code` is the code of a step in the window that is later than the last
    accepted one; then `last_step` is set on the row (the caller commits). False otherwise,
    changing nothing. Works on the user's row whatever its state (the callers check it)."""
    row = row if row is not None else get_row(user.id)
    given = _clean_totp(code)
    if row is None or given is None:
        return False
    totp = pyotp.TOTP(decrypt_secret(row.rbmfa_secret_enc, user_id=user.id),
                      digits=DIGITS, interval=PERIOD)
    now = current_step()
    last = row.rbmfa_last_step
    accepted = None
    for step in range(now - WINDOW, now + WINDOW + 1):
        # Every step is compared (no early exit), each in constant time.
        same = hmac.compare_digest(totp.generate_otp(step).encode('ascii'),
                                   given.encode('ascii'))
        if same and accepted is None and (last is None or step > last):
            accepted = step
    if accepted is None:
        return False
    row.rbmfa_last_step = accepted
    return True


# --- Recovery codes (S6) -------------------------------------------------------------------

def normalise_recovery_code(code: str) -> str:
    return _RECOVERY_NOISE.sub('', str(code)).lower()


def hash_recovery_code(code: str) -> str:
    """64 lowercase hex characters: what `rbrco_code_hash` stores."""
    return hashlib.sha256(normalise_recovery_code(code).encode('utf-8')).hexdigest()


def _new_recovery_code() -> str:
    raw = ''.join(secrets.choice(RECOVERY_ALPHABET) for _ in range(RECOVERY_LENGTH))
    return f'{raw[:5]}-{raw[5:]}'


def new_recovery_codes(user_id: int) -> list[str]:
    """Delete every recovery code of `user_id` and add 10 new ones (the caller commits);
    returns them as shown to the user. They are never stored in clear."""
    db.session.execute(sa.delete(RbRecoveryCode).where(RbRecoveryCode.rbrco_user_id == user_id)
                       .execution_options(synchronize_session=False))
    codes: list[str] = []
    while len(codes) < RECOVERY_COUNT:
        candidate = _new_recovery_code()
        if candidate not in codes:
            codes.append(candidate)
    db.session.add_all(RbRecoveryCode(rbrco_user_id=user_id,
                                      rbrco_code_hash=hash_recovery_code(c)) for c in codes)
    return codes


def use_recovery_code(user, code: str) -> bool:
    """True when `code` matches an unused recovery code of `user`; that code is then marked
    used (the caller commits). Every unused code is compared in constant time."""
    wanted = hash_recovery_code(code).encode('ascii')
    rows = db.session.execute(sa.select(RbRecoveryCode).where(
        RbRecoveryCode.rbrco_user_id == user.id,
        RbRecoveryCode.rbrco_used_at.is_(None))).scalars().all()
    match = None
    for row in rows:
        if hmac.compare_digest(row.rbrco_code_hash.strip().encode('ascii'), wanted) \
                and match is None:
            match = row
    if match is None:
        return False
    match.rbrco_used_at = clock.utcnow()
    return True


# --- Lifecycle (S7-S10, S15) ---------------------------------------------------------------

def _grouped(secret: str) -> str:
    return ' '.join(secret[i:i + 4] for i in range(0, len(secret), 4))


def otpauth_uri(username: str, secret: str) -> str:
    issuer = quote(ISSUER, safe='')
    return (f'otpauth://totp/{issuer}:{quote(username, safe="")}'
            f'?secret={secret}&issuer={issuer}')


def qr_data_uri(uri: str) -> str:
    """An SVG data URI of the QR code of `uri` (error level M, never boosted)."""
    return segno.make_qr(uri, error=QR_ERROR_LEVEL, boost_error=False).svg_data_uri(scale=5)


def setup(user) -> dict:
    """S7: a new secret for a pending setup (replacing any earlier pending one), committed.
    Returns `{secret (grouped by 4), otpauth_uri, qr}`. `AlreadyEnabled` when 2FA is on;
    `MfaUnavailable` without a usable key."""
    row = get_row(user.id)
    if row is not None and row.rbmfa_enabled_at is not None:
        raise AlreadyEnabled()
    secret = pyotp.random_base32()
    encrypted = encrypt_secret(secret)
    if row is None:
        row = RbUserMfa(rbmfa_user_id=user.id)
        db.session.add(row)
    row.rbmfa_secret_enc = encrypted
    row.rbmfa_enabled_at = None
    row.rbmfa_last_step = None
    row.rbmfa_created_at = clock.utcnow()
    db.session.commit()
    uri = otpauth_uri(user.username, secret)
    return {'secret': _grouped(secret), 'otpauth_uri': uri, 'qr': qr_data_uri(uri)}


def _end_other_sessions(user_id: int, keep_session_id: Optional[int]) -> int:
    return sessions.revoke_others(user_id, keep_session_id, commit=False)


def enable(user, code: str, *, keep_session_id: Optional[int]):
    """S8: confirm the pending setup with a code. On success, in one transaction: 2FA on,
    `last_step` stored, 10 new recovery codes, the kept session marked `mfa`, every other
    session revoked. Returns `(MfaStatus, recovery codes, revoked sessions)`."""
    row = get_row(user.id)
    if row is None:
        return MfaStatus.NOT_FOUND, [], 0
    if row.rbmfa_enabled_at is not None:
        return MfaStatus.ALREADY_ENABLED, [], 0
    if not verify_totp(user, code, row=row):
        return MfaStatus.INVALID, [], 0
    row.rbmfa_enabled_at = clock.utcnow()
    codes = new_recovery_codes(user.id)
    if keep_session_id is not None:
        db.session.execute(sa.update(RbSession).where(RbSession.rbses_id == keep_session_id)
                           .values(rbses_mfa=True)
                           .execution_options(synchronize_session=False))
    revoked = _end_other_sessions(user.id, keep_session_id)
    db.session.commit()
    return MfaStatus.OK, codes, revoked


def _delete_all(user_id: int) -> None:
    """Delete the 2FA row and every recovery code of `user_id` (the caller commits). Pending
    changes (`last_step`, a used code) are flushed first; the deleted row then leaves the
    session so nothing writes to it again."""
    db.session.execute(sa.delete(RbRecoveryCode).where(RbRecoveryCode.rbrco_user_id == user_id)
                       .execution_options(synchronize_session=False))
    db.session.execute(sa.delete(RbUserMfa).where(RbUserMfa.rbmfa_user_id == user_id)
                       .execution_options(synchronize_session=False))
    loaded = db.session.identity_map.get(
        sa.inspect(RbUserMfa).identity_key_from_primary_key((user_id,)))
    if loaded is not None:
        db.session.expunge(loaded)


def disable(user, code: str, *, keep_session_id: Optional[int]):
    """S9: turn 2FA off with a TOTP code (6 digits) or a recovery code; deletes the row and
    every recovery code and revokes every other session. Returns `(MfaStatus, revoked)`."""
    row = get_row(user.id)
    if row is None or row.rbmfa_enabled_at is None:
        return MfaStatus.NOT_FOUND, 0
    if _clean_totp(code) is not None:
        passed = verify_totp(user, code, row=row)
    else:
        passed = use_recovery_code(user, code)
    if not passed:
        return MfaStatus.INVALID, 0
    _delete_all(user.id)
    revoked = _end_other_sessions(user.id, keep_session_id)
    db.session.commit()
    return MfaStatus.OK, revoked


def regenerate_codes(user, *, keep_session_id: Optional[int]):
    """S10: 10 new recovery codes replace the old ones; every other session revoked. Returns
    `(MfaStatus, recovery codes, revoked)`."""
    if not is_enabled(user.id):
        return MfaStatus.NOT_FOUND, [], 0
    codes = new_recovery_codes(user.id)
    revoked = _end_other_sessions(user.id, keep_session_id)
    db.session.commit()
    return MfaStatus.OK, codes, revoked


def reset(user) -> Optional[int]:
    """S15 (`flask users reset-2fa`, the F10 admin reset): delete the 2FA row and recovery
    codes of `user` and revoke all their sessions; returns how many sessions ended. None, and
    nothing changed, when 2FA is not on (a pending setup is left alone)."""
    if not is_enabled(user.id):
        return None
    _delete_all(user.id)
    ended = sessions.revoke_all(user.id, commit=False)
    db.session.commit()
    return ended
