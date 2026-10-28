"""Products read API (F14-b S2-S5): list with facets, detail and price history.

Reads only `rbproducts` (F14-a), `rbset` (facet order) and `rbcm_price`. Only
`nonsingle` rows are products and hidden ones are never shown (F14-c adds
"unless owned"). Filtering and ordering run in Python, like `card_list`.
"""
import datetime as _datetime
import math

from app import db
from app.models import RbProducts, RbSet
from app.models.cardmarket import PRODUCT_KINDS
from app.schemas.validators import ProductListQuery
from app.services import catalog, pricing
from app.services.product_prices import (price_rows, product_price, product_price_summaries,
                                         summary_from_rows)

_RANGE_DAYS = {'30d': 30, '90d': 90, '1y': 365}
_SORT_VALUES = {'price': 'value', 'change_7d': 'change_7d_pct',
                'change_30d': 'change_30d_pct'}


def owned_quantities(username, ids) -> dict[int, int]:
    """`{id: copies the user owns}`. Always 0 until F14-c, which reads `rbuserproducts`."""
    return {product_id: 0 for product_id in ids}


def _float(value):
    return float(value) if value is not None else None


def _iso_day(text):
    return f'{text[0:4]}-{text[4:6]}-{text[6:8]}' if text else None


def _visible_products():
    return db.session.query(RbProducts).filter(
        RbProducts.rbpdt_type == 'nonsingle',
        RbProducts.rbpdt_hidden.is_(False),
    ).all()


def _visible_product(product_id):
    """The product when it is a visible non-single, else None."""
    product = db.session.get(RbProducts, product_id)
    if product is None or product.rbpdt_type != 'nonsingle' or product.rbpdt_hidden:
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


def _matches(query: ProductListQuery, product, *, skip=None) -> bool:
    """Every filter of `query`, except the facet named by `skip`."""
    if query.listed == 'true' and not product.rbpdt_listed:
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
    # `owned=owned|missing` behave as `any` until F14-c.
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


def list_products(query: ProductListQuery, username) -> dict:
    """`{items: [ProductSummary], meta: {page, per_page, total, pages, facets, price_as_of}}`."""
    products = _visible_products()
    set_rank = catalog.set_order(db.session.query(RbSet).all())
    set_order = sorted(set_rank, key=lambda s: (set_rank[s], s))

    facets = {
        'kind': _facet([p for p in products if _matches(query, p, skip='kind')],
                       'rbpdt_kind', PRODUCT_KINDS),
        'set': _facet([p for p in products if _matches(query, p, skip='set')],
                      'rbpdt_id_set', set_order),
    }
    matched = [p for p in products if _matches(query, p)]

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
    owned = owned_quantities(username, ids)

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


def get_product(product_id, username):
    """`ProductSummary` + `{description, columns, lines}`, or None (404)."""
    product = _visible_product(product_id)
    if product is None:
        return None
    rows = price_rows([product_id]).get(product_id) or []
    latest = rows[-1] if rows else None
    detail = product_summary(product, price=summary_from_rows(rows),
                             owned_qty=owned_quantities(username, [product_id])[product_id])
    detail.update({
        'description': product.rbpdt_description,
        'columns': ({'avg7': _float(latest.rbprc_avg7), 'trend': _float(latest.rbprc_trend),
                     'low': _float(latest.rbprc_low), 'avg30': _float(latest.rbprc_avg30)}
                    if latest is not None else None),
        'lines': [],                        # F14-c: the user's rbuserproducts lines
    })
    return detail


def get_product_prices(product_id, range_):
    """`{range, points}` ascending inside the range window, or None (404)."""
    if _visible_product(product_id) is None:
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
