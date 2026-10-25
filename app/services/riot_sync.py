"""Riot sync engine (F13-c): diff, auto-apply vs approval, `riot_sync` job.

One run keeps the catalog in line with the official Riot gallery: it always
inserts new cards, and for stored cards it applies differences by itself
around a release (pre-release and the 14 days after) while differences found
in the `monthly` (or `none`) window wait in `rbcardchanges` for the admin
(F13-g). One DB transaction per set: a set that fails rolls back only itself.

`rbcar_banned` is never written here (D-F2-2, D-F13-10): new cards are
inserted with the column default `'N'`, and updates skip the field.
"""
import logging
import os
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from app import db
from app.jobs.registry import JobFailed
from app.models.audit import RbAdminAudit  # noqa: F401  (re-exported for tests)
from app.models.card import RbCard
from app.models.card_change import RbCardChange, SYNCED_FIELDS
from app.models.set import RbSet
from app.services import audit as audit_service
from app.services.card_images import card_image_path
from app.services.riot_scraper import (
    _download_image,
    _fetch_gallery_json,
    _get_session,
    _parse_card,
    GALLERY_URL,
)
from app.utils import clock

logger = logging.getLogger(__name__)

MADRID = ZoneInfo('Europe/Madrid')

ACTIVE_WINDOWS = ('pre_release', 'post_release')


class GalleryError(Exception):
    """The gallery page could not be fetched or parsed (message has no URL)."""


def fetch_gallery() -> dict:
    """One GET of the `en-us` gallery; parsed cards, set codes, unparsed count (S1)."""
    session = _get_session()
    try:
        items = _fetch_gallery_json(session)
    except Exception as error:
        raise GalleryError(f'gallery fetch failed: {error}') from None
    cards, unparsed, codes = [], 0, []
    for raw in items:
        parsed = _parse_card(raw)
        if parsed is None:
            unparsed += 1
            continue
        cards.append(parsed)
        if parsed['rbcar_rbset_id'] not in codes:
            codes.append(parsed['rbcar_rbset_id'])
    return {'cards': cards, 'set_codes': sorted(codes), 'unparsed': unparsed}


def today_madrid(now: datetime) -> date:
    """The Europe/Madrid local date of `now` (naive datetimes read as UTC)."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(MADRID).date()


def window_for(release_date: date | None, today: date) -> str:
    """Which sync window a set with `release_date` is in on `today` (S2, D-F13-19)."""
    if release_date is None:
        return 'monthly'
    before = (release_date - today).days
    if before > 21:
        return 'none'
    if before >= 1:
        return 'pre_release'
    if before >= -13:
        return 'post_release'
    return 'monthly'


def _as_text(value):
    if value is None:
        return None
    return value if isinstance(value, str) else str(value)


def _same(stored, gallery):
    """Stored vs gallery equality: numbers as ints, NULL and empty text as equal."""
    if stored is None or gallery is None:
        return (stored or '') == (gallery or '')
    return stored == gallery


def _error_message(error: BaseException) -> str:
    """`<ExceptionClass>: <first line>` (F13-R3, same shape as M-c)."""
    return f'{type(error).__name__}: {str(error).splitlines()[0] if str(error) else ""}'


def sync(set_codes: list[str] | None = None, trigger: str = 'manual',
         now: datetime | None = None, job_id: int | None = None) -> dict:
    """Run one sync over the gallery (S3-S7). Raises `JobFailed` on gallery failure."""
    moment = now or clock.utcnow()
    today = today_madrid(moment)
    try:
        gallery = fetch_gallery()
    except GalleryError as error:
        raise JobFailed(str(error)) from None

    known = {row[0] for row in db.session.query(RbSet.rbset_id).all()}
    wanted = list(set_codes) if set_codes is not None else list(gallery['set_codes'])
    unknown = [code for code in wanted
               if code not in known and code not in gallery['set_codes']]
    if unknown:
        raise JobFailed(f'riot_sync: unknown set(s): {", ".join(sorted(unknown))}')

    by_set: dict[str, list[dict]] = {}
    for card in gallery['cards']:
        by_set.setdefault(card['rbcar_rbset_id'], []).append(card)

    session = _get_session()
    result = {'trigger': trigger, 'today': today.isoformat(),
              'gallery': {'cards': len(gallery['cards']),
                          'unparsed': gallery['unparsed'],
                          'set_codes': gallery['set_codes']},
              'placeholder_sets': [], 'sets': []}
    for set_id in wanted:
        summary, created = _sync_set(set_id, by_set.get(set_id, []), today, session,
                                     trigger, job_id, moment)
        if created:
            result['placeholder_sets'].append(set_id)
        result['sets'].append(summary)
    db.session.commit()
    return result


def _empty_summary(set_id: str, window: str) -> dict:
    return {'set_id': set_id, 'window': window, 'inserted': 0, 'applied': 0,
            'proposed': 0, 'unchanged': 0, 'missing_from_gallery': 0,
            'images': {'downloaded': 0, 'existing': 0, 'failed': 0}, 'error': None}


def _sync_set(set_id: str, cards: list[dict], today: date, session,
              trigger: str, job_id: int | None, moment: datetime) -> tuple[dict, bool]:
    """Sync one set inside a savepoint; a failure rolls back only this set."""
    summary = _empty_summary(set_id, 'monthly')
    try:
        with db.session.begin_nested():
            created = _process_set(set_id, cards, today, session, summary,
                                   job_id, moment)
    except Exception as error:  # noqa: BLE001  (one set must not kill the run)
        logger.exception('Riot sync failed for set %s', set_id)
        summary['error'] = _error_message(error)
        db.session.rollback()
        return summary, False
    return summary, created


def _process_set(set_id, cards, today, session, summary, job_id, moment) -> bool:
    """Process one set; returns True when a placeholder set was created."""
    created = False
    rs = RbSet.query.get(set_id)
    if rs is None:
        rs = RbSet(rbset_id=set_id, rbset_name=set_id,
                   rbset_ncard=len(cards), rbset_outdat=None)
        db.session.add(rs)
        db.session.flush()
        created = True
        audit_service.record('set.create', 'set', set_id,
                             {'name': set_id, 'release_date': None},
                             actor=audit_service.SYSTEM)
    elif rs.rbset_ncard is None:
        rs.rbset_ncard = len(cards)
    window = window_for(rs.rbset_outdat, today)
    summary['window'] = window

    stored = {c.rbcar_id: c for c in
              RbCard.query.filter_by(rbcar_rbset_id=set_id).all()}
    seen = set()
    inserted_ids = []
    for parsed in cards:
        card_id = parsed['rbcar_id']
        seen.add(card_id)
        card = stored.get(card_id)
        if card is None:
            card = RbCard(rbcar_rbset_id=set_id, rbcar_id=card_id,
                          rbcar_banned='N')
            for field in SYNCED_FIELDS:
                setattr(card, _column(field), parsed[field])
            db.session.add(card)
            db.session.flush()
            if _fetch_image(session, card, summary):
                pass
            summary['inserted'] += 1
            inserted_ids.append(card_id)
        else:
            diff = _diff(card, parsed)
            if not diff:
                summary['unchanged'] += 1
                continue
            if window in ACTIVE_WINDOWS:
                _apply(card, diff, session, summary)
                summary['applied'] += 1
            else:
                summary['proposed'] += _propose(card, diff, job_id, moment)
    summary['missing_from_gallery'] = len(set(stored) - seen)
    if inserted_ids:
        audit_service.record('riot.insert', 'set', set_id, {'cards': inserted_ids},
                             actor=audit_service.SYSTEM)
    return created


def _fetch_image(session, card: RbCard, summary: dict) -> bool:
    """Download the card image when missing on disk; count the outcome."""
    if not card.image_url:
        return False
    try:
        dest = card_image_path(card.image, card.rbcar_rbset_id)
    except ValueError:
        summary['images']['failed'] += 1
        return False
    if os.path.exists(dest):
        summary['images']['existing'] += 1
        return True
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if _download_image(session, card.image_url, dest):
        summary['images']['downloaded'] += 1
        return True
    summary['images']['failed'] += 1
    return False


def _diff(card: RbCard, parsed: dict) -> dict:
    """`{field: [old, new]}` for every synced field that differs (S5)."""
    out = {}
    for field in SYNCED_FIELDS:
        old = getattr(card, _column(field))
        new = parsed[field]
        if _same(old, new):
            continue
        out[field] = [old, new]
    return out


def _apply(card: RbCard, diff: dict, session, summary: dict):
    """Apply every difference at once (S5); re-download a changed image (D-F13-8)."""
    for field, (_, new) in diff.items():
        setattr(card, _column(field), new)
    if 'image_url' in diff or 'image' in diff:
        try:
            dest = card_image_path(card.image, card.rbcar_rbset_id)
        except ValueError:
            summary['images']['failed'] += 1
        else:
            if os.path.exists(dest):
                summary['images']['existing'] += 1
            else:
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                if _download_image(session, card.image_url, dest):
                    summary['images']['downloaded'] += 1
                else:
                    summary['images']['failed'] += 1
    audit_service.record('riot.apply', 'card',
                         f'{card.rbcar_rbset_id}-{card.rbcar_id}',
                         {'fields': diff}, actor=audit_service.SYSTEM)


def _propose(card: RbCard, diff: dict, job_id: int | None, moment: datetime) -> int:
    """Create or refresh one `pending` row per field (S5, D-F13-7)."""
    count = 0
    for field, (old, new) in diff.items():
        existing = (RbCardChange.query
                    .filter_by(rbchg_rbset_id=card.rbcar_rbset_id,
                               rbchg_rbcar_id=card.rbcar_id,
                               rbchg_field=field, rbchg_status='pending')
                    .one_or_none())
        if existing is not None:
            existing.rbchg_new_value = _as_text(new)
            existing.rbchg_detected_at = moment
            existing.rbchg_job_id = job_id
            count += 1
            continue
        latest_rejected = (RbCardChange.query
                           .filter_by(rbchg_rbset_id=card.rbcar_rbset_id,
                                      rbchg_rbcar_id=card.rbcar_id,
                                      rbchg_field=field, rbchg_status='rejected')
                           .order_by(RbCardChange.rbchg_id.desc()).first())
        if latest_rejected is not None and latest_rejected.rbchg_new_value == _as_text(new):
            continue
        db.session.add(RbCardChange(
            rbchg_rbset_id=card.rbcar_rbset_id, rbchg_rbcar_id=card.rbcar_id,
            rbchg_field=field, rbchg_old_value=_as_text(old),
            rbchg_new_value=_as_text(new), rbchg_status='pending',
            rbchg_job_id=job_id, rbchg_detected_at=moment))
        count += 1
    return count


def _column(field: str) -> str:
    """Synced gallery key to the `RbCard` column (they share the name)."""
    return field


