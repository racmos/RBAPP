"""Owned sealed products (F14-c): the caller's `rbuserproducts` lines, their total and the
writes (add with merge, edit, delete), plus the products value of every user for the daily
snapshot.

The products total is never part of the collection value (F14-R6): nothing here reads or
writes `rbcollection`. Every write is scoped to one user and commits once; a line of another
user is "not found" (404). A merge adds the quantity in SQL
(`rbupr_quantity = rbupr_quantity + n`), never read, added and written back, so two requests
at once cannot lose a copy. Money is rounded half up to cents and P/L follows F3-b
(`product_prices.line_numbers`).
"""
from decimal import ROUND_HALF_UP, Decimal

import sqlalchemy as sa

from app import db
from app.models import RbProducts, RbUserProduct
from app.services.product_list import owned_line, product_summary
from app.services.product_prices import line_numbers, product_price_summaries
from app.utils import clock

CENT = Decimal('0.01')
MAX_QUANTITY = 9999


class UnknownProduct(Exception):
    """No product (a non-single) has this id."""


class LineNotFound(Exception):
    """The line does not exist or is not the user's (always a 404)."""


class QuantityTooHigh(Exception):
    """A merge would take a line past `MAX_QUANTITY` copies."""


def _money(value) -> Decimal | None:
    return None if value is None else Decimal(str(value)).quantize(CENT, ROUND_HALF_UP)


def _eq(column, value):
    return column.is_(None) if value is None else column == value


def _payloads(pairs, user_id) -> list[dict]:
    """`owned_line` with its `ProductSummary` for `(line, product)` pairs: one price statement;
    `owned_qty` adds up all the user's lines of each product (one more statement)."""
    pairs = list(pairs)
    prices = product_price_summaries({product.rbpdt_id_product for _, product in pairs})
    owned = _owned_in(user_id, {product.rbpdt_id_product for _, product in pairs})
    payloads = []
    for row, product in pairs:
        price = prices.get(product.rbpdt_id_product)
        summary = product_summary(product, price=price,
                                  owned_qty=owned.get(product.rbpdt_id_product, 0))
        payloads.append(owned_line(row, (price or {}).get('value'), summary))
    return payloads


def _owned_in(user_id, product_ids) -> dict[int, int]:
    if not product_ids:
        return {}
    return dict(db.session.execute(
        sa.select(RbUserProduct.rbupr_id_product, sa.func.sum(RbUserProduct.rbupr_quantity))
        .where(RbUserProduct.rbupr_user_id == user_id,
               RbUserProduct.rbupr_id_product.in_(sorted(product_ids)))
        .group_by(RbUserProduct.rbupr_id_product)).all())


def _pairs(user_id, line_id=None):
    query = (sa.select(RbUserProduct, RbProducts)
             .join(RbProducts, RbProducts.rbpdt_id_product == RbUserProduct.rbupr_id_product)
             .where(RbUserProduct.rbupr_user_id == user_id))
    if line_id is not None:
        query = query.where(RbUserProduct.rbupr_id == line_id)
    return [(row, product) for row, product in db.session.execute(query).all()]


def _owned(user, line_id: int) -> tuple[RbUserProduct, RbProducts]:
    found = _pairs(user.id, line_id)
    if not found:
        raise LineNotFound(line_id)
    return found[0]


def _payload(user, line_id: int) -> dict:
    db.session.expire_all()
    return _payloads(_pairs(user.id, line_id), user.id)[0]


# --- read ------------------------------------------------------------------------------------

def list_lines(user) -> dict:
    """`{items: [line], total: {value, lines, qty, unpriced}}` (S3): lines ordered by product
    name, then id; `total.value` adds up the priced line values."""
    pairs = sorted(_pairs(user.id), key=lambda pair: (
        (pair[1].rbpdt_name or '').casefold(), pair[0].rbupr_id))
    prices = product_price_summaries({product.rbpdt_id_product for _, product in pairs})
    owned: dict[int, int] = {}
    for row, product in pairs:
        owned[product.rbpdt_id_product] = owned.get(product.rbpdt_id_product, 0) + \
            row.rbupr_quantity

    items = []
    value = Decimal(0)
    unpriced = 0
    for row, product in pairs:
        price = prices.get(product.rbpdt_id_product)
        line_value, _, _ = line_numbers((price or {}).get('value'), row.rbupr_quantity,
                                        row.rbupr_purchase_price)
        if line_value is None:
            unpriced += 1
        else:
            value += line_value
        summary = product_summary(product, price=price,
                                  owned_qty=owned[product.rbpdt_id_product])
        items.append(owned_line(row, (price or {}).get('value'), summary))
    return {
        'items': items,
        'total': {
            'value': float(value.quantize(CENT, ROUND_HALF_UP)),
            'lines': len(pairs),
            'qty': sum(row.rbupr_quantity for row, _ in pairs),
            'unpriced': unpriced,
        },
    }


def products_values() -> dict[int, Decimal]:
    """`{user id: value of their priced product lines}` for every user with a line (F14-c S6),
    priced like `list_lines` (each line rounded half up, then added up). Two statements."""
    rows = db.session.execute(sa.select(
        RbUserProduct.rbupr_user_id, RbUserProduct.rbupr_id_product,
        RbUserProduct.rbupr_quantity)).all()
    prices = product_price_summaries({row.rbupr_id_product for row in rows})
    values: dict[int, Decimal] = {}
    for row in rows:
        price = prices.get(row.rbupr_id_product)
        line_value, _, _ = line_numbers((price or {}).get('value'), row.rbupr_quantity, None)
        values[row.rbupr_user_id] = values.get(row.rbupr_user_id, Decimal(0)) + (
            line_value or Decimal(0))
    return {user_id: value.quantize(CENT, ROUND_HALF_UP) for user_id, value in values.items()}


# --- writes ----------------------------------------------------------------------------------

def add_line(user, data) -> tuple[dict, bool]:
    """Add copies of a product; a line of the same product and purchase price (NULL-safe) gets
    the quantity in SQL (`merged`). The merged line keeps its note, or takes the new one when
    it had none. Returns `(line, merged)` (S4)."""
    product = db.session.get(RbProducts, data.product_id)
    if product is None or product.rbpdt_type != 'nonsingle':
        raise UnknownProduct(data.product_id)
    purchase = _money(data.purchase_price)
    now = clock.utcnow()
    existing = db.session.execute(
        sa.select(RbUserProduct.rbupr_id).where(
            RbUserProduct.rbupr_user_id == user.id,
            RbUserProduct.rbupr_id_product == data.product_id,
            _eq(RbUserProduct.rbupr_purchase_price, purchase),
        ).order_by(RbUserProduct.rbupr_id).limit(1)).scalar()
    if existing is not None:
        done = db.session.execute(
            sa.update(RbUserProduct)
            .where(RbUserProduct.rbupr_id == existing,
                   RbUserProduct.rbupr_quantity + data.quantity <= MAX_QUANTITY)
            .values(rbupr_quantity=RbUserProduct.rbupr_quantity + data.quantity,
                    rbupr_note=sa.func.coalesce(RbUserProduct.rbupr_note, data.note),
                    rbupr_updated_at=now)
            .execution_options(synchronize_session=False))
        if done.rowcount != 1:
            db.session.rollback()
            raise QuantityTooHigh(existing)
        db.session.commit()
        return _payload(user, existing), True
    row = RbUserProduct(rbupr_user_id=user.id, rbupr_id_product=data.product_id,
                        rbupr_quantity=data.quantity, rbupr_purchase_price=purchase,
                        rbupr_note=data.note, rbupr_created_at=now, rbupr_updated_at=now)
    db.session.add(row)
    db.session.commit()
    return _payload(user, row.rbupr_id), False


def edit_line(user, line_id: int, data) -> dict:
    """Change the sent fields of one of the user's lines (S4); `null` clears the purchase price
    or the note. No merge: two lines may end up with the same price."""
    row, _ = _owned(user, line_id)
    sent = data.model_fields_set
    if 'quantity' in sent:
        row.rbupr_quantity = data.quantity
    if 'purchase_price' in sent:
        row.rbupr_purchase_price = _money(data.purchase_price)
    if 'note' in sent:
        row.rbupr_note = data.note
    row.rbupr_updated_at = clock.utcnow()
    db.session.commit()
    return _payload(user, line_id)


def delete_line(user, line_id: int) -> dict:
    """Delete one of the user's lines; returns it (with its product, whose `owned_qty` no
    longer counts the line), enough to post it back."""
    row, product = _owned(user, line_id)
    db.session.delete(row)
    db.session.flush()
    payload = _payloads([(row, product)], user.id)[0]
    db.session.commit()
    return payload
