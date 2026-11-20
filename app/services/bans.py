"""Card bans per game mode (F2-a): name normalization, reads and writes.

A ban applies to a card NAME in one mode (`app.schemas.game_domain.GAME_MODES`)
and so to every printing of that name. Names are matched with `name_key` only
(F2-R3). Migration 0009 keeps a frozen copy of `name_key`; a test keeps the two
equal.

A ban is IN EFFECT from its `since` date: `since <= today()`, where `today()` is the
UTC calendar date of `app.utils.clock.utcnow()` (Riot announces a ban list with a calendar
date and no time zone, so a ban dated 23 Nov applies from 00:00 UTC that day). A ban dated
later is UPCOMING: it is shown (`ban_info`, `list_bans`, GET /bans, `flask bans list`) but
never applied: `ban_map()` (deck legality, the `banned_in` filter, card summaries) and
`card_bans` only see bans in effect.

Reads never touch the request: callers that need the bans of many cards load
`ban_map()` once and pass it to `card_bans` / `ban_info`. Writes commit and
raise on invalid input; they never print (the CLI does).
"""
from dataclasses import dataclass
from datetime import date

import sqlalchemy as sa

from app import db
from app.models import RbCard, RbCardBan
from app.models.ban import REASON_MAX_LENGTH
from app.schemas.game_domain import GAME_MODES
from app.utils import clock


@dataclass(frozen=True)
class BanEntry:
    name: str
    mode: str
    since: date
    reason: str | None


BAN_STATUSES = ('all', 'active', 'upcoming')


class UnknownCardName(Exception):
    """No catalog card has this name (by `name_key`); `args[0]` is the name."""


def name_key(name: str) -> str:
    """The normalized form of a card name: typographic apostrophes become `'`,
    case is folded and runs of whitespace become one space (trimmed)."""
    return ' '.join(name.replace('’', "'").replace('‘', "'").casefold().split())


def _entry(ban: RbCardBan) -> BanEntry:
    return BanEntry(ban.rbban_name, ban.rbban_mode, ban.rbban_since, ban.rbban_reason)


def _check_modes(modes) -> None:
    unknown = [mode for mode in modes if mode not in GAME_MODES]
    if unknown:
        raise ValueError(f'unknown game mode: {unknown[0]}')


# --- reads ---------------------------------------------------------------------------

def today() -> date:
    """The date bans are checked against: the UTC calendar date of `clock.utcnow()`."""
    return clock.utcnow().date()


def in_effect(entry: BanEntry, on: date | None = None) -> bool:
    """Whether the ban applies on the date `on` (default `today()`): `since <= on`."""
    return entry.since <= (today() if on is None else on)


def ban_map(include_upcoming: bool = False) -> dict[str, dict[str, BanEntry]]:
    """The bans in effect today (with `include_upcoming`, every ban), keyed by `name_key`
    and then by mode (one query). Legality, filters and card summaries use the default."""
    day = today()
    bans: dict[str, dict[str, BanEntry]] = {}
    for ban in db.session.execute(sa.select(RbCardBan)).scalars():
        entry = _entry(ban)
        if include_upcoming or in_effect(entry, day):
            bans.setdefault(ban.rbban_name_key, {})[ban.rbban_mode] = entry
    return bans


def card_bans(name: str, bans=None) -> dict[str, bool]:
    """Whether `name` is banned TODAY in each mode, always every mode in GAME_MODES order.
    Upcoming bans count as not banned, even in a map read with `include_upcoming`."""
    entries = (ban_map() if bans is None else bans).get(name_key(name), {})
    day = today() if entries else None
    return {mode: mode in entries and in_effect(entries[mode], day) for mode in GAME_MODES}


def ban_info(name: str, bans=None) -> list[dict]:
    """The bans of `name` as `{mode, since (ISO), reason, active}`, in GAME_MODES order;
    `active` is false while the ban is upcoming. Without `bans` every ban is read
    (`ban_map(include_upcoming=True)`); a map passed in decides what is listed."""
    entries = (ban_map(include_upcoming=True) if bans is None else bans).get(name_key(name), {})
    day = today()
    return [{'mode': mode, 'since': entries[mode].since.isoformat(),
             'reason': entries[mode].reason, 'active': in_effect(entries[mode], day)}
            for mode in GAME_MODES if mode in entries]


def list_bans(mode: str | None = None, status: str = 'all',
              on: date | None = None) -> list[BanEntry]:
    """Every ban (or those of one mode), ordered by mode (GAME_MODES order), then name_key.
    `status` (BAN_STATUSES): `all`, `active` (in effect on `on`, default `today()`) or `upcoming`."""
    if status not in BAN_STATUSES:
        raise ValueError(f'unknown ban status: {status}')
    query = sa.select(RbCardBan)
    if mode is not None:
        _check_modes([mode])
        query = query.where(RbCardBan.rbban_mode == mode)
    found = db.session.execute(query).scalars().all()
    found.sort(key=lambda ban: (GAME_MODES.index(ban.rbban_mode), ban.rbban_name_key))
    entries = [_entry(ban) for ban in found]
    if status == 'all':
        return entries
    day = today() if on is None else on
    return [entry for entry in entries if in_effect(entry, day) == (status == 'active')]


def printings_by_key() -> dict[str, list[tuple[str, str]]]:
    """Every catalog card as `(set_id, card_id)`, grouped by the `name_key` of its
    name and ordered by set id, then card id (one query)."""
    printings: dict[str, list[tuple[str, str]]] = {}
    rows = db.session.execute(
        sa.select(RbCard.rbcar_rbset_id, RbCard.rbcar_id, RbCard.rbcar_name)
        .order_by(RbCard.rbcar_rbset_id, RbCard.rbcar_id))
    for set_id, card_id, name in rows:
        printings.setdefault(name_key(name), []).append((set_id, card_id))
    return printings


def _catalog_name(key: str) -> str | None:
    """The catalog spelling of the first card (by set id, card id) whose name has `key`."""
    rows = db.session.execute(
        sa.select(RbCard.rbcar_name).order_by(RbCard.rbcar_rbset_id, RbCard.rbcar_id))
    return next((name for (name,) in rows if name_key(name) == key), None)


def _ban_row(key: str, mode: str) -> RbCardBan | None:
    return db.session.execute(
        sa.select(RbCardBan).where(RbCardBan.rbban_name_key == key,
                                   RbCardBan.rbban_mode == mode)).scalar_one_or_none()


# --- writes --------------------------------------------------------------------------

def add_ban(name: str, modes, since: date | None = None, reason: str | None = None,
            force: bool = False) -> list[tuple[str, str]]:
    """Ban `name` in each of `modes`; one `(mode, 'added' | 'updated' | 'unchanged')`
    per mode. Raises `UnknownCardName` (unless `force`) or `ValueError`, writing nothing."""
    _check_modes(modes)
    if reason is not None and not reason.strip():
        reason = None
    if reason is not None and len(reason) > REASON_MAX_LENGTH:
        raise ValueError('reason too long')
    key = name_key(name)
    display = _catalog_name(key)
    if display is None:
        if not force:
            raise UnknownCardName(name)
        display = name.strip()

    results = []
    for mode in modes:
        ban = _ban_row(key, mode)
        if ban is None:
            db.session.add(RbCardBan(
                rbban_name_key=key, rbban_name=display, rbban_mode=mode,
                rbban_since=since or clock.utcnow().date(), rbban_reason=reason))
            db.session.flush()
            results.append((mode, 'added'))
            continue
        changed = False
        if since is not None and since != ban.rbban_since:
            ban.rbban_since = since
            changed = True
        if reason is not None and reason != ban.rbban_reason:
            ban.rbban_reason = reason
            changed = True
        results.append((mode, 'updated' if changed else 'unchanged'))
    db.session.commit()
    return results


def remove_ban(name: str, modes) -> list[tuple[str, str]]:
    """Lift the ban of `name` (matched by `name_key` only) in each of `modes`;
    one `(mode, 'removed' | 'absent')` per mode."""
    _check_modes(modes)
    key = name_key(name)
    results = []
    for mode in modes:
        ban = _ban_row(key, mode)
        if ban is None:
            results.append((mode, 'absent'))
            continue
        db.session.delete(ban)
        db.session.flush()
        results.append((mode, 'removed'))
    db.session.commit()
    return results
