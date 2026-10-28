"""Collection writes (F3-c): add, edit, delete, split, bulk and "keep a playset".

Every function is scoped to one user and works in one transaction: it commits when it
succeeds and rolls back when it raises. Quantities that add up (merging a new line into
an identical one, splitting into an existing line) are changed in SQL
(`rbcol_quantity = rbcol_quantity + n`), never read, added and written back, so two requests
at once cannot lose a copy. An edit is applied only if the row still has the change time it
was read with (`stale_line` otherwise).
"""
from decimal import ROUND_HALF_UP, Decimal

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import RbCard, RbCollection, RbKeepPlayset, RbUserPrefs
from app.services import catalog, collection_read, collection_rules
from app.utils import clock

CENT = Decimal('0.01')
MARKUP = Decimal('1.05')


class UnknownCard(Exception):
    """No catalog card has this set and card id."""


class FoilNotAllowed(Exception):
    """A foil line was asked for a card that has no foil version."""


class LineNotFound(Exception):
    """The line does not exist or is not the user's (always a 404)."""


class StaleLine(Exception):
    """The line changed after the client read it."""


class InsufficientQuantity(Exception):
    """Not enough copies; `available` is how many could be used."""

    def __init__(self, available: int):
        super().__init__(f'only {available} copies available')
        self.available = available


def _money(value) -> Decimal | None:
    return None if value is None else Decimal(str(value)).quantize(CENT, ROUND_HALF_UP)


def _eq(column, value):
    return column.is_(None) if value is None else column == value


def _card(set_id: str, card_id: str) -> RbCard:
    card = db.session.get(RbCard, (set_id, card_id))
    if card is None:
        raise UnknownCard(f'{set_id}-{card_id}')
    return card


def _foilable(card: RbCard) -> bool:
    card_type, _ = catalog.parse_type(card.rbcar_type)
    return catalog.is_foilable(card_type, card.rbcar_rarity)


def _default_sell_price(market: Decimal | None) -> Decimal | None:
    """Market plus 5 %, rounded half up to cents; None when the card has no price."""
    return None if market is None else (market * MARKUP).quantize(CENT, ROUND_HALF_UP)


def _owned(user, line_id: int) -> tuple[RbCollection, RbCard]:
    found = db.session.execute(
        sa.select(RbCollection, RbCard)
        .join(RbCard, (RbCollection.rbcol_rbset_id == RbCard.rbcar_rbset_id)
              & (RbCollection.rbcol_rbcar_id == RbCard.rbcar_id))
        .where(RbCollection.rbcol_id == line_id, RbCollection.rbcol_user == user.username)
    ).first()
    if found is None:
        raise LineNotFound(line_id)
    return found[0], found[1]


def _identical(user, set_id, card_id, foil, condition, language, purchase, selling, sell_price):
    """The user's line with exactly this key (NULL-safe), or None (the merge key of S2)."""
    return db.session.execute(
        sa.select(RbCollection).where(
            RbCollection.rbcol_user == user.username,
            RbCollection.rbcol_rbset_id == set_id,
            RbCollection.rbcol_rbcar_id == card_id,
            RbCollection.rbcol_foil == foil,
            _eq(RbCollection.rbcol_condition, condition),
            _eq(RbCollection.rbcol_language, language),
            _eq(RbCollection.rbcol_purchase_price, purchase),
            RbCollection.rbcol_selling == selling,
            _eq(RbCollection.rbcol_sell_price, sell_price),
        ).order_by(RbCollection.rbcol_id).limit(1)).scalar()


def _add_to(line_id: int, qty: int, sell_qty: int, now) -> None:
    """Add copies to a line in SQL."""
    db.session.execute(
        sa.update(RbCollection).where(RbCollection.rbcol_id == line_id).values(
            rbcol_quantity=RbCollection.rbcol_quantity + qty,
            rbcol_sell_qty=RbCollection.rbcol_sell_qty + sell_qty,
            rbcol_chadat=now))


def _payload(row, card):
    db.session.refresh(row)
    return collection_read.line_payloads([(row, card)])[0]


# --- add -----------------------------------------------------------------------------------

def add_row(user, card, foil: bool, qty: int, condition, language, purchase, selling: bool,
            sell_qty: int, sell_price, now=None) -> tuple[RbCollection, bool]:
    """The merge rule of S2 without validation, defaults, commit or payload: add `qty` copies to
    the user's identical line (in SQL) or insert a new line. Returns `(row, merged)`. The caller
    owns the transaction (the CSV import adds many rows in one)."""
    now = now or clock.utcnow()
    foil_code, selling_code = ('S' if foil else 'N'), ('Y' if selling else 'N')
    existing = _identical(user, card.rbcar_rbset_id, card.rbcar_id, foil_code, condition,
                          language, purchase, selling_code, sell_price)
    if existing is not None:
        _add_to(existing.rbcol_id, qty, sell_qty, now)
        return existing, True
    row = RbCollection(
        rbcol_rbset_id=card.rbcar_rbset_id, rbcol_rbcar_id=card.rbcar_id, rbcol_foil=foil_code,
        rbcol_user=user.username, rbcol_quantity=qty, rbcol_sell_qty=sell_qty,
        rbcol_selling=selling_code, rbcol_sell_price=sell_price, rbcol_purchase_price=purchase,
        rbcol_condition=condition, rbcol_language=language, rbcol_chadat=now)
    db.session.add(row)
    return row, False


def add_line(user, data) -> tuple[dict, bool]:
    """Add copies of a card; returns `(line, merged)` (S2)."""
    card = _card(data.set_id, data.card_id)
    if data.foil and not _foilable(card):
        raise FoilNotAllowed(f'{data.set_id}-{data.card_id}')
    sell_qty = data.sell_qty if data.sell_qty is not None else (data.qty if data.selling else 0)
    if sell_qty > data.qty:
        raise InsufficientQuantity(data.qty)
    sell_price = _money(data.sell_price)
    if data.selling and sell_price is None:
        sell_price = _default_sell_price(collection_read.market_price(card, data.foil))
    purchase = _money(data.purchase_price)
    row, merged = add_row(user, card, data.foil, data.qty, data.condition, data.language,
                          purchase, data.selling, sell_qty, sell_price)
    db.session.commit()
    return _payload(row, card), merged


# --- edit ----------------------------------------------------------------------------------

def edit_line(user, line_id: int, data) -> dict:
    """Change the sent fields of a line (S3)."""
    row, card = _owned(user, line_id)
    stamp = data.updated_stamp
    if stamp is not None and row.rbcol_chadat.replace(microsecond=0) != stamp.replace(
            microsecond=0):
        raise StaleLine(line_id)

    sent = data.model_fields_set
    qty = data.qty if 'qty' in sent else row.rbcol_quantity
    if 'sell_qty' in sent:
        if data.sell_qty > qty:
            raise InsufficientQuantity(qty)
        sell_qty = data.sell_qty
    else:
        sell_qty = min(row.rbcol_sell_qty, qty)
    values = {'rbcol_quantity': qty, 'rbcol_sell_qty': sell_qty}
    if 'condition' in sent:
        values['rbcol_condition'] = data.condition
    if 'language' in sent:
        values['rbcol_language'] = data.language
    if 'purchase_price' in sent:
        values['rbcol_purchase_price'] = _money(data.purchase_price)
    if 'sell_price' in sent:
        values['rbcol_sell_price'] = _money(data.sell_price)
    if 'selling' in sent:
        values['rbcol_selling'] = 'Y' if data.selling else 'N'
        if data.selling:
            if 'sell_qty' not in sent and sell_qty == 0:
                values['rbcol_sell_qty'] = qty
            if values.get('rbcol_sell_price', row.rbcol_sell_price) is None:
                values['rbcol_sell_price'] = _default_sell_price(
                    collection_read.market_price(card, row.rbcol_foil == 'S'))
    values['rbcol_chadat'] = clock.utcnow()

    done = db.session.execute(
        sa.update(RbCollection).where(
            RbCollection.rbcol_id == line_id,
            RbCollection.rbcol_user == user.username,
            RbCollection.rbcol_chadat == row.rbcol_chadat).values(**values)
        .execution_options(synchronize_session=False))
    if done.rowcount != 1:
        db.session.rollback()
        raise StaleLine(line_id)
    db.session.commit()
    return _payload(row, card)


# --- delete --------------------------------------------------------------------------------

def delete_line(user, line_id: int) -> dict:
    """Delete a line; returns it, enough to post it back (undo)."""
    row, card = _owned(user, line_id)
    payload = collection_read.line_payloads([(row, card)])[0]
    db.session.delete(row)
    db.session.commit()
    return payload


# --- split ---------------------------------------------------------------------------------

def split_line(user, line_id: int, data) -> tuple[dict, dict, bool]:
    """Move `data.qty` copies into another line; returns `(source, target, merged)` (S5)."""
    row, card = _owned(user, line_id)
    if data.qty > row.rbcol_quantity - 1:
        raise InsufficientQuantity(row.rbcol_quantity - 1)
    sent = data.model_fields_set
    condition = data.condition if 'condition' in sent else row.rbcol_condition
    language = data.language if 'language' in sent else row.rbcol_language
    purchase = _money(data.purchase_price) if 'purchase_price' in sent else row.rbcol_purchase_price
    selling = data.selling if data.selling is not None else row.rbcol_selling == 'Y'
    sell_price = _money(data.sell_price) if 'sell_price' in sent else row.rbcol_sell_price
    if selling and sell_price is None:
        sell_price = _default_sell_price(collection_read.market_price(card, row.rbcol_foil == 'S'))
    selling_flag = 'Y' if selling else 'N'

    target = _identical(user, row.rbcol_rbset_id, row.rbcol_rbcar_id, row.rbcol_foil, condition,
                        language, purchase, selling_flag, sell_price)
    if target is not None and target.rbcol_id == row.rbcol_id:
        payload = _payload(row, card)          # nothing differs: nothing moves
        return payload, payload, True

    now = clock.utcnow()
    remaining = RbCollection.rbcol_quantity - data.qty
    done = db.session.execute(
        sa.update(RbCollection).where(
            RbCollection.rbcol_id == line_id, RbCollection.rbcol_user == user.username,
            remaining >= 1).values(
            rbcol_quantity=remaining,
            rbcol_sell_qty=sa.case((RbCollection.rbcol_sell_qty > remaining, remaining),
                                   else_=RbCollection.rbcol_sell_qty),
            rbcol_chadat=now).execution_options(synchronize_session=False))
    if done.rowcount != 1:
        db.session.rollback()
        current, _ = _owned(user, line_id)
        raise InsufficientQuantity(current.rbcol_quantity - 1)

    moved_for_sale = data.qty if selling else 0
    if target is not None:
        _add_to(target.rbcol_id, data.qty, moved_for_sale, now)
        merged = True
    else:
        target = RbCollection(
            rbcol_rbset_id=row.rbcol_rbset_id, rbcol_rbcar_id=row.rbcol_rbcar_id,
            rbcol_foil=row.rbcol_foil, rbcol_user=user.username, rbcol_quantity=data.qty,
            rbcol_sell_qty=moved_for_sale, rbcol_selling=selling_flag,
            rbcol_sell_price=sell_price, rbcol_purchase_price=purchase,
            rbcol_condition=condition, rbcol_language=language, rbcol_chadat=now)
        db.session.add(target)
        merged = False
    db.session.commit()
    return _payload(row, card), _payload(target, card), merged


# --- bulk ----------------------------------------------------------------------------------

def _owned_all(user, ids) -> list[tuple[RbCollection, RbCard]]:
    wanted = set(ids)
    found = db.session.execute(
        sa.select(RbCollection, RbCard)
        .join(RbCard, (RbCollection.rbcol_rbset_id == RbCard.rbcar_rbset_id)
              & (RbCollection.rbcol_rbcar_id == RbCard.rbcar_id))
        .where(RbCollection.rbcol_id.in_(wanted), RbCollection.rbcol_user == user.username)
        .order_by(RbCollection.rbcol_id)).all()
    if len(found) != len(wanted):
        raise LineNotFound(sorted(wanted - {row.rbcol_id for row, _ in found}))
    return [(row, card) for row, card in found]


def bulk_set(user, ids, values) -> int:
    """Apply `values` (a `CollectionBulkSet`) to all the lines or to none (S6)."""
    pairs = _owned_all(user, ids)
    sent = values.model_fields_set
    markets = collection_read.markets_for(card for _, card in pairs) \
        if values.selling else {}
    now = clock.utcnow()
    for row, card in pairs:
        if 'condition' in sent:
            row.rbcol_condition = values.condition
        if 'language' in sent:
            row.rbcol_language = values.language
        if 'purchase_price' in sent:
            row.rbcol_purchase_price = _money(values.purchase_price)
        if 'sell_price' in sent:
            row.rbcol_sell_price = _money(values.sell_price)
        if values.selling is not None:
            row.rbcol_selling = 'Y' if values.selling else 'N'
        qty = row.rbcol_quantity
        if values.sell_qty_rule == 'all':
            row.rbcol_sell_qty = qty
        elif values.sell_qty_rule == 'none':
            row.rbcol_sell_qty = 0
        elif values.sell_qty_rule == 'keep_n':
            row.rbcol_sell_qty = max(0, qty - values.keep)
        elif values.selling and row.rbcol_sell_qty == 0:
            row.rbcol_sell_qty = qty
        if values.selling and row.rbcol_sell_price is None:
            row.rbcol_sell_price = _default_sell_price(
                markets.get((row.rbcol_rbset_id, row.rbcol_rbcar_id, row.rbcol_foil == 'S')))
        row.rbcol_chadat = now
    db.session.commit()
    return len(pairs)


def bulk_delete(user, ids) -> list[dict]:
    """Delete all the lines or none; returns them (S6)."""
    pairs = _owned_all(user, ids)
    payloads = collection_read.line_payloads(pairs)
    for row, _ in pairs:
        db.session.delete(row)
    db.session.commit()
    return payloads


# --- keep a playset ------------------------------------------------------------------------

def keep_playset(user, set_id: str, card_id: str, keep: bool) -> dict:
    """Mark or unmark a card name as "keep a playset"; idempotent (S7)."""
    card = _card(set_id, card_id)
    key = catalog.name_key(card.rbcar_name)
    mark = db.session.get(RbKeepPlayset, (user.id, key))
    if keep and mark is None:
        db.session.add(RbKeepPlayset(rbkps_user_id=user.id, rbkps_name_key=key))
    elif not keep and mark is not None:
        db.session.delete(mark)
    try:
        db.session.commit()
    except IntegrityError:          # the same mark was inserted meanwhile: it is there
        db.session.rollback()

    owned = db.session.execute(
        sa.select(RbCollection.rbcol_quantity, RbCollection.rbcol_sell_qty, RbCard.rbcar_name)
        .join(RbCard, (RbCollection.rbcol_rbset_id == RbCard.rbcar_rbset_id)
              & (RbCollection.rbcol_rbcar_id == RbCard.rbcar_id))
        .where(RbCollection.rbcol_user == user.username)).all()
    kept = sum(quantity - for_sale for quantity, for_sale, name in owned
               if catalog.name_key(name) == key)
    size = collection_rules.playset_size(db.session.get(RbUserPrefs, user.id))
    marked = db.session.get(RbKeepPlayset, (user.id, key)) is not None
    return {'name': card.rbcar_name, 'keep_playset': marked, 'kept': kept,
            'playset_size': size, 'playset_short': marked and kept < size}
