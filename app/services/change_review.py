"""Review of proposed card changes (F13-e S3-S6).

Approving writes the proposed value onto the card (`riot_sync` itself never
writes outside its own run); rejecting only flips the row. A change applies
only when the card still holds the value seen at detection time (numbers as
ints, NULL and empty text as equal — the S5 comparison of F13-c).
"""
import os

from sqlalchemy import func, or_, select

from app import db
from app.models.card import RbCard
from app.models.card_change import RbCardChange as Change
from app.models.user import User
from app.services import audit as audit_service
from app.services.card_images import card_image_path
from app.services.riot_scraper import _download_image, _get_session
from app.utils import clock

NUMERIC_FIELDS = ('rbcar_energy', 'rbcar_power', 'rbcar_might')

__all__ = ['NUMERIC_FIELDS', 'Change', 'change_item', 'matches',
           'apply_change', 'reject_change', 'pending_counts', 'list_changes']


def _column(field: str) -> str:
    """Synced fields name the `RbCard` column directly."""
    return field


def matches(current, old_text: str | None, field: str) -> bool:
    """Whether the card still holds the value seen at detection time."""
    if field in NUMERIC_FIELDS:
        if current is None or old_text is None or old_text == '':
            return current is None and (old_text is None or old_text == '')
        try:
            return int(current) == int(old_text)
        except (TypeError, ValueError):
            return False
    return (current or '') == (old_text or '')


def _coerce(field: str, value: str | None):
    if value is None:
        return None
    if field in NUMERIC_FIELDS:
        return int(value)
    return value


def change_item(row: Change, card_name=None, image=None, image_url=None,
                decided_by=None) -> dict:
    """The S3 item, with the card name and image of today.

    `list_changes` passes the joined columns so one page costs no extra
    queries; single-item reads load them lazily instead."""
    if card_name is None and image is None:
        card = RbCard.query.filter_by(rbcar_rbset_id=row.rbchg_rbset_id,
                                      rbcar_id=row.rbchg_rbcar_id).one_or_none()
        card_name = card.rbcar_name if card else None
        image = card.image if card else None
        image_url = card.image_url if card else None
    if decided_by is None and row.rbchg_decided_by:
        user = db.session.get(User, row.rbchg_decided_by)
        decided_by = user.username if user else None
    from app.services.card_images import card_image_url
    return {'id': row.rbchg_id, 'set_id': row.rbchg_rbset_id, 'card_id': row.rbchg_rbcar_id,
            'card_name': card_name,
            'image_src': card_image_url(image, row.rbchg_rbset_id),
            'field': row.rbchg_field, 'old_value': row.rbchg_old_value,
            'new_value': row.rbchg_new_value, 'status': row.rbchg_status,
            'detected_at': row.rbchg_detected_at.isoformat() if row.rbchg_detected_at else None,
            'job_id': row.rbchg_job_id,
            'decided_at': row.rbchg_decided_at.isoformat() if row.rbchg_decided_at else None,
            'decided_by': decided_by}


def pending_counts() -> dict:
    """Global totals per status (S3 `meta.counts`)."""
    from sqlalchemy import func
    rows = db.session.query(Change.rbchg_status, func.count()).group_by(
        Change.rbchg_status).all()
    counts = {'pending': 0, 'approved': 0, 'rejected': 0}
    for status, total in rows:
        if status in counts:
            counts[status] = total
    return counts


def list_changes(status=None, set_id=None, field=None, q=None, page=1, per_page=50):
    """Filtered changes, newest first; returns `(items, total)`, two queries."""
    from sqlalchemy import func, or_
    query = Change.query
    if status is not None:
        query = query.filter(Change.rbchg_status == status)
    if set_id:
        query = query.filter(Change.rbchg_rbset_id == set_id)
    if field:
        query = query.filter(Change.rbchg_field == field)
    if q:
        like = f'%{q}%'
        name_match = (db.session.query(RbCard.rbcar_id)
                      .filter(RbCard.rbcar_rbset_id == Change.rbchg_rbset_id,
                              RbCard.rbcar_id == Change.rbchg_rbcar_id,
                              RbCard.rbcar_name.ilike(like))
                      .correlate(Change).exists())
        query = query.filter(or_(
            func.lower(Change.rbchg_rbcar_id) == q.lower(), name_match))
    total = db.session.scalar(
        select(func.count()).select_from(query.order_by(None).subquery())) or 0
    rows = (query.with_entities(Change, RbCard.rbcar_name, RbCard.image,
                                RbCard.image_url, User.username)
            .outerjoin(RbCard, (RbCard.rbcar_rbset_id == Change.rbchg_rbset_id)
                       & (RbCard.rbcar_id == Change.rbchg_rbcar_id))
            .outerjoin(User, User.id == Change.rbchg_decided_by)
            .order_by(Change.rbchg_detected_at.desc(), Change.rbchg_id.desc())
            .offset((page - 1) * per_page).limit(per_page).all())
    return [change_item(row, name, image, image_url, username)
            for row, name, image, image_url, username in rows], total


def apply_change(change: Change, actor) -> list[str]:
    """Apply one pending, decided-now change; returns warnings (S4).

    Raises `StaleChange` when the card no longer holds `old_value` and
    `DecidedChange` when the row is not pending. The caller commits.
    """
    if change.rbchg_status != 'pending':
        raise DecidedChange(change)
    card = RbCard.query.filter_by(rbcar_rbset_id=change.rbchg_rbset_id,
                                  rbcar_id=change.rbchg_rbcar_id).one_or_none()
    current = getattr(card, change.rbchg_field) if card is not None else None
    if not matches(current, change.rbchg_old_value, change.rbchg_field):
        raise StaleChange(change)
    if card is None:  # the card is gone: approving removes the proposal
        change.rbchg_status = 'approved'
    else:
        setattr(card, change.rbchg_field, _coerce(change.rbchg_field, change.rbchg_new_value))
    change.rbchg_status = 'approved'
    change.rbchg_decided_at = clock.utcnow()
    change.rbchg_decided_by = actor.id if actor is not None else None
    warnings = []
    if change.rbchg_field == 'image_url' and card is not None:
        if not _download_for(card):
            warnings.append('image_download_failed')
    audit_service.record('riot.change_approve', 'card',
                         f'{change.rbchg_rbset_id}-{change.rbchg_rbcar_id}',
                         {'card': f'{change.rbchg_rbset_id}-{change.rbchg_rbcar_id}',
                          'field': change.rbchg_field,
                          'old': change.rbchg_old_value, 'new': change.rbchg_new_value},
                         actor=actor)
    return warnings


def reject_change(change: Change, actor) -> None:
    """Reject one pending change; the card is untouched (S5). The caller commits."""
    if change.rbchg_status != 'pending':
        raise DecidedChange(change)
    change.rbchg_status = 'rejected'
    change.rbchg_decided_at = clock.utcnow()
    change.rbchg_decided_by = actor.id if actor is not None else None
    audit_service.record('riot.change_reject', 'card',
                         f'{change.rbchg_rbset_id}-{change.rbchg_rbcar_id}',
                         {'card': f'{change.rbchg_rbset_id}-{change.rbchg_rbcar_id}',
                          'field': change.rbchg_field}, actor=actor)


def _download_for(card: RbCard) -> bool:
    """Download the card's current `image_url` over its file (D-F13-8)."""
    if not card.image_url:
        return False
    name = card.image or os.path.basename(card.image_url.split('?')[0]) or \
        f'{card.rbcar_rbset_id.lower()}_{card.rbcar_id}.png'
    try:
        dest = card_image_path(name, card.rbcar_rbset_id)
    except ValueError:
        return False
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.exists(dest):
        return True
    return bool(_download_image(_get_session(), card.image_url, dest))


class DecidedChange(Exception):
    """The row is not pending any more."""


class StaleChange(Exception):
    """The card no longer holds the detected old value."""
