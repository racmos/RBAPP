"""Captcha providers for registration (LOGIN-8, D16, R11).

`CAPTCHA_PROVIDER` picks one of two providers:

    none     no challenge, every payload passes (default in testing, kill switch)
    altcha   proof-of-work challenge signed with an HMAC key (ALTCHA, PoW v1)

ALTCHA flow: the server signs a challenge that expires after
`ALTCHA_EXPIRE_SECONDS` (5 min, R11); the widget in the browser solves it and
posts a base64 payload in the form field `altcha`; `verify` checks signature,
solution and expiry, then REMEMBERS the challenge so the same payload cannot be
used again.

Replay store: table `rbcaptcha_used` (shared by every Gunicorn worker, survives
restarts). The primary key is sha256(challenge); inserting it inside a SAVEPOINT
means an IntegrityError is a replay and does not poison the surrounding
PostgreSQL transaction. Rows are deleted once their challenge has expired (an
expired payload is refused before it gets here), so the table stays tiny.

Time comes from `app.utils.clock` (D17). The library's own expiry check uses the
wall clock, so it is switched off and the expiry is checked here.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional, Protocol

from altcha import (ChallengeOptionsV1, create_challenge_v1, extract_params_v1,
                    verify_solution_v1)
from flask import current_app
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import RbCaptchaUsed
from app.utils import clock

FORM_FIELD = 'altcha'                  # name of the hidden input the widget adds to the form


class CaptchaProvider(Protocol):
    name: str

    def challenge(self) -> Optional[dict]:
        """What the page hands to the widget, or None when there is no challenge."""

    def verify(self, payload: Optional[str]) -> bool:
        """True if `payload` solves a fresh challenge that was never accepted before."""


class NoneProvider:
    name = 'none'

    def challenge(self) -> Optional[dict]:
        return None

    def verify(self, payload: Optional[str]) -> bool:
        return True


def altcha_hmac_key(config: Mapping[str, Any]) -> str:
    """ALTCHA_HMAC_KEY if set, else HMAC-SHA256(SECRET_KEY, "altcha") as hex (D16)."""
    explicit = config.get('ALTCHA_HMAC_KEY')
    if explicit:
        return explicit
    secret = config['SECRET_KEY']
    secret = secret.encode() if isinstance(secret, str) else secret
    return hmac.new(secret, b'altcha', hashlib.sha256).hexdigest()


def _to_epoch(moment: datetime) -> int:
    """Naive UTC datetime -> Unix seconds."""
    return int(moment.replace(tzinfo=timezone.utc).timestamp())


class AltchaProvider:
    name = 'altcha'

    def __init__(self, hmac_key: str, expire_seconds: int, max_number: int):
        self.hmac_key = hmac_key
        self.expire_seconds = expire_seconds
        self.max_number = max_number

    def challenge(self) -> dict:
        expires = clock.utcnow().replace(tzinfo=timezone.utc) + timedelta(seconds=self.expire_seconds)
        options = ChallengeOptionsV1(hmac_key=self.hmac_key, max_number=self.max_number,
                                     expires=expires)
        return create_challenge_v1(options).to_dict()

    def verify(self, payload: Optional[str]) -> bool:
        now = clock.utcnow()
        # Housekeeping first, so it also runs for bad payloads.
        RbCaptchaUsed.query.filter(RbCaptchaUsed.rbcap_expires_at < now).delete(
            synchronize_session=False)
        db.session.commit()

        if not payload or not isinstance(payload, str):
            return False
        try:
            valid, _error = verify_solution_v1(payload, self.hmac_key, check_expires=False)
            if not valid:
                return False
            decoded = _decode(payload)
            expires_at = _expiry(decoded)
        except (ValueError, TypeError, KeyError, AttributeError):
            return False
        if expires_at is None or expires_at <= _to_epoch(now):
            return False

        return self._remember(decoded['challenge'], datetime.fromtimestamp(
            expires_at, timezone.utc).replace(tzinfo=None))

    @staticmethod
    def _remember(challenge: str, expires_at: datetime) -> bool:
        """Store sha256(challenge); False if it was stored before (a replay)."""
        digest = hashlib.sha256(challenge.encode()).hexdigest()
        try:
            with db.session.begin_nested():
                # Core insert, not session.add(): a replay must reach the database and
                # fail there, not collide with an object already in the identity map.
                db.session.execute(insert(RbCaptchaUsed).values(
                    rbcap_hash=digest, rbcap_expires_at=expires_at))
        except IntegrityError:
            # begin_nested() already rolled back its SAVEPOINT; the outer
            # transaction is intact (no session.rollback() here).
            return False
        db.session.commit()
        return True


def _decode(payload: str) -> dict:
    data = json.loads(base64.b64decode(payload, validate=True).decode())
    if not isinstance(data, dict) or not isinstance(data.get('challenge'), str):
        raise ValueError('not an ALTCHA payload')
    return data


def _expiry(decoded: dict) -> Optional[int]:
    """Unix expiry time carried in the (signed) salt, or None."""
    values = extract_params_v1(decoded).get('expires')
    return int(values[0]) if values else None


def get_captcha_provider() -> CaptchaProvider:
    """The provider selected by `CAPTCHA_PROVIDER` in the current app's config."""
    config = current_app.config
    if config.get('CAPTCHA_PROVIDER') == 'altcha':
        return AltchaProvider(
            hmac_key=altcha_hmac_key(config),
            expire_seconds=config['ALTCHA_EXPIRE_SECONDS'],
            max_number=config['ALTCHA_MAX_NUMBER'],
        )
    return NoneProvider()
