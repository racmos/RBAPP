"""Product prices (F14-b S1, D-F14-4).

The ONE place that decides what a sealed product is worth: the first of
`rbprc_avg7`, `rbprc_trend`, `rbprc_low` that is not NULL and not 0. Foil
columns are never read. The 7/30-day changes use the reference-row rule and
the rounding of the card `price_summaries` (`app/services/pricing.py`).
"""
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from sqlalchemy import Float, cast

from app import db
from app.models.cardmarket import RbcmPrice
from app.services.pricing import _day, _reference

_ORDER = ('rbprc_avg7', 'rbprc_trend', 'rbprc_low')
CENT = Decimal('0.01')
TENTH = Decimal('0.1')


def product_price(row) -> tuple[Optional[float], Optional[str]]:
    """`(value, source)` of one `rbcm_price` row (or anything with the three
    columns), or `(None, None)`; `source` is `avg7`, `trend` or `low`."""
    if not row:
        return None, None
    for column in _ORDER:
        value = getattr(row, column)
        if value:                       # NULL and 0 are both "missing"
            return float(value), column.removeprefix('rbprc_')
    return None, None


class _Row:
    """The price columns the product reads use, without ORM overhead."""

    __slots__ = ('rbprc_id_product', 'rbprc_date', 'rbprc_avg7', 'rbprc_trend',
                 'rbprc_low', 'rbprc_avg30')

    def __init__(self, id_product, date, avg7, trend, low, avg30):
        self.rbprc_id_product = id_product
        self.rbprc_date = date
        self.rbprc_avg7 = avg7
        self.rbprc_trend = trend
        self.rbprc_low = low
        self.rbprc_avg30 = avg30


def price_rows(ids) -> dict[int, list[_Row]]:
    """`{id: [rows ascending by date]}` for the products that have rows: one statement."""
    ids = sorted(set(ids))
    if not ids:
        return {}
    columns = (RbcmPrice.rbprc_id_product, RbcmPrice.rbprc_date,
               cast(RbcmPrice.rbprc_avg7, Float), cast(RbcmPrice.rbprc_trend, Float),
               cast(RbcmPrice.rbprc_low, Float), cast(RbcmPrice.rbprc_avg30, Float))
    by_product = {}
    for values in db.session.query(*columns).filter(RbcmPrice.rbprc_id_product.in_(ids)):
        row = _Row(*values)
        by_product.setdefault(row.rbprc_id_product, []).append(row)
    for rows in by_product.values():
        rows.sort(key=lambda row: row.rbprc_date or '')
    return by_product


def _change(now_row, ref_row):
    now, _ = product_price(now_row)
    then, _ = product_price(ref_row)
    if now is None or then is None or then == 0:
        return None
    return round((now - then) / then * 100, 1)


def summary_from_rows(rows) -> Optional[dict]:
    """The `price` object of a `ProductSummary` from rows ascending by date, or None."""
    if not rows:
        return None
    latest = rows[-1]
    latest_day = _day(latest.rbprc_date)
    value, source = product_price(latest)
    return {
        'value': value,
        'source': source,
        'change_7d_pct': _change(latest, _reference(rows, latest_day, 7)),
        'change_30d_pct': _change(latest, _reference(rows, latest_day, 30)),
        'as_of': latest_day.isoformat(),
    }


def product_price_summaries(ids) -> dict[int, Optional[dict]]:
    """`{id: price summary or None}` for every id: at most one SQL statement."""
    ids = list(ids)
    rows = price_rows(ids)
    return {product_id: summary_from_rows(rows.get(product_id)) for product_id in ids}


def line_numbers(price: Optional[float], quantity: int, purchase) -> tuple:
    """`(value, pl_abs, pl_pct)` of an owned product line (F14-c), as `Decimal`s or None, the
    F3-b way: value = price x quantity to cents; P/L only with a price and a purchase price
    above 0, the percentage to one decimal; all rounded half up."""
    if price is None:
        return None, None, None
    market = Decimal(str(price))
    value = (market * quantity).quantize(CENT, ROUND_HALF_UP)
    if purchase is None or purchase <= 0:
        return value, None, None
    purchase = Decimal(str(purchase))
    gain = market - purchase
    return (value, (gain * quantity).quantize(CENT, ROUND_HALF_UP),
            (gain / purchase * 100).quantize(TENTH, ROUND_HALF_UP))
