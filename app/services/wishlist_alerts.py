"""Wishlist price alerts (F4-g-2, docs/requirements/F3/F3-f-wishlists-design.md D2, A3, A5).

`raise_alerts` runs after each daily Cardmarket price load (job `price_alerts`, queued by
`daily_prices`). Every wishlist line with a max price is compared with its market price, the
same resolution as `WishlistLine.market` (`wishlists.cheapest_market` over `price_summaries`):
the line's printing for its foil wish, or for a by-name line the cheapest priced printing of
the name.

Grouping: the lines of one user are grouped by the alert's unique key, (`name_key`, set,
card): a printing target and the by-name target of the same name are different alerts, and
the foil wishes of one printing share one. A group raises **one** alert for the price date
when **any** of its priced lines is at or below its max price (A3, owner 2026-11-12); the
alert stores the lowest max price among the lines that were met and that line's price
(ties: the lower price). Lines without a max price are never read; lines without a market
price take no part (a group with no priced line counts as `skipped_no_price`).

`price_date` is the date of the newest `rbcm_price` row (`pricing.price_as_of`), not the
wall-clock day, so a second run on the same load inserts nothing (the unique index on user,
target and price date; rows already there are skipped and the INSERT ignores conflicts).
There is no arming state: the next load raises the alert again while the price stays low.
Alerts are never linked to a list, so deleting a list keeps them (A5).

Statements whatever the number of lines: price date, lines, cards, price mapping, prices, the
day's existing alerts, one INSERT per 1000 alerts (7), then the commit.

Reading (`list_alerts`, `alert_lists`, `mark_read`) only ever sees the caller's alerts: another
user's alert, or an unknown id, raises `AlertNotFound` (the API answers 404). No Flask objects.
"""
import math
from datetime import date
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql, sqlite

from app import db
from app.models import RbCard, RbCollection, RbSet, RbWishlist, RbWishlistAlert, RbWishlistLine
from app.services import catalog
from app.services.bans import name_key
from app.services.card_detail import _card_mini
from app.services.pricing import price_as_of, price_summaries
from app.services.wishlists import _float, _foilable, _iso, _money, cheapest_market
from app.utils import clock


class NoPrices(Exception):
    """No Cardmarket price has been loaded yet: there is no price date to alert on."""


class AlertNotFound(Exception):
    """The alert does not exist or is not the user's."""


def _latest_price_date() -> date:
    latest = price_as_of()
    if latest is None:
        raise NoPrices('no Cardmarket prices loaded')
    return date.fromisoformat(latest)


# Rows per INSERT: 9 parameters a row stays far below PostgreSQL's 65 535.
INSERT_CHUNK = 1000


def _insert(rows: list[dict]) -> None:
    """INSERT the rows (one statement per `INSERT_CHUNK`), ignoring any that a concurrent run
    already wrote (both dialects)."""
    dialect = postgresql if db.engine.dialect.name == 'postgresql' else sqlite
    for start in range(0, len(rows), INSERT_CHUNK):
        db.session.execute(dialect.insert(RbWishlistAlert)
                           .values(rows[start:start + INSERT_CHUNK]).on_conflict_do_nothing())


def raise_alerts(price_date: date | None = None) -> dict:
    """Raise the alerts of `price_date` (default: the latest price load) and commit.
    Returns `{price_date, lines_checked, cards_checked, alerts_created, skipped_no_price}`:
    lines with a max price, user + target groups, alerts inserted, groups without a price."""
    if price_date is None:
        price_date = _latest_price_date()
    lines = db.session.execute(
        sa.select(RbWishlist.rbwls_user_id, RbWishlistLine)
        .join(RbWishlist, RbWishlist.rbwls_id == RbWishlistLine.rbwsl_list_id)
        .where(RbWishlistLine.rbwsl_max_price.is_not(None))
        .order_by(RbWishlistLine.rbwsl_id)).all()
    result = {'price_date': price_date.isoformat(), 'lines_checked': len(lines),
              'cards_checked': 0, 'alerts_created': 0, 'skipped_no_price': 0}
    if not lines:
        return result

    wanted = {line.rbwsl_name_key for _, line in lines}
    cards, by_name = {}, {}
    for card in db.session.execute(sa.select(RbCard)).scalars():
        printing = (card.rbcar_rbset_id, card.rbcar_id)
        cards[printing] = card
        key = name_key(card.rbcar_name)
        if key in wanted:
            by_name.setdefault(key, []).append(printing)

    def printings(line) -> list[tuple]:
        if line.rbwsl_rbset_id is None:
            return by_name.get(line.rbwsl_name_key, [])
        printing = (line.rbwsl_rbset_id, line.rbwsl_rbcar_id)
        return [printing] if printing in cards else []

    needed = sorted({k for _, line in lines for k in printings(line)})
    prices = price_summaries((k[0], k[1], cards[k].rbcar_rarity, _foilable(cards[k]))
                             for k in needed)

    groups: dict[tuple, list] = {}
    for user, line in lines:
        target = (user, line.rbwsl_name_key, line.rbwsl_rbset_id, line.rbwsl_rbcar_id)
        groups.setdefault(target, []).append(line)
    result['cards_checked'] = len(groups)

    raised = {}
    for target, group in groups.items():
        priced = []
        for line in group:
            market = cheapest_market(prices, printings(line), line.rbwsl_foil)
            if market is not None:
                priced.append((Decimal(line.rbwsl_max_price), _money(market['value']), line))
        if not priced:
            result['skipped_no_price'] += 1
            continue
        met = [entry for entry in priced if entry[1] <= entry[0]]
        if met:
            raised[target] = min(met, key=lambda entry: (entry[0], entry[1]))

    if raised:
        existing = {(row.rbwal_user_id, row.rbwal_name_key, row.rbwal_rbset_id,
                     row.rbwal_rbcar_id) for row in db.session.execute(
            sa.select(RbWishlistAlert.rbwal_user_id, RbWishlistAlert.rbwal_name_key,
                      RbWishlistAlert.rbwal_rbset_id, RbWishlistAlert.rbwal_rbcar_id)
            .where(RbWishlistAlert.rbwal_price_date == price_date)).all()}
        now = clock.utcnow()
        rows = [{'rbwal_user_id': target[0], 'rbwal_name_key': target[1],
                 'rbwal_name': line.rbwsl_name, 'rbwal_rbset_id': target[2],
                 'rbwal_rbcar_id': target[3], 'rbwal_price': price,
                 'rbwal_max_price': max_price, 'rbwal_price_date': price_date,
                 'rbwal_created_at': now}
                for target, (max_price, price, line) in raised.items()
                if target not in existing]
        if rows:
            _insert(rows)
        result['alerts_created'] = len(rows)
    db.session.commit()
    return result


# --- reading ---------------------------------------------------------------------------------

def _cards_of(rows, username: str) -> dict:
    """`{alert id: CardMini | None}`: the alert's printing, or for a by-name alert the base
    printing of the name (as `WishlistLine.card`). Five statements: cards, sets, price mapping,
    prices and the user's copies of those printings."""
    cards = db.session.execute(sa.select(RbCard)).scalars().all()
    by_key = {(card.rbcar_rbset_id, card.rbcar_id): card for card in cards}
    base_keys = catalog.base_printing_keys(cards, catalog.set_order(
        db.session.query(RbSet).all()))
    wanted = {row.rbwal_name_key for row in rows if row.rbwal_rbset_id is None}
    base_by_name = {}
    for card in cards:
        printing = (card.rbcar_rbset_id, card.rbcar_id)
        if wanted and printing in base_keys and name_key(card.rbcar_name) in wanted:
            key = name_key(card.rbcar_name)
            base_by_name.setdefault(key, printing)
    shown = {}
    for row in rows:
        printing = (row.rbwal_rbset_id, row.rbwal_rbcar_id) if row.rbwal_rbset_id is not None \
            else base_by_name.get(row.rbwal_name_key)
        shown[row.rbwal_id] = printing if printing in by_key else None
    printings = sorted({k for k in shown.values() if k is not None})
    prices = price_summaries((k[0], k[1], by_key[k].rbcar_rarity, _foilable(by_key[k]))
                             for k in printings)
    owned = {}
    if printings:
        for set_id, card_id, qty in db.session.execute(
                sa.select(RbCollection.rbcol_rbset_id, RbCollection.rbcol_rbcar_id,
                          sa.func.sum(RbCollection.rbcol_quantity))
                .where(RbCollection.rbcol_user == username)
                .group_by(RbCollection.rbcol_rbset_id, RbCollection.rbcol_rbcar_id)).all():
            owned[(set_id, card_id)] = int(qty or 0)
    return {alert_id: None if k is None else _card_mini(
                by_key[k], market=(prices.get(k) or {}).get('market'),
                owned_total=owned.get(k, 0), is_base=k in base_keys)
            for alert_id, k in shown.items()}


def alert_item(row: RbWishlistAlert, card: dict | None) -> dict:
    """The API shape of an alert (`WishlistAlert`)."""
    return {'id': row.rbwal_id, 'name': row.rbwal_name, 'card': card,
            'set_id': row.rbwal_rbset_id, 'card_id': row.rbwal_rbcar_id,
            'price': _float(row.rbwal_price), 'max_price': _float(row.rbwal_max_price),
            'price_date': row.rbwal_price_date.isoformat(),
            'created_at': _iso(row.rbwal_created_at), 'read_at': _iso(row.rbwal_read_at)}


def list_alerts(user, *, unread: bool = False, page: int = 1, per_page: int = 25) -> dict:
    """`{items: [WishlistAlert], meta: {page, per_page, total, pages, unread_count}}`, newest
    first (raised time, then id). `unread` keeps the unread alerts. Two statements (counts,
    page) when the page is empty, seven with alerts on it."""
    mine = RbWishlistAlert.rbwal_user_id == user.id
    total, unread_count = db.session.execute(sa.select(
        sa.func.count(), sa.func.coalesce(sa.func.sum(sa.case(
            (RbWishlistAlert.rbwal_read_at.is_(None), 1), else_=0)), 0))
        .select_from(RbWishlistAlert).where(mine)).one()
    total, unread_count = int(total), int(unread_count)
    if unread:
        total = unread_count
    query = sa.select(RbWishlistAlert).where(mine)
    if unread:
        query = query.where(RbWishlistAlert.rbwal_read_at.is_(None))
    rows = list(db.session.execute(query.order_by(
        RbWishlistAlert.rbwal_created_at.desc(), RbWishlistAlert.rbwal_id.desc())
        .limit(per_page).offset((page - 1) * per_page)).scalars())
    cards = _cards_of(rows, user.username) if rows else {}
    return {'items': [alert_item(row, cards.get(row.rbwal_id)) for row in rows],
            'meta': {'page': page, 'per_page': per_page, 'total': total,
                     'pages': math.ceil(total / per_page) if total else 0,
                     'unread_count': unread_count}}


def alert_lists(user, alert_id) -> list[dict]:
    """The user's wishlists that hold the alert's card **now** (A5), in the user's list order:
    `[{id, name, is_default, qty, max_price}]`. A by-name alert matches every line of the
    name; a printing alert matches the lines of that printing and the by-name lines of the
    name. `qty` adds the matching lines of the list (every finish) and `max_price` is their
    lowest max price (null when none has one). Two statements."""
    row = db.session.execute(sa.select(RbWishlistAlert).where(
        RbWishlistAlert.rbwal_id == alert_id, RbWishlistAlert.rbwal_user_id == user.id)
    ).scalar()
    if row is None:
        raise AlertNotFound(alert_id)
    query = (sa.select(RbWishlist, RbWishlistLine)
             .join(RbWishlistLine, RbWishlistLine.rbwsl_list_id == RbWishlist.rbwls_id)
             .where(RbWishlist.rbwls_user_id == user.id,
                    RbWishlistLine.rbwsl_name_key == row.rbwal_name_key))
    if row.rbwal_rbset_id is not None:
        query = query.where(sa.or_(
            RbWishlistLine.rbwsl_rbset_id.is_(None),
            sa.and_(RbWishlistLine.rbwsl_rbset_id == row.rbwal_rbset_id,
                    RbWishlistLine.rbwsl_rbcar_id == row.rbwal_rbcar_id)))
    items: dict[int, dict] = {}
    for wishlist, line in db.session.execute(query.order_by(
            RbWishlist.rbwls_position, RbWishlistLine.rbwsl_id)).all():
        item = items.setdefault(wishlist.rbwls_id, {
            'id': wishlist.rbwls_id, 'name': wishlist.rbwls_name,
            'is_default': wishlist.rbwls_is_default, 'qty': 0, 'max_price': None})
        item['qty'] += line.rbwsl_qty
        if line.rbwsl_max_price is not None:
            value = _float(line.rbwsl_max_price)
            item['max_price'] = value if item['max_price'] is None \
                else min(item['max_price'], value)
    return list(items.values())


def mark_read(user, ids=None) -> int:
    """Mark the caller's unread alerts read (all of them when `ids` is empty or None; else
    the ones among `ids`; read, unknown and other users' ids are ignored). Returns how many
    changed."""
    query = sa.update(RbWishlistAlert).where(
        RbWishlistAlert.rbwal_user_id == user.id, RbWishlistAlert.rbwal_read_at.is_(None))
    if ids:
        query = query.where(RbWishlistAlert.rbwal_id.in_(sorted(set(ids))))
    try:
        marked = db.session.execute(query.values(rbwal_read_at=clock.utcnow()),
                                    execution_options={'synchronize_session': False}).rowcount
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return marked
