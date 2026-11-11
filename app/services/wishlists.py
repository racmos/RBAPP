"""Wishlists of one user (F3-f-2): the lists and their lines, with the owned and price
indicators of each line (docs/requirements/F3/F3-f-wishlists-design.md).

Lists (A4): at most `MAX_LISTS` per user, names unique per user ignoring case, positions
1..n, exactly one default list once the user has any. The first `GET /wishlists` of a user
without lists creates the default list "Wishlist"; a list created by POST when the user has
none becomes the default. The default list cannot be unstarred (star another one) nor
deleted. Deleting another list deletes its lines.

Lines (A1, A2, A6): a target is a card name (`name_key`) plus a printing (set + number) or
none (any printing), plus a foil wish (`any`, `N`, `S`). Adding the same target to a list
adds the quantities (capped at 99); a foil copy, an alternate-art printing and a by-name
target are different lines. At most `MAX_LINES` lines per list; merging into an existing
line never counts as a new one.

Every function takes the signed-in user and only sees that user's lists: another user's
list or line, or an unknown id, raises `ListNotFound` / `LineNotFound` (the API answers 404).
Writes commit when they succeed and roll back when they raise. No Flask objects here.
"""
from decimal import ROUND_HALF_UP, Decimal

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import RbCard, RbCollection, RbSet, RbWishlist, RbWishlistLine
from app.services import catalog
from app.services.bans import name_key
from app.services.card_detail import _card_mini
from app.services.pricing import price_summaries
from app.utils import clock

MAX_LISTS = 20
MAX_LINES = 100
QTY_MAX = 99
DEFAULT_NAME = 'Wishlist'
CENT = Decimal('0.01')
UNSET = object()


class ListNotFound(Exception):
    """The wishlist does not exist or is not the user's."""


class LineNotFound(Exception):
    """The line does not exist, is not in that list, or the list is not the user's."""


class DuplicateName(Exception):
    """The user already has a list with this name (ignoring case)."""


class DuplicateLine(Exception):
    """Another line of the list already has this target (name, printing and foil)."""


class WishlistLimit(Exception):
    """Too many lists for the user (`scope='lists'`) or lines in a list (`scope='lines'`)."""

    def __init__(self, scope: str, maximum: int):
        super().__init__(f'at most {maximum} {scope}')
        self.scope = scope
        self.max = maximum


class DefaultRequired(Exception):
    """The default list cannot be unstarred: the way to change it is to star another."""


class DefaultList(Exception):
    """The default list cannot be deleted until another one is starred."""


class InvalidOrder(Exception):
    """The new order is not exactly the user's list ids, each once."""


class SameList(Exception):
    """A move or copy needs another list as the target."""


class UnknownCard(Exception):
    """The printing or the name is not in the catalog; `field` is `card_id` or `name`."""

    def __init__(self, field: str):
        super().__init__(field)
        self.field = field


class FoilNotAllowed(Exception):
    """A foil (`S`) wish for a card that has no foil version (no printing of a by-name
    target has one)."""


# --- helpers -------------------------------------------------------------------------------

def _iso(moment) -> str | None:
    return moment.strftime('%Y-%m-%dT%H:%M:%SZ') if moment is not None else None


def _money(value) -> Decimal | None:
    return None if value is None else Decimal(str(value)).quantize(CENT, ROUND_HALF_UP)


def _float(value) -> float | None:
    return None if value is None else float(value)


def _foilable(card: RbCard) -> bool:
    card_type, _ = catalog.parse_type(card.rbcar_type)
    return catalog.is_foilable(card_type, card.rbcar_rarity)


def _eq(column, value):
    return column.is_(None) if value is None else column == value


def _owned_list(user, list_id) -> RbWishlist:
    found = db.session.execute(sa.select(RbWishlist).where(
        RbWishlist.rbwls_id == list_id, RbWishlist.rbwls_user_id == user.id)).scalar()
    if found is None:
        raise ListNotFound(list_id)
    return found


def _owned_line(user, list_id, line_id) -> tuple[RbWishlist, RbWishlistLine]:
    wishlist = _owned_list(user, list_id)
    found = db.session.execute(sa.select(RbWishlistLine).where(
        RbWishlistLine.rbwsl_id == line_id,
        RbWishlistLine.rbwsl_list_id == wishlist.rbwls_id)).scalar()
    if found is None:
        raise LineNotFound(line_id)
    return wishlist, found


def _lists(user) -> list[RbWishlist]:
    return list(db.session.execute(sa.select(RbWishlist).where(
        RbWishlist.rbwls_user_id == user.id).order_by(RbWishlist.rbwls_position)).scalars())


def _name_taken(user, name: str, except_id=None) -> bool:
    query = sa.select(RbWishlist.rbwls_id).where(
        RbWishlist.rbwls_user_id == user.id,
        sa.func.lower(RbWishlist.rbwls_name) == name.lower())
    if except_id is not None:
        query = query.where(RbWishlist.rbwls_id != except_id)
    return db.session.execute(query.limit(1)).scalar() is not None


def _commit_name(user, name: str, except_id=None) -> None:
    """Commit; a unique violation caused by a name inserted meanwhile is a DuplicateName."""
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        if _name_taken(user, name, except_id):
            raise DuplicateName(name) from None
        raise


def _renumber(rows: list[RbWishlist]) -> None:
    """Give `rows` the positions 1..n in their order. Positions are unique per user and
    checked row by row, so every row first moves above all current positions (as
    `locations._renumber`)."""
    above = max([row.rbwls_position for row in rows] + [len(rows)])
    for index, row in enumerate(rows, 1):
        row.rbwls_position = above + index
    db.session.flush()
    now = clock.utcnow()
    for index, row in enumerate(rows, 1):
        if row.rbwls_position != index:
            row.rbwls_position = index
            row.rbwls_updated_at = now
    db.session.flush()


def _line_counts(list_ids) -> dict[int, int]:
    list_ids = list(list_ids)
    if not list_ids:
        return {}
    return dict(db.session.execute(
        sa.select(RbWishlistLine.rbwsl_list_id, sa.func.count())
        .where(RbWishlistLine.rbwsl_list_id.in_(list_ids))
        .group_by(RbWishlistLine.rbwsl_list_id)).all())


def _rollback_on_error(action):
    try:
        return action()
    except Exception:
        db.session.rollback()
        raise


# --- lists ---------------------------------------------------------------------------------

def list_item(wishlist: RbWishlist, line_count: int = 0) -> dict:
    """The API shape of a list (`WishlistSummary`)."""
    return {'id': wishlist.rbwls_id, 'name': wishlist.rbwls_name,
            'is_default': wishlist.rbwls_is_default, 'position': wishlist.rbwls_position,
            'line_count': line_count, 'created_at': _iso(wishlist.rbwls_created_at),
            'updated_at': _iso(wishlist.rbwls_updated_at)}


def ensure_default(user) -> list[RbWishlist]:
    """The user's lists in order; a user without lists first gets the default list
    "Wishlist" (A4). Race-safe: a concurrent first call hits the unique indexes, rolls back
    and reads what the other one created."""
    rows = _lists(user)
    if rows:
        return rows
    now = clock.utcnow()
    db.session.add(RbWishlist(rbwls_user_id=user.id, rbwls_name=DEFAULT_NAME,
                              rbwls_is_default=True, rbwls_position=1,
                              rbwls_created_at=now, rbwls_updated_at=now))
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
    return _lists(user)


def list_items(user) -> list[dict]:
    """Every list of the user as `list_item`, in order (creating the default list first
    when the user has none). Two SQL statements once the default list exists."""
    rows = ensure_default(user)
    counts = _line_counts(row.rbwls_id for row in rows)
    return [list_item(row, counts.get(row.rbwls_id, 0)) for row in rows]


def owned_item(user, list_id) -> dict:
    wishlist = _owned_list(user, list_id)
    return list_item(wishlist, _line_counts([wishlist.rbwls_id]).get(wishlist.rbwls_id, 0))


def create_list(user, name: str) -> RbWishlist:
    """A new list, last in the user's order; the user's first list is the default."""
    rows = _lists(user)
    if len(rows) >= MAX_LISTS:
        raise WishlistLimit('lists', MAX_LISTS)
    if _name_taken(user, name):
        raise DuplicateName(name)
    now = clock.utcnow()
    wishlist = RbWishlist(rbwls_user_id=user.id, rbwls_name=name, rbwls_is_default=not rows,
                          rbwls_position=max((row.rbwls_position for row in rows), default=0) + 1,
                          rbwls_created_at=now, rbwls_updated_at=now)
    db.session.add(wishlist)
    _commit_name(user, name)
    return wishlist


def update_list(user, list_id, *, name=UNSET, is_default=UNSET) -> RbWishlist:
    """Rename and/or star a list. Starring unstars the previous default in the same
    transaction; unstarring the default is refused (DefaultRequired)."""
    wishlist = _owned_list(user, list_id)
    if is_default is False and wishlist.rbwls_is_default:
        raise DefaultRequired(list_id)
    if name is not UNSET and _name_taken(user, name, wishlist.rbwls_id):
        raise DuplicateName(name)
    now = clock.utcnow()
    if name is not UNSET:
        wishlist.rbwls_name = name
    if is_default is True and not wishlist.rbwls_is_default:
        for row in db.session.execute(sa.select(RbWishlist).where(
                RbWishlist.rbwls_user_id == user.id, RbWishlist.rbwls_is_default)).scalars():
            row.rbwls_is_default = False
            row.rbwls_updated_at = now
        db.session.flush()                     # one default per user: unstar first
        wishlist.rbwls_is_default = True
    wishlist.rbwls_updated_at = now
    _rollback_on_error(lambda: _commit_name(user, wishlist.rbwls_name, wishlist.rbwls_id))
    return wishlist


def delete_list(user, list_id) -> tuple[dict, list[dict]]:
    """Delete a list that is not the default, with its lines; the order closes up. Returns
    the removed list (`list_item`) and its lines (`WishlistLine`), so they can be restored."""
    wishlist = _owned_list(user, list_id)
    if wishlist.rbwls_is_default:
        raise DefaultList(list_id)
    lines = list_lines(user, list_id)['items']
    item = list_item(wishlist, len(lines))

    def action():
        db.session.execute(sa.delete(RbWishlistLine).where(
            RbWishlistLine.rbwsl_list_id == wishlist.rbwls_id))
        db.session.delete(wishlist)
        db.session.flush()
        _renumber(_lists(user))
        db.session.commit()
    _rollback_on_error(action)
    return item, lines


def reorder_lists(user, list_ids) -> None:
    """Set the whole order: `list_ids` must be every list of the user, each once."""
    rows = {row.rbwls_id: row for row in _lists(user)}
    ids = list(list_ids)
    if not ids or len(ids) != len(set(ids)) or set(ids) != set(rows):
        raise InvalidOrder(ids)
    _rollback_on_error(lambda: (_renumber([rows[list_id] for list_id in ids]),
                                db.session.commit()))


# --- line targets --------------------------------------------------------------------------

def _cards_named(key: str) -> list[RbCard]:
    """The catalog printings whose `name_key` is `key` (names are compared in Python, the
    way every other `name_key` match is)."""
    rows = db.session.execute(sa.select(RbCard)).scalars()
    return [card for card in rows if name_key(card.rbcar_name) == key]


def _base_card(cards: list[RbCard]) -> RbCard:
    set_rank = catalog.set_order(db.session.query(RbSet).all())
    base = catalog.base_printing_keys(cards, set_rank)
    return next(card for card in cards if (card.rbcar_rbset_id, card.rbcar_id) in base)


def _target(set_id, card_id, name) -> tuple[str, str, list[RbCard]]:
    """`(name_key, name as shown, the printings the foil check reads)` of a new target."""
    if set_id is not None:
        card = db.session.get(RbCard, (set_id, card_id))
        if card is None:
            raise UnknownCard('card_id')
        return name_key(card.rbcar_name), card.rbcar_name, [card]
    key = name_key(name or '')
    cards = _cards_named(key) if key else []
    if not cards:
        raise UnknownCard('name')
    return key, _base_card(cards).rbcar_name, cards


def _line_cards(line: RbWishlistLine) -> list[RbCard]:
    """The printings an existing line stands for (its printing, or every printing of its
    name)."""
    if line.rbwsl_rbset_id is not None:
        card = db.session.get(RbCard, (line.rbwsl_rbset_id, line.rbwsl_rbcar_id))
        return [card] if card is not None else []
    return _cards_named(line.rbwsl_name_key)


def _check_foil(foil: str, cards: list[RbCard]) -> None:
    if foil == 'S' and not any(_foilable(card) for card in cards):
        raise FoilNotAllowed()


def _same_target(list_id, key, set_id, card_id, foil):
    return sa.select(RbWishlistLine).where(
        RbWishlistLine.rbwsl_list_id == list_id, RbWishlistLine.rbwsl_name_key == key,
        _eq(RbWishlistLine.rbwsl_rbset_id, set_id), _eq(RbWishlistLine.rbwsl_rbcar_id, card_id),
        RbWishlistLine.rbwsl_foil == foil)


def _line_total(list_id) -> int:
    return db.session.execute(sa.select(sa.func.count()).where(
        RbWishlistLine.rbwsl_list_id == list_id)).scalar_one()


# --- line writes ---------------------------------------------------------------------------

def add_line(user, list_id, *, set_id=None, card_id=None, name=None, foil='any', qty=1,
             max_price=None, note=None) -> tuple[dict, bool]:
    """Add a target to a list; `(WishlistLine, merged)`. The same target (name, printing,
    foil) adds the quantities, capped at 99, and a sent max price or note replaces the
    line's; a new line needs room (`MAX_LINES`)."""
    wishlist = _owned_list(user, list_id)
    key, shown, cards = _target(set_id, card_id, name)
    _check_foil(foil, cards)
    max_price = _money(max_price)
    now = clock.utcnow()

    def action():
        line = db.session.execute(
            _same_target(wishlist.rbwls_id, key, set_id, card_id, foil)).scalar()
        merged = line is not None
        if merged:
            line.rbwsl_qty = min(QTY_MAX, line.rbwsl_qty + qty)
            if max_price is not None:
                line.rbwsl_max_price = max_price
            if note is not None:
                line.rbwsl_note = note
            line.rbwsl_updated_at = now
        else:
            if _line_total(wishlist.rbwls_id) >= MAX_LINES:
                raise WishlistLimit('lines', MAX_LINES)
            line = RbWishlistLine(
                rbwsl_list_id=wishlist.rbwls_id, rbwsl_name_key=key, rbwsl_name=shown,
                rbwsl_rbset_id=set_id, rbwsl_rbcar_id=card_id, rbwsl_foil=foil, rbwsl_qty=qty,
                rbwsl_max_price=max_price, rbwsl_note=note, rbwsl_created_at=now,
                rbwsl_updated_at=now)
            db.session.add(line)
        wishlist.rbwls_updated_at = now
        db.session.commit()
        return line, merged
    line, merged = _rollback_on_error(action)
    return line_payloads(user, [line])[0], merged


def update_line(user, list_id, line_id, *, qty=UNSET, foil=UNSET, max_price=UNSET,
                note=UNSET) -> dict:
    """Change the sent fields of a line (`None` clears the max price or the note). A foil
    change that would give the target of another line of the list is a DuplicateLine."""
    wishlist, line = _owned_line(user, list_id, line_id)
    if foil is not UNSET and foil != line.rbwsl_foil:
        _check_foil(foil, _line_cards(line))
        if db.session.execute(_same_target(wishlist.rbwls_id, line.rbwsl_name_key,
                                           line.rbwsl_rbset_id, line.rbwsl_rbcar_id,
                                           foil)).scalar() is not None:
            raise DuplicateLine(line_id)
        line.rbwsl_foil = foil
    if qty is not UNSET:
        line.rbwsl_qty = qty
    if max_price is not UNSET:
        line.rbwsl_max_price = _money(max_price)
    if note is not UNSET:
        line.rbwsl_note = note
    now = clock.utcnow()
    line.rbwsl_updated_at = wishlist.rbwls_updated_at = now
    _rollback_on_error(db.session.commit)
    return line_payloads(user, [line])[0]


def delete_line(user, list_id, line_id) -> dict:
    """Delete a line; returns it as `WishlistLine` (posting it back restores it)."""
    wishlist, line = _owned_line(user, list_id, line_id)
    payload = line_payloads(user, [line])[0]

    def action():
        db.session.delete(line)
        wishlist.rbwls_updated_at = clock.utcnow()
        db.session.commit()
    _rollback_on_error(action)
    return payload


def _target_key(line: RbWishlistLine) -> tuple:
    return (line.rbwsl_name_key, line.rbwsl_rbset_id, line.rbwsl_rbcar_id, line.rbwsl_foil)


def move_lines(user, list_id, line_ids, to_list_id, mode: str) -> dict:
    """Move (`mode='move'`) or copy (`'copy'`) lines of a list to another list of the user,
    all or nothing. A line whose target the other list already has is merged into it
    (quantities add, capped at 99; the target line keeps its max price and note and takes
    the moved line's only where it has none); a merge into a line already at 99 adds nothing
    and counts as skipped. In a move the source line goes away in every case. The new lines
    must fit (`MAX_LINES`), else WishlistLimit and nothing changes. Returns `{moved, merged,
    skipped}`: lines created in the target, lines merged into one, lines skipped."""
    source = _owned_list(user, list_id)
    if to_list_id == source.rbwls_id:
        raise SameList(to_list_id)
    target = _owned_list(user, to_list_id)
    ids = list(dict.fromkeys(line_ids))
    rows = list(db.session.execute(sa.select(RbWishlistLine).where(
        RbWishlistLine.rbwsl_id.in_(ids), RbWishlistLine.rbwsl_list_id == source.rbwls_id)
        .order_by(RbWishlistLine.rbwsl_id)).scalars())
    if len(rows) != len(ids):
        raise LineNotFound(sorted(set(ids) - {row.rbwsl_id for row in rows}))
    present = {_target_key(row): row for row in db.session.execute(sa.select(
        RbWishlistLine).where(RbWishlistLine.rbwsl_list_id == target.rbwls_id)).scalars()}
    new = [row for row in rows if _target_key(row) not in present]
    if len(present) + len(new) > MAX_LINES:
        raise WishlistLimit('lines', MAX_LINES)

    counts = {'moved': 0, 'merged': 0, 'skipped': 0}
    now = clock.utcnow()

    def action():
        for row in rows:
            hit = present.get(_target_key(row))
            if hit is None:
                counts['moved'] += 1
                if mode == 'move':
                    row.rbwsl_list_id = target.rbwls_id
                    row.rbwsl_updated_at = now
                else:
                    db.session.add(RbWishlistLine(
                        rbwsl_list_id=target.rbwls_id, rbwsl_name_key=row.rbwsl_name_key,
                        rbwsl_name=row.rbwsl_name, rbwsl_rbset_id=row.rbwsl_rbset_id,
                        rbwsl_rbcar_id=row.rbwsl_rbcar_id, rbwsl_foil=row.rbwsl_foil,
                        rbwsl_qty=row.rbwsl_qty, rbwsl_max_price=row.rbwsl_max_price,
                        rbwsl_note=row.rbwsl_note, rbwsl_created_at=now,
                        rbwsl_updated_at=now))
                continue
            if hit.rbwsl_qty >= QTY_MAX:
                counts['skipped'] += 1
            else:
                counts['merged'] += 1
                hit.rbwsl_qty = min(QTY_MAX, hit.rbwsl_qty + row.rbwsl_qty)
            if hit.rbwsl_max_price is None:
                hit.rbwsl_max_price = row.rbwsl_max_price
            if hit.rbwsl_note is None:
                hit.rbwsl_note = row.rbwsl_note
            hit.rbwsl_updated_at = now
            if mode == 'move':
                db.session.delete(row)
        source.rbwls_updated_at = target.rbwls_updated_at = now
        db.session.commit()
    _rollback_on_error(action)
    return counts


# --- read model ----------------------------------------------------------------------------

class _ReadContext:
    """The catalog, prices and owned copies the lines of one response need, in a fixed number
    of SQL statements whatever the number of lines: cards, sets, the price mapping and price
    rows (`price_summaries`, only when a line has a known card) and the user's copies grouped
    by printing and foil."""

    def __init__(self, user, lines):
        cards = db.session.execute(sa.select(RbCard)).scalars().all()
        self.set_rank = catalog.set_order(db.session.query(RbSet).all())
        self.base_keys = catalog.base_printing_keys(cards, self.set_rank)
        self.cards = {(card.rbcar_rbset_id, card.rbcar_id): card for card in cards}
        wanted = {line.rbwsl_name_key for line in lines}
        self.by_name: dict[str, list[tuple]] = {}
        for card in cards:
            key = name_key(card.rbcar_name)
            if key in wanted:
                self.by_name.setdefault(key, []).append((card.rbcar_rbset_id, card.rbcar_id))
        for keys in self.by_name.values():
            keys.sort(key=lambda k: catalog.natural_key(
                self.set_rank.get(k[0], len(self.set_rank)), k[1]))
        printings = {k for keys in self.by_name.values() for k in keys}
        self.prices = price_summaries(
            (k[0], k[1], self.cards[k].rbcar_rarity, _foilable(self.cards[k]))
            for k in sorted(printings))
        self.owned: dict[tuple, dict] = {}
        for set_id, card_id, foil, qty in db.session.execute(
                sa.select(RbCollection.rbcol_rbset_id, RbCollection.rbcol_rbcar_id,
                          RbCollection.rbcol_foil, sa.func.sum(RbCollection.rbcol_quantity))
                .where(RbCollection.rbcol_user == user.username)
                .group_by(RbCollection.rbcol_rbset_id, RbCollection.rbcol_rbcar_id,
                          RbCollection.rbcol_foil)).all():
            entry = self.owned.setdefault((set_id, card_id), {'total': 0, 'foil': 0})
            entry['total'] += int(qty or 0)
            if foil == 'S':
                entry['foil'] += int(qty or 0)

    def _count(self, keys) -> dict:
        total = sum(self.owned.get(k, {}).get('total', 0) for k in keys)
        foil = sum(self.owned.get(k, {}).get('foil', 0) for k in keys)
        return {'total': total, 'foil': foil}

    def _market(self, keys, foil: str) -> dict | None:
        """The cheapest price among `keys` for the foil wish (`any` takes either finish)."""
        best = None
        for k in keys:
            summary = self.prices.get(k)
            if not summary:
                continue
            for is_foil, field in ((False, 'market'), (True, 'market_foil')):
                if (foil == 'N' and is_foil) or (foil == 'S' and not is_foil):
                    continue
                value = summary.get(field)
                if value is None or (best is not None and value >= best['value']):
                    continue
                best = {'value': value, 'source': summary.get(f'{field}_source'),
                        'as_of': summary.get('as_of'), 'set_id': k[0], 'card_id': k[1],
                        'foil': is_foil}
        if best is not None:
            best['value'] = float(_money(best['value']))
        return best

    def payload(self, line: RbWishlistLine) -> dict:
        group = self.by_name.get(line.rbwsl_name_key, [])
        if line.rbwsl_rbset_id is not None:
            shown = (line.rbwsl_rbset_id, line.rbwsl_rbcar_id)
            mine = [shown]
        else:
            shown = next((k for k in group if k in self.base_keys), group[0] if group else None)
            mine = list(group)
        others = [k for k in group if k not in mine and k != shown]
        card = self.cards.get(shown) if shown is not None else None
        market = self._market(mine, line.rbwsl_foil)
        max_price = line.rbwsl_max_price
        reached = None
        if max_price is not None:
            reached = market is not None and _money(market['value']) <= Decimal(max_price)
        owned_others = self._count(others)
        return {
            'id': line.rbwsl_id,
            'list_id': line.rbwsl_list_id,
            'name': line.rbwsl_name,
            'set_id': line.rbwsl_rbset_id,
            'card_id': line.rbwsl_rbcar_id,
            'card': None if card is None else _card_mini(
                card, market=(self.prices.get(shown) or {}).get('market'),
                owned_total=self._count([shown])['total'], is_base=shown in self.base_keys),
            'foil': line.rbwsl_foil,
            'qty': line.rbwsl_qty,
            'max_price': _float(max_price),
            'note': line.rbwsl_note,
            'created_at': _iso(line.rbwsl_created_at),
            'updated_at': _iso(line.rbwsl_updated_at),
            'market': market,
            'reached': reached,
            'owned': {
                'this_version': self._count(mine),
                'other_versions': {
                    'total': owned_others['total'],
                    'alt_art': self._count(k for k in others
                                           if k not in self.base_keys)['total'],
                    'foil': owned_others['foil'],
                },
            },
        }


def line_payloads(user, lines) -> list[dict]:
    """`WishlistLine` for each of `lines` (rows of one user), batched."""
    lines = list(lines)
    context = _ReadContext(user, lines)
    return [context.payload(line) for line in lines]


def list_lines(user, list_id, q: str | None = None) -> dict:
    """`{items: [WishlistLine], meta}` of one list in the order the lines were added; `q`
    keeps the lines whose name contains it (ignoring case). `meta`: `total` (lines
    returned), `line_count` (lines in the list), `max_lines`, `market_total` (market x qty of
    the returned priced lines, EUR) and `unpriced` (returned lines without a market price)."""
    wishlist = _owned_list(user, list_id)
    rows = list(db.session.execute(sa.select(RbWishlistLine).where(
        RbWishlistLine.rbwsl_list_id == wishlist.rbwls_id)
        .order_by(RbWishlistLine.rbwsl_id)).scalars())
    needle = ' '.join((q or '').casefold().split())
    shown = [row for row in rows if needle in ' '.join(row.rbwsl_name.casefold().split())]
    items = line_payloads(user, shown)
    total = sum((Decimal(str(item['market']['value'])) * item['qty']
                 for item in items if item['market'] is not None), Decimal(0))
    return {'items': items, 'meta': {
        'total': len(items), 'line_count': len(rows), 'max_lines': MAX_LINES,
        'market_total': float(total.quantize(CENT, ROUND_HALF_UP)),
        'unpriced': sum(1 for item in items if item['market'] is None)}}
