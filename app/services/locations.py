"""Storage locations (F16-a): where each copy of a collection line is kept.

A location belongs to one user (`rbloc_user`, the username, like `rbcollection`), has a code
that is unique per user ignoring case, an optional description, a place in the user's order
(`rbloc_position`, 1..n) and a lock. `rbcollection_locations` holds how many copies of a line
are in each location; the sum over a line is at most `rbcol_quantity` and the rest is
"unassigned" (derived, never stored).

The take order (F16-R6, R7): the user's unlocked locations by position, the lines of a
location by id, then the unassigned copies of the lines by id. Locked locations are never
taken from, and their quantities are read-only for the user until unlocked. The same order
serves the take into a location (`take_copies`, the mount of F16-e) and the removal of copies
when a line's quantity drops (`release`, used by `collection_write`).

Public writes are scoped to one user and commit when they succeed, rolling back when they
raise; `release` and `carry` leave the transaction to the caller. No Flask objects here.
"""
import re
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import RbCard, RbCollection, RbCollectionLocation, RbLocation
from app.services.bans import name_key
from app.utils import clock

CODE_RE = re.compile(r'[A-Za-z0-9-]{1,32}')
CODE_MAX = 32
DESCRIPTION_MAX = 200
SUGGESTED_RE = re.compile(r'([Bb])([0-9]+)-([Ff])([0-9]+)-([Pp])([0-9]+)')
FIRST_SUGGESTED_CODE = 'B001-F001-P0001'
BUMPS = {'block': 0, 'row': 1, 'pack': 2}
UNSET = object()


class InvalidCode(ValueError):
    """The code is not 1-32 letters, digits or `-`."""


class InvalidDescription(ValueError):
    """The description is longer than 200 characters."""


class DuplicateCode(Exception):
    """The user already has a location with this code (ignoring case)."""


class LocationNotFound(Exception):
    """The location does not exist or is not the user's."""


class LineNotFound(Exception):
    """The collection line does not exist or is not the user's."""


class LocationLocked(Exception):
    """The location is locked: its quantities are read-only, and a locked deck location
    cannot be deleted."""


class InvalidOrder(Exception):
    """The new order is not exactly the user's location ids, each once."""


class LocationOverQuantity(Exception):
    """More copies asked for than can be placed: `available` is how many can (the unassigned
    copies for an assignment, the line quantity for a whole replacement), `requested` how
    many were asked for."""

    def __init__(self, available: int, requested: int | None = None):
        super().__init__(f'only {available} copies can be placed')
        self.available = available
        self.requested = requested


class NotEnoughCopies(Exception):
    """The source (a location, or unassigned) holds fewer copies than asked for."""

    def __init__(self, available: int):
        super().__init__(f'only {available} copies there')
        self.available = available


class Shortfall(Exception):
    """Not enough copies outside locked locations; nothing changed.

    `missing`: one dict per short want (`index`, `line_ids`, `set_id`, `card_id`, `name`,
    `qty`, `available`); `locked`: the locked locations holding copies of those cards
    (`location_id`, `code`, `qty`), in the user's order."""

    def __init__(self, missing: list[dict], locked: list[dict]):
        super().__init__('not enough copies outside locked locations')
        self.missing = missing
        self.locked = locked


@dataclass(frozen=True)
class Want:
    """`qty` copies of some lines: the given `line_ids`, every line of one printing
    (`set_id` + `card_id`, any foil) or every line of a card name, any printing (D2)."""
    qty: int
    line_ids: tuple[int, ...] = ()
    set_id: str | None = None
    card_id: str | None = None
    name: str | None = None

    def __post_init__(self):
        if not isinstance(self.qty, int) or self.qty < 1:
            raise ValueError('qty must be at least 1')
        if (self.set_id is None) != (self.card_id is None):
            raise ValueError('a printing needs set_id and card_id')
        selectors = (bool(self.line_ids), self.set_id is not None, self.name is not None)
        if sum(selectors) != 1:
            raise ValueError('a want needs exactly one of line_ids, printing or name')


@dataclass(frozen=True)
class Move:
    """`qty` copies of a line from a location (`None` = unassigned) to a location
    (`None` = out of the collection, for a quantity drop)."""
    line_id: int
    from_location_id: int | None
    to_location_id: int | None
    qty: int


# --- helpers -------------------------------------------------------------------------------

def _check_code(code) -> str:
    if not isinstance(code, str) or not CODE_RE.fullmatch(code):
        raise InvalidCode(code)
    return code


def _check_description(description) -> str | None:
    if description is not None and len(description) > DESCRIPTION_MAX:
        raise InvalidDescription(len(description))
    return description or None


def _check_qty(qty) -> int:
    if not isinstance(qty, int) or qty < 1:
        raise ValueError('qty must be at least 1')
    return qty


def _owned_location(user, location_id) -> RbLocation:
    found = db.session.execute(sa.select(RbLocation).where(
        RbLocation.rbloc_id == location_id,
        RbLocation.rbloc_user == user.username)).scalar()
    if found is None:
        raise LocationNotFound(location_id)
    return found


def _owned_line(user, line_id) -> RbCollection:
    found = db.session.execute(sa.select(RbCollection).where(
        RbCollection.rbcol_id == line_id,
        RbCollection.rbcol_user == user.username).with_for_update()).scalar()
    if found is None:
        raise LineNotFound(line_id)
    return found


def _code_taken(user, code: str, except_id=None) -> bool:
    query = sa.select(RbLocation.rbloc_id).where(
        RbLocation.rbloc_user == user.username,
        sa.func.lower(RbLocation.rbloc_code) == code.lower())
    if except_id is not None:
        query = query.where(RbLocation.rbloc_id != except_id)
    return db.session.execute(query.limit(1)).scalar() is not None


def _commit_code(user, code: str, except_id=None) -> None:
    """Commit; a unique violation caused by a code inserted meanwhile is a DuplicateCode."""
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        if _code_taken(user, code, except_id):
            raise DuplicateCode(code) from None
        raise


def _ordered(user) -> list[RbLocation]:
    return list(db.session.execute(sa.select(RbLocation).where(
        RbLocation.rbloc_user == user.username).order_by(RbLocation.rbloc_position)).scalars())


def _renumber(rows: list[RbLocation]) -> None:
    """Give `rows` the positions 1..n in their order. Positions are unique per user and
    checked row by row, so every row first moves above all current positions."""
    above = max([row.rbloc_position for row in rows] + [len(rows)])
    for index, row in enumerate(rows, 1):
        row.rbloc_position = above + index
    db.session.flush()
    now = clock.utcnow()
    for index, row in enumerate(rows, 1):
        row.rbloc_position = index
        row.rbloc_updated_at = now
    db.session.flush()


def _held(line_id: int, location_id: int) -> RbCollectionLocation | None:
    return db.session.get(RbCollectionLocation, (line_id, location_id))


def _change(line_id: int, location_id: int, delta: int) -> None:
    """Add `delta` (negative to take) copies of a line to a location; 0 deletes the row."""
    held = _held(line_id, location_id)
    qty = (held.rbcll_qty if held is not None else 0) + delta
    if held is None:
        db.session.add(RbCollectionLocation(rbcll_line_id=line_id, rbcll_location_id=location_id,
                                            rbcll_qty=qty))
    elif qty == 0:
        db.session.delete(held)
    else:
        held.rbcll_qty = qty


def _assigned(line_id: int) -> int:
    return db.session.execute(sa.select(sa.func.coalesce(sa.func.sum(
        RbCollectionLocation.rbcll_qty), 0)).where(
        RbCollectionLocation.rbcll_line_id == line_id)).scalar_one()


# --- locations -----------------------------------------------------------------------------

def list_locations(user) -> list[RbLocation]:
    """The user's locations in their order."""
    return _ordered(user)


def _counts(user) -> dict[int, tuple[int, int]]:
    """`{location id: (copies, lines)}` of the user's locations that hold copies."""
    rows = db.session.execute(
        sa.select(RbCollectionLocation.rbcll_location_id,
                  sa.func.sum(RbCollectionLocation.rbcll_qty), sa.func.count())
        .join(RbLocation, RbLocation.rbloc_id == RbCollectionLocation.rbcll_location_id)
        .where(RbLocation.rbloc_user == user.username)
        .group_by(RbCollectionLocation.rbcll_location_id)).all()
    return {location_id: (int(copies), lines) for location_id, copies, lines in rows}


def location_item(location: RbLocation, copies: int = 0, cards: int = 0) -> dict:
    """The API shape of a location (F16-b): `cards` is the number of lines kept there."""
    return {'id': location.rbloc_id, 'code': location.rbloc_code,
            'description': location.rbloc_description, 'position': location.rbloc_position,
            'locked': location.rbloc_locked, 'deck_id': location.rbloc_deck_id,
            'copies': copies, 'cards': cards}


def location_items(user) -> list[dict]:
    """Every location of the user as `location_item`, in the user's order."""
    counts = _counts(user)
    return [location_item(location, *counts.get(location.rbloc_id, (0, 0)))
            for location in _ordered(user)]


def owned_item(user, location_id) -> dict:
    """One location of the user as `location_item`; LocationNotFound otherwise."""
    location = _owned_location(user, location_id)
    return location_item(location, *_counts(user).get(location.rbloc_id, (0, 0)))


def unassigned_total(user) -> int:
    """Copies of all the user's lines that are in no location."""
    total = db.session.execute(sa.select(sa.func.coalesce(sa.func.sum(
        RbCollection.rbcol_quantity), 0)).where(
        RbCollection.rbcol_user == user.username)).scalar_one()
    placed = db.session.execute(sa.select(sa.func.coalesce(sa.func.sum(
        RbCollectionLocation.rbcll_qty), 0)).join(
        RbCollection, RbCollection.rbcol_id == RbCollectionLocation.rbcll_line_id).where(
        RbCollection.rbcol_user == user.username)).scalar_one()
    return int(total) - int(placed)


def create_location(user, code, description=None) -> RbLocation:
    """A new location, last in the user's order (F16-R1, R2)."""
    _check_code(code)
    description = _check_description(description)
    if _code_taken(user, code):
        raise DuplicateCode(code)
    last = db.session.execute(sa.select(sa.func.max(RbLocation.rbloc_position)).where(
        RbLocation.rbloc_user == user.username)).scalar()
    location = RbLocation(rbloc_user=user.username, rbloc_code=code,
                          rbloc_description=description, rbloc_position=(last or 0) + 1,
                          rbloc_locked=False, rbloc_updated_at=clock.utcnow())
    db.session.add(location)
    _commit_code(user, code)
    return location


def update_location(user, location_id, *, code=UNSET, description=UNSET) -> RbLocation:
    """Change the code and/or the description; a locked location can be renamed (F16-R1)."""
    location = _owned_location(user, location_id)
    if code is not UNSET:
        _check_code(code)
        if _code_taken(user, code, location.rbloc_id):
            raise DuplicateCode(code)
        location.rbloc_code = code
    if description is not UNSET:
        location.rbloc_description = _check_description(description)
    location.rbloc_updated_at = clock.utcnow()
    _commit_code(user, location.rbloc_code, location.rbloc_id)
    return location


def delete_location(user, location_id) -> int:
    """Delete a location; its copies go back to unassigned and the order closes up. A locked
    deck location cannot be deleted (F16-R1). Returns how many copies became unassigned."""
    location = _owned_location(user, location_id)
    if location.rbloc_locked and location.rbloc_deck_id is not None:
        raise LocationLocked(location_id)
    held = list(db.session.execute(sa.select(RbCollectionLocation).where(
        RbCollectionLocation.rbcll_location_id == location.rbloc_id)).scalars())
    freed = sum(row.rbcll_qty for row in held)
    for row in held:
        db.session.delete(row)
    db.session.delete(location)
    db.session.flush()
    _renumber(_ordered(user))
    db.session.commit()
    return freed


def reorder_locations(user, location_ids) -> list[RbLocation]:
    """Set the whole order at once: `location_ids` must be every location of the user, each
    once; anything else changes nothing (F16-R2)."""
    rows = {row.rbloc_id: row for row in _ordered(user)}
    ids = list(location_ids)
    if len(ids) != len(set(ids)) or set(ids) != set(rows):
        raise InvalidOrder(ids)
    ordered = [rows[location_id] for location_id in ids]
    _renumber(ordered)
    db.session.commit()
    return ordered


def set_locked(user, location_id, locked: bool) -> RbLocation:
    """Lock or unlock a location (F16-R3)."""
    location = _owned_location(user, location_id)
    location.rbloc_locked = bool(locked)
    location.rbloc_updated_at = clock.utcnow()
    db.session.commit()
    return location


def suggest_next_code(user, last_code, bump: str) -> str | None:
    """The suggested code after `last_code` (F16-R1a, D6): `B001-F001-P0001` (block, row,
    pack). `bump` ('block', 'row' or 'pack') is the part that starts a new one: it goes up by
    one and the parts to its right restart at 1; widths and the letters' case are kept and a
    code the user already has is skipped. Without `last_code` the user's newest location with
    the pattern is used, or `B001-F001-P0001` when there is none. A code without the pattern
    has no suggestion (None)."""
    if bump not in BUMPS:
        raise ValueError(f'unknown bump {bump!r}')
    taken = {code.lower() for code in db.session.execute(sa.select(RbLocation.rbloc_code).where(
        RbLocation.rbloc_user == user.username)).scalars()}
    if last_code is None:
        newest = db.session.execute(sa.select(RbLocation.rbloc_code).where(
            RbLocation.rbloc_user == user.username).order_by(RbLocation.rbloc_id.desc())).scalars()
        last_code = next((code for code in newest if SUGGESTED_RE.fullmatch(code)), None)
        if last_code is None:
            return FIRST_SUGGESTED_CODE
    match = SUGGESTED_RE.fullmatch(last_code)
    if match is None:
        return None
    letters, digits = match.groups()[0::2], match.groups()[1::2]
    numbers = [int(part) for part in digits]
    part = BUMPS[bump]
    numbers[part + 1:] = [1] * (2 - part)

    def build():
        return '-'.join(f'{letter}{str(number).zfill(len(width))}'
                        for letter, number, width in zip(letters, numbers, digits))

    numbers[part] += 1
    while build().lower() in taken:
        numbers[part] += 1
    code = build()
    return code if len(code) <= CODE_MAX else None


# --- copies per location -------------------------------------------------------------------

def unassigned(line: RbCollection) -> int:
    """Copies of the line in no location: its quantity minus its location quantities."""
    return line.rbcol_quantity - _assigned(line.rbcol_id)


def line_locations(user, line_id) -> dict:
    """The line's locations in the user's order, with their quantity, and the unassigned
    remainder."""
    line = _owned_line(user, line_id)
    found = db.session.execute(
        sa.select(RbLocation, RbCollectionLocation.rbcll_qty)
        .join(RbCollectionLocation, RbCollectionLocation.rbcll_location_id == RbLocation.rbloc_id)
        .where(RbCollectionLocation.rbcll_line_id == line.rbcol_id)
        .order_by(RbLocation.rbloc_position)).all()
    return {
        'locations': [{'location_id': loc.rbloc_id, 'code': loc.rbloc_code,
                       'description': loc.rbloc_description, 'locked': loc.rbloc_locked,
                       'qty': qty} for loc, qty in found],
        'unassigned': line.rbcol_quantity - sum(qty for _, qty in found),
    }


def move_copies(user, line_id, from_location_id, to_location_id, qty: int) -> None:
    """Move copies of a line between locations; `None` is unassigned on either side. Both
    locations must be unlocked (F16-R3, R4)."""
    _check_qty(qty)
    if from_location_id is None and to_location_id is None:
        raise ValueError('a move needs a location')
    line = _owned_line(user, line_id)
    sides = [_owned_location(user, location_id)
             for location_id in (from_location_id, to_location_id) if location_id is not None]
    if any(location.rbloc_locked for location in sides):
        raise LocationLocked([location.rbloc_id for location in sides if location.rbloc_locked])
    if from_location_id is None:
        available = line.rbcol_quantity - _assigned(line.rbcol_id)
    else:
        held = _held(line.rbcol_id, from_location_id)
        available = held.rbcll_qty if held is not None else 0
    if qty > available:
        raise NotEnoughCopies(available)
    if from_location_id is not None:
        _change(line.rbcol_id, from_location_id, -qty)
    if to_location_id is not None:
        _change(line.rbcol_id, to_location_id, qty)
    db.session.commit()


def assign_copies(user, line_id, location_id, qty: int) -> None:
    """Put unassigned copies of a line in a location; over-assigning is refused (F16-R4)."""
    try:
        move_copies(user, line_id, None, location_id, qty)
    except NotEnoughCopies as exc:
        raise LocationOverQuantity(exc.available, qty) from None


def set_line_locations(user, line_id, assignments: dict) -> None:
    """Replace where a line's copies are (F16-R4): `assignments` is `{location id: qty}` and
    every location of the line that is not in it loses its copies (they become unassigned).
    A locked location whose quantity would change -> LocationLocked; more copies than the
    line quantity -> LocationOverQuantity(quantity, requested). All or nothing."""
    try:
        for qty in assignments.values():
            _check_qty(qty)
        line = _owned_line(user, line_id)
        targets = {location_id: _owned_location(user, location_id)
                   for location_id in assignments}
        current = {row.rbcll_location_id: row.rbcll_qty for row in db.session.execute(
            sa.select(RbCollectionLocation).where(
                RbCollectionLocation.rbcll_line_id == line.rbcol_id)).scalars()}
        changed = [location_id for location_id in current.keys() | assignments.keys()
                   if current.get(location_id, 0) != assignments.get(location_id, 0)]
        locked = [location_id for location_id in changed
                  if (targets.get(location_id) or db.session.get(RbLocation, location_id))
                  .rbloc_locked]
        if locked:
            raise LocationLocked(sorted(locked))
        requested = sum(assignments.values())
        if requested > line.rbcol_quantity:
            raise LocationOverQuantity(line.rbcol_quantity, requested)
        for location_id in changed:
            _change(line.rbcol_id, location_id,
                    assignments.get(location_id, 0) - current.get(location_id, 0))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def remove_copies(user, line_id, location_id, qty: int) -> None:
    """Take copies of a line out of a location; they become unassigned (F16-R4)."""
    move_copies(user, line_id, location_id, None, qty)


# --- take in order -------------------------------------------------------------------------

def _candidates(owner: str, wants) -> list[list[RbCollection]]:
    """The owner's lines each want selects, by id (locked for update on PostgreSQL)."""
    query = sa.select(RbCollection, RbCard.rbcar_name).join(
        RbCard, (RbCollection.rbcol_rbset_id == RbCard.rbcar_rbset_id)
        & (RbCollection.rbcol_rbcar_id == RbCard.rbcar_id)).where(
        RbCollection.rbcol_user == owner)
    if all(want.line_ids for want in wants):
        query = query.where(RbCollection.rbcol_id.in_(
            {line_id for want in wants for line_id in want.line_ids}))
    rows = list(db.session.execute(
        query.order_by(RbCollection.rbcol_id).with_for_update(of=RbCollection)).all())
    by_id = {line.rbcol_id: line for line, _ in rows}
    selected = []
    for want in wants:
        if want.line_ids:
            missing = [line_id for line_id in want.line_ids if line_id not in by_id]
            if missing:
                raise LineNotFound(missing)
            selected.append([by_id[line_id] for line_id in sorted(set(want.line_ids))])
        elif want.name is not None:
            key = name_key(want.name)
            selected.append([line for line, name in rows if name_key(name) == key])
        else:
            selected.append([line for line, _ in rows if (line.rbcol_rbset_id, line.rbcol_rbcar_id)
                             == (want.set_id, want.card_id)])
    return selected


def _plan(owner: str, wants, target_id=None) -> list[Move]:
    """The moves that take every want in order, or Shortfall (nothing is written). Copies
    already in `target_id` are not taken again."""
    selected = _candidates(owner, wants)
    line_ids = {line.rbcol_id for lines in selected for line in lines}
    held = db.session.execute(
        sa.select(RbCollectionLocation.rbcll_line_id, RbCollectionLocation.rbcll_qty, RbLocation)
        .join(RbLocation, RbLocation.rbloc_id == RbCollectionLocation.rbcll_location_id)
        .where(RbCollectionLocation.rbcll_line_id.in_(line_ids))
        .order_by(RbLocation.rbloc_position, RbCollectionLocation.rbcll_line_id)).all()
    left = {line.rbcol_id: line.rbcol_quantity for lines in selected for line in lines}
    for line_id, qty, _ in held:
        left[line_id] -= qty                      # what remains is unassigned
    sources = [((loc.rbloc_id, line_id), qty) for line_id, qty, loc in held
               if not loc.rbloc_locked and loc.rbloc_id != target_id]
    available = dict(sources)
    available.update({(None, line_id): qty for line_id, qty in left.items()})

    moves, missing = [], []
    for index, (want, lines) in enumerate(zip(wants, selected)):
        mine = {line.rbcol_id for line in lines}
        order = [key for key, _ in sources if key[1] in mine] + \
                [(None, line.rbcol_id) for line in lines]
        need = want.qty
        taken = []
        for key in order:
            qty = min(need, available[key])
            if qty:
                available[key] -= qty
                need -= qty
                taken.append(Move(key[1], key[0], target_id, qty))
            if not need:
                break
        moves.extend(taken)
        if need:
            missing.append({'index': index, 'line_ids': list(want.line_ids),
                            'set_id': want.set_id, 'card_id': want.card_id, 'name': want.name,
                            'qty': want.qty, 'available': want.qty - need})
    if missing:
        short = {line.rbcol_id for item in missing for line in selected[item['index']]}
        locked = {}
        for line_id, qty, loc in held:
            if line_id in short and loc.rbloc_locked and loc.rbloc_id != target_id:
                entry = locked.setdefault(loc.rbloc_id, {'location_id': loc.rbloc_id,
                                                         'code': loc.rbloc_code, 'qty': 0})
                entry['qty'] += qty
        raise Shortfall(missing, list(locked.values()))
    return moves


def take_copies(user, wants, into_location_id) -> list[Move]:
    """Move the copies of every want into a location of the user, taking them in order:
    unlocked locations by position, then unassigned (F16-R6). The target may be locked (the
    mounted deck of F16-e). All or nothing: when a want is short, Shortfall says which and
    which locked locations hold copies, and nothing changes. Line totals never change."""
    wants = list(wants)
    try:
        target = _owned_location(user, into_location_id)
        moves = _plan(user.username, wants, target.rbloc_id)
        for move in moves:
            if move.from_location_id is not None:
                _change(move.line_id, move.from_location_id, -move.qty)
            _change(move.line_id, target.rbloc_id, move.qty)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return moves


def release(line: RbCollection, qty: int) -> list[Move]:
    """Take `qty` copies off a line whose quantity is about to drop by `qty` (F16-R7): the
    same order as `take_copies`, so copies leave unlocked locations first and unassigned
    last; locked locations are skipped. Raises Shortfall when the copies outside locked
    locations are not enough. Writes nothing on failure; the caller commits."""
    moves = _plan(line.rbcol_user, [Want(qty, line_ids=(line.rbcol_id,))])
    for move in moves:
        if move.from_location_id is not None:
            _change(move.line_id, move.from_location_id, -move.qty)
    db.session.flush()
    return moves


def carry(moves, line_id: int) -> None:
    """Put the copies `moves` took out of locations into the same locations on another line
    (a split keeps copies where they are). The caller commits."""
    for move in moves:
        if move.from_location_id is not None:
            _change(line_id, move.from_location_id, move.qty)
    db.session.flush()
