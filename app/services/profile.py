"""The signed-in user's private profile and security summary (F9-b S6-S8).

The profile (`rbuserprofile`) is private (D-F9-3/12): display name, bio, country, city and the
avatar (F9-c: `avatar_url` from `app.services.avatars`, the versioned URL or None). Reading
never creates a row; the first `update_profile` (or avatar upload) does. Times use the F9-a format (`sessions._iso`).
"""
from __future__ import annotations

from typing import Optional

from app import db
from app.models import RbUserProfile
from app.security import reauth_until
from app.services import sessions
from app.services.avatars import profile_avatar_url
from app.utils import clock

_LOOKUP = object()
PROFILE_FIELDS = ('display_name', 'bio', 'country', 'city')
# What `security.mfa` says until F9-d (TOTP) fills it.
NO_MFA = {'available': False, 'enabled': False, 'pending': False, 'recovery_codes_left': 0}


def get_profile(user_id: int) -> Optional[RbUserProfile]:
    """The profile row of `user_id`, or None (never creates one)."""
    return db.session.get(RbUserProfile, user_id)


def user_payload(user, row=_LOOKUP) -> dict:
    """The public fields of an account (S6): never the hash. `email` may be None;
    `display_name` comes from the profile; `avatar_url` is the versioned avatar URL or None
    (F9-c S8). Pass the profile
    `row` (or None) when it is already known, to save the lookup."""
    if row is _LOOKUP:
        row = get_profile(user.id)
    return {'id': user.id, 'username': user.username, 'email': user.email,
            'is_admin': bool(user.is_admin),
            'display_name': row.rbupf_display_name if row is not None else None,
            'avatar_url': profile_avatar_url(row)}


def profile_payload(row: Optional[RbUserProfile]) -> dict:
    """The `profile` object of `GET /me`; every key None without a row."""
    if row is None:
        return {**dict.fromkeys(PROFILE_FIELDS), 'avatar_url': None, 'updated_at': None}
    return {'display_name': row.rbupf_display_name, 'bio': row.rbupf_bio,
            'country': row.rbupf_country, 'city': row.rbupf_city,
            'avatar_url': profile_avatar_url(row),
            'updated_at': sessions._iso(row.rbupf_updated_at)}


def security_summary(user) -> dict:
    """The `security` object of `GET /me` (S7). `mfa`, `api_key` and `connections` keep these
    values until F9-d, F9-h and F9-f fill them."""
    return {
        'has_password': user.has_password,
        'password_changed_at': sessions._iso(user.password_changed_at),
        'member_since': sessions._iso(user.created_at),
        'mfa': dict(NO_MFA),
        'sessions_active': sessions.count_active(user.id),
        'api_key': None,
        'connections': [],
        'reauth_until': sessions._iso(reauth_until(sessions.current())),
    }


def me_payload(user) -> dict:
    """The body of `GET /me` and `PATCH /me`: `{user, profile, security}`."""
    row = get_profile(user.id)
    return {'user': user_payload(user, row), 'profile': profile_payload(row),
            'security': security_summary(user)}


def update_profile(user_id: int, changes: dict) -> RbUserProfile:
    """Apply validated `changes` (only the keys that were sent; None = cleared), stamp
    `updated_at` and commit. The first call creates the row."""
    row = get_profile(user_id)
    if row is None:
        row = RbUserProfile(rbupf_user_id=user_id)
        db.session.add(row)
    for field in PROFILE_FIELDS:
        if field in changes:
            setattr(row, f'rbupf_{field}', changes[field])
    row.rbupf_updated_at = clock.utcnow()
    db.session.commit()
    return row
