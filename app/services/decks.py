"""Decks v2 of one user (F5-d): CRUD, content save with hard limits, versions, diff.

Every function takes the signed-in user and only ever sees that user's decks: another user's
deck or an unknown id raises `DeckNotFound` (the API answers 404, D-F5-9). Rules come from
the engine (`app/services/deck_rules.py`); legality, domains, counts and value are computed on
read and never stored (bans change over time).

Versions (D-F5-3): the head's current version is the draft. `save_content` rewrites it in
place (autosave); `snapshot` and `restore` add a new version with the next seq, which becomes
the current one, so every older version stays as it was.

Value (EUR): the market price of each printing (`price_summaries`, non-foil chain) times its
copies over legend, champion, main, runes, battlefields and sideboard; the workbench never
counts (product.md). `value_unpriced` counts the copies without a price (cards missing from
the catalog included).
"""
import re
import unicodedata
from copy import deepcopy

import sqlalchemy as sa
from sqlalchemy import tuple_
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import RbCard, RbCollection, RbDeckHead, RbDeckVersion, RbSet
from app.schemas.deck_content import empty_content
from app.schemas.game_domain import GAME_MODES
from app.services import bans as bans_service
from app.services import catalog, deck_rules, deck_text
from app.services.card_detail import _card_mini
from app.services.deck_migration import catalog_card
from app.services.pricing import price_summaries
from app.utils import clock

SLOT_ZONES = ('legend', 'champion')
LINE_ZONES = ('main', 'runes', 'sideboard', 'workbench')
# Content v2 keys in contract order (F5-R6).
CONTENT_ZONES = ('legend', 'champion', 'main', 'runes', 'battlefields', 'sideboard', 'workbench')
COUNT_ZONES = ('main', 'runes', 'battlefields', 'sideboard', 'workbench')
VALUE_ZONES = ('legend', 'champion', 'main', 'runes', 'battlefields', 'sideboard')


class DeckNotFound(Exception):
    """No deck with that id belongs to the user."""


class VersionNotFound(Exception):
    """The deck has no version with that seq."""


class DuplicateName(Exception):
    """The user already has a deck with that name."""


class UnknownCards(Exception):
    """Cards of the content are not in the catalog; `args[0]` is `[(field, set, id)]`."""


class HardLimitExceeded(Exception):
    """The content breaks hard limits (F5-R9); `args[0]` is `hard_limit_violations`."""


class FormatUnknown(Exception):
    """The import or export format is not one of `deck_text.FORMATS` (F5-e)."""


IMPORTED_NAME = 'Imported deck'
NAME_MAX = 80


# --- content helpers -------------------------------------------------------------------------

def _refs(content):
    """`(zone, field, ref, qty)` for every card of `content`, in content order."""
    for zone in CONTENT_ZONES:
        value = content.get(zone)
        if zone in SLOT_ZONES:
            if value:
                yield zone, zone, value, 1
            continue
        for index, item in enumerate(value or []):
            yield zone, f'{zone}.{index}', item, item.get('qty', 1) if zone != 'battlefields' else 1


def _key(ref):
    return (ref['set'], ref['id'])


def normal_content(content):
    """Stored content with the contract key order (JSONB does not keep it)."""
    content = content or {}
    out = {'v': 2}
    for zone in CONTENT_ZONES:
        value = content.get(zone)
        if zone in SLOT_ZONES:
            out[zone] = {'set': value['set'], 'id': value['id']} if value else None
        elif zone == 'battlefields':
            out[zone] = [{'set': item['set'], 'id': item['id']} for item in value or []]
        else:
            out[zone] = [{'set': item['set'], 'id': item['id'], 'qty': item['qty']}
                         for item in value or []]
    return out


def _iso(moment):
    return moment.strftime('%Y-%m-%dT%H:%M:%SZ') if moment is not None else None


# --- catalog of one request ------------------------------------------------------------------

class _Catalog:
    """The catalog, bans, prices and owned copies one response needs, in bounded queries:
    cards, sets, bans, then (for the cards asked for) prices (two) and the user's copies."""

    def __init__(self, user):
        rows = db.session.query(RbCard).all()
        self.rows = {(c.rbcar_rbset_id, c.rbcar_id): c for c in rows}
        self.rules = {key: catalog_card(c) for key, c in self.rows.items()}
        self.base_keys = catalog.base_printing_keys(
            rows, catalog.set_order(db.session.query(RbSet).all()))
        self.bans = {key: list(modes) for key, modes in bans_service.ban_map().items()}
        self.username = user.username
        self.prices, self.owned = {}, {}

    def load(self, contents):
        """Prices and owned copies of every known card of `contents`."""
        keys = sorted({_key(ref) for content in contents for _z, _f, ref, _q in _refs(content)
                       if _key(ref) in self.rows} - set(self.prices))
        if not keys:
            return
        self.prices.update(price_summaries(
            (s, i, self.rows[(s, i)].rbcar_rarity, _foilable(self.rows[(s, i)]))
            for s, i in keys))
        for key in keys:
            self.prices.setdefault(key, None)
        rows = db.session.query(RbCollection.rbcol_rbset_id, RbCollection.rbcol_rbcar_id,
                                RbCollection.rbcol_quantity).filter(
            RbCollection.rbcol_user == self.username,
            tuple_(RbCollection.rbcol_rbset_id, RbCollection.rbcol_rbcar_id).in_(keys))
        for set_id, card_id, qty in rows:
            self.owned[(set_id, card_id)] = self.owned.get((set_id, card_id), 0) + (qty or 0)

    def market(self, key):
        return (self.prices.get(key) or {}).get('market')

    def card(self, key):
        """The `DeckCard` of a known printing: `CardMini` plus its `tags`."""
        row = self.rows[key]
        out = _card_mini(row, market=self.market(key), owned_total=self.owned.get(key, 0),
                         is_base=key in self.base_keys)
        out['tags'] = catalog.parse_tags(row.rbcar_tags)
        return out

    def cards(self, refs):
        out = {}
        for ref in refs:
            key = _key(ref)
            if key in self.rows and f'{key[0]}-{key[1]}' not in out:
                out[f'{key[0]}-{key[1]}'] = self.card(key)
        return out

    def known(self, content):
        """`(content without the cards missing from the catalog, [{zone, set, id}] of them)`."""
        clean, unknown = deepcopy(content), []
        for zone in CONTENT_ZONES:
            if zone in SLOT_ZONES:
                if clean[zone] and _key(clean[zone]) not in self.rows:
                    unknown.append({'zone': zone, **clean[zone]})
                    clean[zone] = None
                continue
            kept = []
            for item in clean[zone]:
                if _key(item) in self.rows:
                    kept.append(item)
                else:
                    unknown.append({'zone': zone, 'set': item['set'], 'id': item['id']})
            clean[zone] = kept
        return clean, unknown


def _foilable(row):
    parsed_type, _ = catalog.parse_type(row.rbcar_type)
    return catalog.is_foilable(parsed_type, row.rbcar_rarity)


# --- summaries -------------------------------------------------------------------------------

def _counts(content):
    return {zone: (len(content[zone]) if zone == 'battlefields'
                   else sum(item['qty'] for item in content[zone])) for zone in COUNT_ZONES}


def _value(content, cat):
    total, unpriced = 0.0, 0
    for zone, _field, ref, qty in _refs(content):
        if zone not in VALUE_ZONES:
            continue
        market = cat.market(_key(ref)) if _key(ref) in cat.rows else None
        if market is None:
            unpriced += qty
        else:
            total += market * qty
    return round(total, 2), unpriced


def _legality(clean, cat):
    return {mode: deck_rules.validate(clean, cat.rules, cat.bans, mode) for mode in GAME_MODES}


def _analysis(content, cat):
    """`(unknown_cards, domains, counts, value, value_unpriced, legality)` of a content."""
    clean, unknown = cat.known(content)
    value, unpriced = _value(content, cat)
    return {'unknown_cards': unknown, 'domains': deck_rules.deck_domains(clean, cat.rules),
            'counts': _counts(content), 'value': value, 'value_unpriced': unpriced,
            'legality': _legality(clean, cat)}


def head_item(head):
    return {'id': head.rbdkh_id, 'name': head.rbdkh_name, 'mode': head.rbdkh_mode,
            'visibility': head.rbdkh_visibility, 'created_at': _iso(head.rbdkh_created_at),
            'updated_at': _iso(head.rbdkh_updated_at)}


def _detail(head, version, cat):
    content = normal_content(version.rbdkv_content if version else None)
    cat.load([content])
    out = head_item(head)
    out.update(current_seq=version.rbdkv_seq if version else None, content=content,
               cards=cat.cards(ref for _z, _f, ref, _q in _refs(content)))
    out.update(_analysis(content, cat))
    return out


def _version_item(version, head):
    return {'seq': version.rbdkv_seq, 'note': version.rbdkv_note,
            'created_at': _iso(version.rbdkv_created_at),
            'is_current': version.rbdkv_id == head.rbdkh_current_version_id}


def _version_detail(version, head, cat):
    content = normal_content(version.rbdkv_content)
    cat.load([content])
    out = _version_item(version, head)
    out.update(content=content, cards=cat.cards(ref for _z, _f, ref, _q in _refs(content)))
    out.update(_analysis(content, cat))
    return out


# --- lookups ---------------------------------------------------------------------------------

def _head(user, deck_id, lock=False):
    query = sa.select(RbDeckHead).where(RbDeckHead.rbdkh_id == deck_id,
                                        RbDeckHead.rbdkh_user_id == user.id)
    if lock:
        query = query.with_for_update()
    head = db.session.execute(query).scalar_one_or_none()
    if head is None:
        raise DeckNotFound(deck_id)
    return head


def _current(head):
    version = (db.session.get(RbDeckVersion, head.rbdkh_current_version_id)
               if head.rbdkh_current_version_id is not None else None)
    if version is None or version.rbdkv_deck_id != head.rbdkh_id:
        version = (RbDeckVersion.query.filter_by(rbdkv_deck_id=head.rbdkh_id)
                   .order_by(RbDeckVersion.rbdkv_seq.desc()).first())
    return version


def _version(head, seq):
    version = RbDeckVersion.query.filter_by(rbdkv_deck_id=head.rbdkh_id, rbdkv_seq=seq).first()
    if version is None:
        raise VersionNotFound(seq)
    return version


def _name_taken(user, name, deck_id=None):
    query = sa.select(RbDeckHead.rbdkh_id).where(RbDeckHead.rbdkh_user_id == user.id,
                                                 RbDeckHead.rbdkh_name == name)
    if deck_id is not None:
        query = query.where(RbDeckHead.rbdkh_id != deck_id)
    return db.session.execute(query).first() is not None


def _commit():
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise DuplicateName() from exc


# --- reads -----------------------------------------------------------------------------------

def list_decks(user):
    """The user's decks, newest change first, each with its summary (bounded queries)."""
    heads = (RbDeckHead.query.filter_by(rbdkh_user_id=user.id)
             .order_by(RbDeckHead.rbdkh_updated_at.desc(), RbDeckHead.rbdkh_id.desc()).all())
    if not heads:
        return []
    ids = [h.rbdkh_current_version_id for h in heads if h.rbdkh_current_version_id is not None]
    by_id = {v.rbdkv_id: v for v in RbDeckVersion.query.filter(RbDeckVersion.rbdkv_id.in_(ids))}
    contents = [normal_content(getattr(by_id.get(h.rbdkh_current_version_id), 'rbdkv_content',
                                       None)) for h in heads]
    cat = _Catalog(user)
    cat.load(contents)
    items = []
    for head, content in zip(heads, contents):
        analysis = _analysis(content, cat)
        item = head_item(head)
        item.update(
            legend=cat.card(_key(content['legend']))
            if content['legend'] and _key(content['legend']) in cat.rows else None,
            champion=cat.card(_key(content['champion']))
            if content['champion'] and _key(content['champion']) in cat.rows else None,
            domains=analysis['domains'], counts=analysis['counts'], value=analysis['value'],
            value_unpriced=analysis['value_unpriced'],
            legal={mode: result['legal'] for mode, result in analysis['legality'].items()},
            issues={mode: list(dict.fromkeys(issue['code'] for issue in result['issues']))
                    for mode, result in analysis['legality'].items()})
        items.append(item)
    return items


def get_deck(user, deck_id):
    head = _head(user, deck_id)
    return _detail(head, _current(head), _Catalog(user))


def list_versions(user, deck_id):
    """The deck's versions, newest first."""
    head = _head(user, deck_id)
    return [_version_item(v, head) for v in RbDeckVersion.query.filter_by(
        rbdkv_deck_id=head.rbdkh_id).order_by(RbDeckVersion.rbdkv_seq.desc())]


def get_version(user, deck_id, seq):
    head = _head(user, deck_id)
    return _version_detail(_version(head, seq), head, _Catalog(user))


# --- writes ----------------------------------------------------------------------------------

def create_deck(user, name, mode):
    """A new private deck with an empty version 1 (its current version)."""
    if _name_taken(user, name):
        raise DuplicateName()
    return _new_deck(user, name, mode, empty_content(), _Catalog(user))


def _new_deck(user, name, mode, content, cat):
    now = clock.utcnow()
    head = RbDeckHead(rbdkh_user_id=user.id, rbdkh_name=name, rbdkh_mode=mode,
                      rbdkh_visibility='private', rbdkh_created_at=now, rbdkh_updated_at=now)
    db.session.add(head)
    try:
        db.session.flush()
    except IntegrityError as exc:
        db.session.rollback()
        raise DuplicateName() from exc
    version = RbDeckVersion(rbdkv_deck_id=head.rbdkh_id, rbdkv_seq=1,
                            rbdkv_content=content, rbdkv_created_at=now)
    db.session.add(version)
    db.session.flush()
    head.rbdkh_current_version_id = version.rbdkv_id
    _commit()
    return _detail(head, version, cat)


def update_deck(user, deck_id, changes):
    """Set the sent `name` / `mode` / `visibility` (the share link is F5-g)."""
    head = _head(user, deck_id, lock=True)
    if 'name' in changes and _name_taken(user, changes['name'], head.rbdkh_id):
        raise DuplicateName()
    for name, column in (('name', 'rbdkh_name'), ('mode', 'rbdkh_mode'),
                         ('visibility', 'rbdkh_visibility')):
        if name in changes:
            setattr(head, column, changes[name])
    head.rbdkh_updated_at = clock.utcnow()
    _commit()
    return _detail(head, _current(head), _Catalog(user))


def delete_deck(user, deck_id):
    """Delete the deck and every version; returns the deleted head."""
    head = _head(user, deck_id, lock=True)
    item = head_item(head)
    RbDeckVersion.query.filter_by(rbdkv_deck_id=head.rbdkh_id).delete()
    db.session.delete(head)
    db.session.commit()
    return item


def save_content(user, deck_id, content):
    """Replace the current version's content (autosave, no new version).

    Raises `UnknownCards` when a card is not in the catalog and `HardLimitExceeded` when the
    content breaks a hard limit; soft rules never block (they are legality issues).
    """
    head = _head(user, deck_id, lock=True)
    cat = _Catalog(user)
    content = normal_content(content)
    unknown = [(f'content.{field}', ref['set'], ref['id'])
               for _zone, field, ref, _qty in _refs(content) if _key(ref) not in cat.rows]
    if unknown:
        raise UnknownCards(unknown)
    violations = deck_rules.hard_limit_violations(content, cat.rules)
    if violations:
        raise HardLimitExceeded(violations)
    version = _current(head)
    version.rbdkv_content = content
    head.rbdkh_current_version_id = version.rbdkv_id
    head.rbdkh_updated_at = clock.utcnow()
    db.session.commit()
    return _detail(head, version, cat)


def _add_version(user, head, content, note):
    seq = (db.session.query(sa.func.max(RbDeckVersion.rbdkv_seq))
           .filter(RbDeckVersion.rbdkv_deck_id == head.rbdkh_id).scalar() or 0) + 1
    now = clock.utcnow()
    version = RbDeckVersion(rbdkv_deck_id=head.rbdkh_id, rbdkv_seq=seq,
                            rbdkv_content=normal_content(content), rbdkv_note=note,
                            rbdkv_created_at=now)
    db.session.add(version)
    db.session.flush()
    head.rbdkh_current_version_id = version.rbdkv_id
    head.rbdkh_updated_at = now
    db.session.commit()
    return _version_detail(version, head, _Catalog(user))


def snapshot(user, deck_id, note=None):
    """A new version (next seq, current) holding a copy of the current content."""
    head = _head(user, deck_id, lock=True)
    current = _current(head)
    return _add_version(user, head, current.rbdkv_content if current else None, note)


def restore(user, deck_id, seq):
    """A new version (next seq, current) holding a copy of version `seq`."""
    head = _head(user, deck_id, lock=True)
    source = _version(head, seq)
    return _add_version(user, head, source.rbdkv_content, f'Restored from version {seq}.')


# --- text import / export (F5-e) -------------------------------------------------------------

def _parse_import(cat, text, fmt):
    if fmt not in deck_text.FORMATS:
        raise FormatUnknown(fmt)
    content, warnings, counts = deck_text.build_content(
        deck_text.parse_text(text), deck_text.Resolver(cat.rules, cat.base_keys), cat.rules)
    return normal_content(content), warnings, counts


def import_preview(user, text, fmt='auto'):
    """`{deck_preview, warnings, counts}` of a deck text; writes nothing. `deck_preview` is
    the content with its cards and analysis, as `get_deck` gives them."""
    cat = _Catalog(user)
    content, warnings, counts = _parse_import(cat, text, fmt)
    cat.load([content])
    deck = {'content': content, 'cards': cat.cards(ref for _z, _f, ref, _q in _refs(content))}
    deck.update(_analysis(content, cat))
    return {'deck_preview': deck, 'warnings': warnings, 'counts': counts}


def _free_name(user, name):
    """`name` (cut to NAME_MAX), or the first free `name (n)` from 2 on."""
    candidate, n = name[:NAME_MAX].rstrip(), 1
    while _name_taken(user, candidate):
        n += 1
        suffix = f' ({n})'
        candidate = name[:NAME_MAX - len(suffix)].rstrip() + suffix
    return candidate


def import_deck(user, text, fmt='auto', name=None, mode=GAME_MODES[0]):
    """A new private deck whose version 1 is the imported content, kept as read: hard limits
    are not refused here (they are `hard_limit` warnings and legality issues). The name is
    `name`, else the legend's text name, else IMPORTED_NAME; a taken name gets ` (n)`."""
    cat = _Catalog(user)
    content, warnings, _counts = _parse_import(cat, text, fmt)
    legend = content['legend']
    if not name and legend:
        name = deck_text.card_label(cat.rules[_key(legend)])
    out = _new_deck(user, _free_name(user, name or IMPORTED_NAME), mode, content, cat)
    out['warnings'] = warnings
    return out


def _slug(name):
    ascii_name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', ascii_name.lower()).strip('-') or 'deck'


def export_text(user, deck_id, fmt='text'):
    """`(filename, text)` of the deck's current version in the common text format."""
    if fmt != 'text':
        raise FormatUnknown(fmt)
    head = _head(user, deck_id)
    version = _current(head)
    content = normal_content(version.rbdkv_content if version else None)
    cat = _Catalog(user)
    return f'{_slug(head.rbdkh_name)}.txt', deck_text.format_text(content, cat.rules)


def diff(user, deck_id, a, b):
    """What changes from version `a` to version `b`, per zone (content order).

    Each zone has `added` (only in b), `removed` (only in a) and `changed` (both, other
    quantity) entries `{set, id, before, after}` (copies; 1 for legend, champion and each
    battlefield), ordered by card name (`name_sort_key`), then set and id. `cards` holds the
    `DeckCard` of every printing named in an entry.
    """
    head = _head(user, deck_id)
    old = normal_content(_version(head, a).rbdkv_content)
    new = normal_content(_version(head, b).rbdkv_content)
    cat = _Catalog(user)
    cat.load([old, new])

    def counts(content, zone):
        out = {}
        for item_zone, _field, ref, qty in _refs(content):
            if item_zone == zone:
                out[_key(ref)] = out.get(_key(ref), 0) + qty
        return out

    def order(key):
        name = cat.rows[key].rbcar_name if key in cat.rows else f'{key[0]}-{key[1]}'
        return (deck_rules.name_sort_key(name), key)

    zones, named = {}, []
    for zone in CONTENT_ZONES:
        before, after = counts(old, zone), counts(new, zone)
        entry = {'added': [], 'removed': [], 'changed': []}
        for key in sorted(set(before) | set(after), key=order):
            was, now = before.get(key, 0), after.get(key, 0)
            kind = 'added' if not was else 'removed' if not now else 'changed'
            if was != now:
                entry[kind].append({'set': key[0], 'id': key[1], 'before': was, 'after': now})
                named.append({'set': key[0], 'id': key[1]})
        zones[zone] = entry
    return {'a': a, 'b': b, 'zones': zones, 'cards': cat.cards(named)}
