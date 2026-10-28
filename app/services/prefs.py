"""Interface preferences of an account (PREF-3, PREF-4, D7).

`get_prefs` never writes; `update_prefs` creates the row on the first write.
Both return the public keys, `None` meaning Auto.
"""
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import RbUserPrefs
from app.schemas.prefs_domain import PREF_KEYS
from app.utils import clock

__all__ = ['PREF_KEYS', 'get_prefs', 'update_prefs']


def _column(key: str) -> str:
    return f'rbprf_{key}'


def _as_dict(row: RbUserPrefs | None) -> dict:
    """The public keys of `row`; all `None` when the user has no row."""
    return {key: getattr(row, _column(key)) if row is not None else None
            for key in PREF_KEYS}


def get_prefs(user_id: int) -> dict:
    """The user's preferences. A user without a row gets all `None`s and nothing is inserted."""
    return _as_dict(db.session.get(RbUserPrefs, user_id))


def _apply(row: RbUserPrefs, changes: dict) -> None:
    for key, value in changes.items():
        setattr(row, _column(key), value)
    row.rbprf_updated_at = clock.utcnow()


def update_prefs(user_id: int, changes: dict) -> dict:
    """Apply `changes` (only the keys present; `None` resets to Auto) and return all of them.

    Keys that are not preferences are dropped, never stored. An empty change
    writes nothing, not even a row. The row is created on the first write; if
    another request created it between our SELECT and our INSERT, the INSERT
    fails on the primary key and is retried once as an UPDATE (D7).
    """
    changes = {key: changes[key] for key in PREF_KEYS if key in changes}
    row = db.session.get(RbUserPrefs, user_id)
    if not changes:
        return _as_dict(row)

    if row is not None:
        _apply(row, changes)
        db.session.commit()
        return _as_dict(row)

    row = RbUserPrefs(rbprf_user_id=user_id)
    _apply(row, changes)
    db.session.add(row)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        row = db.session.get(RbUserPrefs, user_id)
        if row is None:                      # not a lost race: something else is wrong
            raise
        _apply(row, changes)
        db.session.commit()
    return _as_dict(row)
