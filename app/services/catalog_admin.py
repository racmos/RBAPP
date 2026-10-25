"""Catalog admin reads and writes (F13-b): sets, cards, image upload, use checks.

Pure queries and row mutations; the views commit once, together with the
audit row (`app/services/audit.py`), so a rolled-back change leaves no trace.
"""
import os
import re

from sqlalchemy import func, or_, select

from app import db
from app.models.card import RbCard
from app.models.collection import RbCollection
from app.models.deck import RbDeck
from app.models.set import RbSet
from app.services.card_images import card_image_url


def _nat(value: str):
    """Natural sort key: digit runs compare as numbers (`2` < `10` < `10a`)."""
    return tuple(int(part) if part.isdigit() else part.lower()
                 for part in re.split(r'(\\d+)', value or ''))


def set_item(rs: RbSet, card_count: int = 0) -> dict:
    """The S2 set payload."""
    return {'id': rs.rbset_id, 'name': rs.rbset_name,
            'release_date': rs.rbset_outdat.isoformat() if rs.rbset_outdat else None,
            'card_count': card_count, 'declared_count': rs.rbset_ncard}


def list_sets() -> list[dict]:
    """Every set with its card count, one query (S2): no date first, then date desc, then id."""
    rows = (db.session.query(RbSet, func.count(RbCard.rbcar_id))
            .outerjoin(RbCard, RbCard.rbcar_rbset_id == RbSet.rbset_id)
            .group_by(RbSet.rbset_id).all())
    # `sorted` is stable: pre-sort by id, so ties keep id order.
    dated = [r for r in rows if r[0].rbset_outdat is not None]
    dated = sorted(sorted(dated, key=lambda row: row[0].rbset_id),
                   key=lambda row: row[0].rbset_outdat, reverse=True)
    undated = sorted([r for r in rows if r[0].rbset_outdat is None],
                     key=lambda row: row[0].rbset_id)
    return [set_item(rs, count) for rs, count in undated + dated]


def set_card_count(set_id: str) -> int:
    """How many cards the set has (S4, S5)."""
    return RbCard.query.filter_by(rbcar_rbset_id=set_id).count()


def apply_set_patch(rs: RbSet, data) -> dict:
    """Apply name/date/count from an `AdminSetPatch`; return `{field: [old, new]}`."""
    changes = {}
    if data.name is not None and data.name != rs.rbset_name:
        changes['name'] = [rs.rbset_name, data.name]
        rs.rbset_name = data.name
    old_date = rs.rbset_outdat.isoformat() if rs.rbset_outdat else None
    if data.release_date is not None:
        new_date = data.release_date.isoformat()
        if new_date != old_date:
            changes['release_date'] = [old_date, new_date]
            rs.rbset_outdat = data.release_date
    if data.declared_count is not None and data.declared_count != rs.rbset_ncard:
        changes['declared_count'] = [rs.rbset_ncard, data.declared_count]
        rs.rbset_ncard = data.declared_count
    return changes


def card_item(card: RbCard) -> dict:
    """The S6 `AdminCard` payload: raw column values, key, M-d image URLs."""
    return {'set_id': card.rbcar_rbset_id, 'card_id': card.rbcar_id,
            'key': f'{card.rbcar_rbset_id}-{card.rbcar_id}',
            'name': card.rbcar_name, 'domain': card.rbcar_domain,
            'type': card.rbcar_type, 'tags': card.rbcar_tags,
            'energy': card.rbcar_energy, 'power': card.rbcar_power,
            'might': card.rbcar_might, 'ability': card.rbcar_ability,
            'rarity': card.rbcar_rarity, 'artist': card.rbcar_artist,
            'image': card.image,
            'image_url': card_image_url(card.image, card.rbcar_rbset_id),
            'image_src': card.image_src}


def list_cards(params) -> tuple[list[dict], int]:
    """Filtered cards and the total (S6): two bounded queries, natural sort in Python."""
    query = RbCard.query
    if params.set:
        query = query.filter(RbCard.rbcar_rbset_id.in_(params.set))
    if params.rarity:
        lowered = [value.lower() for value in params.rarity]
        query = query.filter(func.lower(RbCard.rbcar_rarity).in_(lowered))
    if params.type:
        query = query.filter(RbCard.rbcar_type.ilike(f'%{params.type}%'))
    if params.domain:
        query = query.filter(RbCard.rbcar_domain.ilike(f'%{params.domain}%'))
    if params.missing_image:
        query = query.filter(or_(RbCard.image.is_(None), RbCard.image == ''))
    if params.q:
        like = f'%{params.q}%'
        clauses = [RbCard.rbcar_name.ilike(like),
                   func.lower(RbCard.rbcar_id) == params.q.lower()]
        if '-' in params.q:
            set_part, _, card_part = params.q.rpartition('-')
            if set_part and card_part:
                clauses.append((func.lower(RbCard.rbcar_rbset_id) == set_part.lower())
                               & (func.lower(RbCard.rbcar_id) == card_part.lower()))
        query = query.filter(or_(*clauses))
    total = db.session.scalar(
        select(func.count()).select_from(query.order_by(None).subquery()))
    cards = query.all()
    if params.sort == 'name':
        cards.sort(key=lambda c: ((c.rbcar_name or '').lower(), c.rbcar_rbset_id,
                                  _nat(c.rbcar_id)))
    else:
        cards.sort(key=lambda c: (c.rbcar_rbset_id, _nat(c.rbcar_id)))
    if params.dir == 'desc':
        cards.reverse()
    start = (params.page - 1) * params.per_page
    return [card_item(c) for c in cards[start:start + params.per_page]], total


def card_use_count(set_id: str, card_id: str) -> tuple[int, int]:
    """`(collection lines, decks)` referencing the card (S10).

    Decks store `{main: [{set, id, qty}], sideboard: [...]}` JSON (DeckCards);
    the scan reads each deck's JSON once and counts decks, not lines.
    """
    lines = (RbCollection.query
             .filter_by(rbcol_rbset_id=set_id, rbcol_rbcar_id=card_id).count())
    decks = 0
    for (blob,) in db.session.query(RbDeck.rbdck_cards).all():
        if not isinstance(blob, dict):
            continue
        found = any(
            isinstance(entry, dict) and entry.get('set') == set_id
            and entry.get('id') == card_id
            for group in ('main', 'sideboard')
            for entry in (blob.get(group) or []))
        decks += found
    return lines, decks


def detect_image_ext(head: bytes) -> str | None:
    """`png`/`jpg`/`webp` from the magic bytes (S9), else None."""
    if head[:4] == b'\x89PNG':
        return 'png'
    if head[:3] == b'\xff\xd8\xff':
        return 'jpg'
    if head[:4] == b'RIFF' and head[8:12] == b'WEBP':
        return 'webp'
    return None


def image_stem(card: RbCard) -> str:
    """The stem of the card's current image, else `<set lower>_<card>` (S9)."""
    if card.image:
        return os.path.splitext(os.path.basename(card.image))[0]
    return f'{card.rbcar_rbset_id.lower()}_{card.rbcar_id}'
