"""
Cardmarket price resolution (PRC-1, PRC-2, D12).

The ONE place that decides which price column a card is worth. The collection
list/export and the deck view both go through `resolve_price`; no route may
pick `rbprc_*` columns by its own rule.

Fallback chain (a missing price is worse than an approximate one):

  premium (rarity rare / epic / showcase) or foil 'S':
      avg7_foil -> avg7 -> low_foil -> low
  anything else (common, uncommon, unknown or empty rarity, non-foil):
      avg7 -> avg7_foil -> low -> low_foil

A value that is NULL or 0 counts as missing (R5). A row where every value is
missing has no price: the result is None, never 0.0.
"""
from typing import Optional

from sqlalchemy import func

from app import db
from app.models.cardmarket import RbcmPrice, RbcmProduct, RbcmProductCardMap

PREMIUM_RARITIES = frozenset({'rare', 'epic', 'showcase'})

_PREMIUM_ORDER = ('rbprc_avg7_foil', 'rbprc_avg7', 'rbprc_low_foil', 'rbprc_low')
_COMMON_ORDER = ('rbprc_avg7', 'rbprc_avg7_foil', 'rbprc_low', 'rbprc_low_foil')


def _chain(order, price_row):
    """The first available (value, source) of an order, or `(None, None)`."""
    if not price_row:
        return None, None
    for column in order:
        value = getattr(price_row, column)
        if value:                       # NULL and 0 are both "missing"
            return float(value), column.removeprefix('rbprc_')
    return None, None


def resolve_price_with_source(row, *, rarity: Optional[str],
                              foil: Optional[str] = 'N') -> tuple[Optional[float], Optional[str]]:
    """The unit price of one card and the column that won, or `(None, None)`.

    `row` is an RbcmPrice (or anything with the four `rbprc_*` attributes)
    or None; `source` is the column name without the `rbprc_` prefix.
    `foil` is 'S' for foil; any other value is non-foil.
    """
    premium = (rarity or '').lower() in PREMIUM_RARITIES or foil == 'S'
    return _chain(_PREMIUM_ORDER if premium else _COMMON_ORDER, row)


def resolve_price(price_row, *, rarity: Optional[str], foil: Optional[str]) -> Optional[float]:
    """The unit price of one card from its `rbcm_price` row, or None.

    `price_row` is an RbcmPrice (or anything with the four `rbprc_*` attributes)
    or None. `foil` is 'S' for foil; any other value is non-foil.
    """
    return resolve_price_with_source(price_row, rarity=rarity, foil=foil)[0]


def canonical_product_id(rbset_id: str, rbcar_id: str, foil: str = 'N') -> Optional[int]:
    """The Cardmarket idProduct that prices a card, or None if it is unmapped.

    Same rule as the collection query (`collection._collection_query`): the
    product is MIN(id_product) among the mappings of the requested foil, or
    among the unclassified ones (foil NULL: rare/epic or legacy). With neither,
    any mapping of the card is used as an approximation.
    """
    base = db.session.query(func.min(RbcmProductCardMap.rbpcm_id_product)).filter(
        RbcmProductCardMap.rbpcm_rbset_id == rbset_id,
        RbcmProductCardMap.rbpcm_rbcar_id == rbcar_id)

    exact = base.filter(RbcmProductCardMap.rbpcm_foil == foil).scalar()
    if exact is not None:
        return exact
    unclassified = base.filter(RbcmProductCardMap.rbpcm_foil.is_(None)).scalar()
    if unclassified is not None:
        return unclassified
    return base.scalar()


def _mapped_index(mapping_rows):
    """`{(set_id, card_id): [(foil, id_product), ...]}` for one lookup per card."""
    index = {}
    for row_set, row_card, row_foil, product in mapping_rows:
        index.setdefault((row_set, row_card), []).append((row_foil, product))
    return index


def _mapped_products(by_card, set_id: str, card_id: str, foil_slot: str):
    """Lowest Cardmarket id for one card and foil slot, or None (S4 rule)."""
    exact, unclassified, any_match = None, None, None
    for row_foil, product in by_card.get((set_id, card_id), ()):
        if row_foil == foil_slot and (exact is None or product < exact):
            exact = product
        if row_foil is None and (unclassified is None or product < unclassified):
            unclassified = product
        if any_match is None or product < any_match:
            any_match = product
    if exact is not None:
        return exact
    return unclassified if unclassified is not None else any_match


def _day(text):
    """'YYYYMMDD' to a date."""
    import datetime as _datetime
    return _datetime.date(int(text[0:4]), int(text[4:6]), int(text[6:8]))


class _PriceRow:
    """The six price columns `price_summaries` reads, without ORM overhead."""

    __slots__ = ('rbprc_id_product', 'rbprc_date', 'rbprc_avg7',
                 'rbprc_avg7_foil', 'rbprc_low', 'rbprc_low_foil')

    def __init__(self, id_product, date, avg7, avg7_foil, low, low_foil):
        self.rbprc_id_product = id_product
        self.rbprc_date = date
        self.rbprc_avg7 = avg7
        self.rbprc_avg7_foil = avg7_foil
        self.rbprc_low = low
        self.rbprc_low_foil = low_foil


def _price_row(*values):
    return _PriceRow(*values)


def _reference(rows, latest_day, days):
    """The newest row dated on or before `latest_day - days`, or None."""
    import datetime as _datetime
    target = (latest_day - _datetime.timedelta(days=days)).strftime('%Y%m%d')
    older = [row for row in rows if (row.rbprc_date or '') <= target]
    return max(older, key=lambda row: row.rbprc_date) if older else None


def _trend(now_row, ref_row, rarity, foil):
    now, _ = resolve_price_with_source(now_row, rarity=rarity, foil=foil)
    then, _ = resolve_price_with_source(ref_row, rarity=rarity, foil=foil)
    if now is None or then is None or then == 0:
        return None
    return round((now - then) / then * 100, 1)


def price_summaries(items):
    """One batched price summary per card (S6): at most two SQL statements.

    `items` are `(set_id, card_id, rarity, foilable)` tuples. Returns
    `{(set_id, card_id): summary or None}`; unmapped cards map to None.
    """
    items = list(items)
    if not items:
        return {}
    # The mapping table is tiny: one scan beats a 1000-pair tuple IN (S6).
    mapping_rows = db.session.query(
        RbcmProductCardMap.rbpcm_rbset_id,
        RbcmProductCardMap.rbpcm_rbcar_id,
        RbcmProductCardMap.rbpcm_foil,
        RbcmProductCardMap.rbpcm_id_product,
    ).all()

    by_card = _mapped_index(mapping_rows)
    wanted = set()
    slots = {}
    for set_id, card_id, _, foilable in items:
        kinds = ['N'] + (['S'] if foilable else [])
        slots[(set_id, card_id)] = kinds
        for slot in kinds:
            product = _mapped_products(by_card, set_id, card_id, slot)
            if product is not None:
                wanted.add(product)

    from sqlalchemy import cast as _cast, Float as _Float
    by_product = {}
    if wanted:
        columns = (RbcmPrice.rbprc_id_product, RbcmPrice.rbprc_date,
                   _cast(RbcmPrice.rbprc_avg7, _Float).label('rbprc_avg7'),
                   _cast(RbcmPrice.rbprc_avg7_foil, _Float).label('rbprc_avg7_foil'),
                   _cast(RbcmPrice.rbprc_low, _Float).label('rbprc_low'),
                   _cast(RbcmPrice.rbprc_low_foil, _Float).label('rbprc_low_foil'))
        for values in db.session.query(*columns).filter(
                RbcmPrice.rbprc_id_product.in_(sorted(wanted))).all():
            row = _price_row(*values)
            by_product.setdefault(row.rbprc_id_product, []).append(row)
    for rows in by_product.values():
        rows.sort(key=lambda row: row.rbprc_date or '')

    result = {}
    for set_id, card_id, rarity, foilable in items:
        products = {slot: _mapped_products(by_card, set_id, card_id, slot)
                    for slot in slots[(set_id, card_id)]}
        if all(product is None for product in products.values()):
            result[(set_id, card_id)] = None
            continue
        n_rows = by_product.get(products.get('N')) or []
        s_rows = by_product.get(products.get('S')) or [] if foilable else []
        latest_n = n_rows[-1] if n_rows else None
        latest_s = s_rows[-1] if s_rows else None
        market, market_source = resolve_price_with_source(latest_n, rarity=rarity, foil='N')
        if foilable:
            market_foil, market_foil_source = resolve_price_with_source(
                latest_s, rarity=rarity, foil='S')
        else:
            market_foil, market_foil_source = None, None
        latest = latest_n or latest_s
        if latest is None:
            result[(set_id, card_id)] = {
                'market': None, 'market_source': None,
                'market_foil': None, 'market_foil_source': None,
                'trend_7d_pct': None, 'trend_30d_pct': None, 'as_of': None}
            continue
        latest_day = _day(latest.rbprc_date)
        ref_7 = _reference(n_rows, latest_day, 7)
        ref_30 = _reference(n_rows, latest_day, 30)
        result[(set_id, card_id)] = {
            'market': market, 'market_source': market_source,
            'market_foil': market_foil, 'market_foil_source': market_foil_source,
            'trend_7d_pct': _trend(latest_n, ref_7, rarity, 'N'),
            'trend_30d_pct': _trend(latest_n, ref_30, rarity, 'N'),
            'as_of': latest_day.isoformat(),
        }
    return result


def latest_price_for_card(rbset_id: str, rbcar_id: str, *, rarity: Optional[str],
                          foil: str = 'N') -> Optional[float]:
    """The price of a card from the newest `rbcm_price` row of its product, or None."""
    id_product = canonical_product_id(rbset_id, rbcar_id, foil)
    if id_product is None:
        return None
    row = (RbcmPrice.query.filter_by(rbprc_id_product=id_product)
           .order_by(RbcmPrice.rbprc_date.desc()).first())
    return resolve_price(row, rarity=rarity, foil=foil)


def price_as_of() -> Optional[str]:
    """The date (`YYYY-MM-DD`) of the newest `rbcm_price` row, or None when there is none."""
    latest = db.session.query(func.max(RbcmPrice.rbprc_date)).scalar()
    if not latest:
        return None
    return f'{latest[0:4]}-{latest[4:6]}-{latest[6:8]}'


def product_names(items):
    """`{(set_id, card_id, foil): Cardmarket product name}` for `(set_id, card_id, foil)` items
    (`foil` is 'S' or 'N'), using the same product choice as the prices (exact foil mapping,
    else unclassified, else any) and the newest `rbcm_products` row of that product. Cards
    without a mapped product or name are left out. At most two SQL statements (F3-d)."""
    items = list(items)
    if not items:
        return {}
    by_card = _mapped_index(db.session.query(
        RbcmProductCardMap.rbpcm_rbset_id, RbcmProductCardMap.rbpcm_rbcar_id,
        RbcmProductCardMap.rbpcm_foil, RbcmProductCardMap.rbpcm_id_product).all())
    chosen = {item: _mapped_products(by_card, item[0], item[1], item[2]) for item in items}
    wanted = sorted({product for product in chosen.values() if product is not None})
    newest = {}
    if wanted:
        for product, name, day in db.session.query(
                RbcmProduct.rbprd_id_product, RbcmProduct.rbprd_name,
                RbcmProduct.rbprd_date).filter(RbcmProduct.rbprd_id_product.in_(wanted)):
            if name and (product not in newest or (day or '') > newest[product][0]):
                newest[product] = (day or '', name)
    return {item: newest[product][1] for item, product in chosen.items()
            if product in newest}
