"""Products read API (F14-b S2-S5): list with facets, detail and price history.

Reads `rbproducts` (F14-a), `rbset` (facet order), `rbcm_price` and the caller's
`rbuserproducts` lines (F14-c). Only `nonsingle` rows are products; hidden ones are
shown only to users who own them. Filtering and ordering run in Python, like
`card_list`.
"""
import datetime as _datetime
import math

import sqlalchemy as sa

from app import db
from app.models import RbProducts, RbSet, RbUserProduct
from app.models.cardmarket import PRODUCT_KINDS
from app.schemas.validators import ProductListQuery
from app.services import catalog, pricing
from app.services.product_prices import (line_numbers, price_rows, product_price,
                                         product_price_summaries, summary_from_rows)

_RANGE_DAYS = {'30d': 30, '90d': 90, '1y': 365}
_SORT_VALUES = {'price': 'value', 'change_7d': 'change_7d_pct',
                'change_30d': 'change_30d_pct'}


def owned_quantities(user_id) -> dict[int, int]:
    """`{product id: copies the user owns}` over all their lines (one statement); a product
    the user does not own is absent."""
    return dict(db.session.execute(
        sa.select(RbUserProduct.rbupr_id_product, sa.func.sum(RbUserProduct.rbupr_quantity))
        .where(RbUserProduct.rbupr_user_id == user_id)
        .group_by(RbUserProduct.rbupr_id_product)).all())


def _float(value):
    return float(value) if value is not None else None


def _money(value):
    return float(value) if value is not None else None


def _iso_utc(moment):
    return moment.strftime('%Y-%m-%dT%H:%M:%SZ') if moment is not None else None


def owned_line(row, price_value, product=None) -> dict:
    """One `rbuserproducts` line: `{id, product?, quantity, purchase_price, note, value, pl_abs,
    pl_pct, updated_at}`. `product` (a `ProductSummary`) is included when given; the product
    detail `lines` leave it out. `price_value` is the product's current price or None."""
    value, pl_abs, pl_pct = line_numbers(price_value, row.rbupr_quantity,
                                         row.rbupr_purchase_price)
    line = {'id': row.rbupr_id}
    if product is not None:
        line['product'] = product
    line.update({
        'quantity': row.rbupr_quantity,
        'purchase_price': _money(row.rbupr_purchase_price),
        'note': row.rbupr_note,
        'value': _money(value),
        'pl_abs': _money(pl_abs),
        'pl_pct': _money(pl_pct),
        'updated_at': _iso_utc(row.rbupr_updated_at),
    })
    return line


def _iso_day(text):
    return f'{text[0:4]}-{text[4:6]}-{text[6:8]}' if text else None


def _visible_products(owned_ids):
    """Non-singles that are not hidden, plus the hidden ones in `owned_ids`."""
    return db.session.query(RbProducts).filter(
        RbProducts.rbpdt_type == 'nonsingle',
        sa.or_(RbProducts.rbpdt_hidden.is_(False),
               RbProducts.rbpdt_id_product.in_(list(owned_ids))),
    ).all()


def _visible_product(product_id, user_id):
    """The product when it is a non-single that is not hidden or that the user owns, else
    None. Ownership is read only for a hidden product."""
    product = db.session.get(RbProducts, product_id)
    if product is None or product.rbpdt_type != 'nonsingle':
        return None
    if product.rbpdt_hidden and not db.session.execute(
            sa.select(RbUserProduct.rbupr_id).where(
                RbUserProduct.rbupr_user_id == user_id,
                RbUserProduct.rbupr_id_product == product_id).limit(1)).first():
        return None
    return product


def product_summary(product, *, price, owned_qty) -> dict:
    """The `ProductSummary` of one product (key order is part of the contract)."""
    return {
        'id': product.rbpdt_id_product,
        'name': product.rbpdt_name,
        'kind': product.rbpdt_kind,
        'category': product.rbpdt_category,
        'set_id': product.rbpdt_id_set,
        'image_src': None,                  # F14-d serves /riftbound/media/products/<file>
        'listed': bool(product.rbpdt_listed),
        'price': price,
        'owned_qty': owned_qty,
    }


def _matches(query: ProductListQuery, product, owned, *, skip=None) -> bool:
    """Every filter of `query`, except the facet named by `skip`; `owned` is
    `owned_quantities` of the caller."""
    if query.listed == 'true' and not product.rbpdt_listed:
        return False
    if query.owned != 'any' and (product.rbpdt_id_product in owned) != (query.owned == 'owned'):
        return False
    q = (query.q or '').strip().casefold()
    if q and q not in (product.rbpdt_name or '').casefold():
        return False
    if skip != 'kind' and query.kind and \
            (product.rbpdt_kind or '').casefold() not in {k.casefold() for k in query.kind}:
        return False
    if skip != 'set' and query.set and \
            (product.rbpdt_id_set or '').casefold() not in {s.casefold() for s in query.set}:
        return False
    return True


def _facet(products, attr, known_order) -> dict:
    """Counts of a facet: known values in `known_order`, then the rest by name; NULL skipped."""
    counts = {}
    for product in products:
        value = getattr(product, attr)
        if value is not None:
            counts[value] = counts.get(value, 0) + 1
    ordered = [(key, counts[key]) for key in known_order if key in counts]
    known = set(known_order)
    ordered += sorted(((key, count) for key, count in counts.items() if key not in known),
                      key=lambda item: item[0].casefold())
    return dict(ordered)


def _name_key(product):
    return ((product.rbpdt_name or '').casefold(), product.rbpdt_id_product)


def _sorted(products, query: ProductListQuery, prices) -> list:
    by_name = sorted(products, key=_name_key, reverse=(query.sort == 'name'
                                                       and query.dir == 'desc'))
    if query.sort == 'name':
        return by_name
    field = _SORT_VALUES[query.sort]

    def value(product):
        return (prices.get(product.rbpdt_id_product) or {}).get(field)

    with_value = [p for p in by_name if value(p) is not None]
    nulls = [p for p in by_name if value(p) is None]
    # Stable sort over the name order: equal values keep the name tiebreak.
    with_value.sort(key=value, reverse=(query.dir == 'desc'))
    return with_value + nulls


def list_products(query: ProductListQuery, user_id) -> dict:
    """`{items: [ProductSummary], meta: {page, per_page, total, pages, facets, price_as_of}}`
    for the user `user_id` (their `owned_qty`, the `owned` filter, their hidden products)."""
    owned = owned_quantities(user_id)
    products = _visible_products(owned)
    set_rank = catalog.set_order(db.session.query(RbSet).all())
    set_order = sorted(set_rank, key=lambda s: (set_rank[s], s))

    facets = {
        'kind': _facet([p for p in products if _matches(query, p, owned, skip='kind')],
                       'rbpdt_kind', PRODUCT_KINDS),
        'set': _facet([p for p in products if _matches(query, p, owned, skip='set')],
                      'rbpdt_id_set', set_order),
    }
    matched = [p for p in products if _matches(query, p, owned)]

    # Price sorts need every match priced; otherwise the page is enough (one statement each).
    prices = (product_price_summaries(p.rbpdt_id_product for p in matched)
              if query.sort != 'name' else {})
    ordered = _sorted(matched, query, prices)

    total = len(ordered)
    pages = math.ceil(total / query.per_page) if total else 0
    start = (query.page - 1) * query.per_page
    page = ordered[start:start + query.per_page]
    ids = [p.rbpdt_id_product for p in page]
    if query.sort == 'name':
        prices = product_price_summaries(ids)

    return {
        'items': [product_summary(p, price=prices.get(p.rbpdt_id_product),
                                  owned_qty=owned.get(p.rbpdt_id_product, 0))
                  for p in page],
        'meta': {
            'page': query.page,
            'per_page': query.per_page,
            'total': total,
            'pages': pages,
            'facets': facets,
            'price_as_of': pricing.price_as_of(),
        },
    }


def get_product(product_id, user_id):
    """`ProductSummary` + `{description, columns, lines}`, or None (404); `lines` are the
    caller's lines of the product (`owned_line` without `product`), oldest first."""
    product = _visible_product(product_id, user_id)
    if product is None:
        return None
    lines = db.session.execute(
        sa.select(RbUserProduct).where(RbUserProduct.rbupr_user_id == user_id,
                                       RbUserProduct.rbupr_id_product == product_id)
        .order_by(RbUserProduct.rbupr_id)).scalars().all()
    rows = price_rows([product_id]).get(product_id) or []
    latest = rows[-1] if rows else None
    price = summary_from_rows(rows)
    detail = product_summary(product, price=price,
                             owned_qty=sum(line.rbupr_quantity for line in lines))
    detail.update({
        'description': product.rbpdt_description,
        'columns': ({'avg7': _float(latest.rbprc_avg7), 'trend': _float(latest.rbprc_trend),
                     'low': _float(latest.rbprc_low), 'avg30': _float(latest.rbprc_avg30)}
                    if latest is not None else None),
        'lines': [owned_line(line, (price or {}).get('value')) for line in lines],
    })
    return detail


def get_product_prices(product_id, range_, user_id):
    """`{range, points}` ascending inside the range window, or None (404)."""
    if _visible_product(product_id, user_id) is None:
        return None
    rows = price_rows([product_id]).get(product_id) or []
    days = _RANGE_DAYS.get(range_)
    if days is not None and rows:
        latest_day = pricing._day(rows[-1].rbprc_date)
        cutoff = (latest_day - _datetime.timedelta(days=days)).strftime('%Y%m%d')
        rows = [row for row in rows if (row.rbprc_date or '') >= cutoff]
    return {
        'range': range_,
        'points': [{
            'date': _iso_day(row.rbprc_date),
            'value': product_price(row)[0],
            'avg7': _float(row.rbprc_avg7),
            'trend': _float(row.rbprc_trend),
            'low': _float(row.rbprc_low),
        } for row in rows],
    }
