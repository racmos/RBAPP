"""Cardmarket expansions (CM-d): every expansion with its products on the latest load and
its mapping to a set of ours, and the map / unmap writes. No Flask request objects.

`rbcm_expansions.rbexp_rbset_id` is a soft FK to `rbset` (NULL = not mapped). The matcher
prefers cards of the mapped set and `products_refresh` gives products the set of their
expansion; prices never depend on it. The writes only change the row: the views audit and
commit, so a failed write leaves nothing behind.

Cardmarket names few expansions, so each item carries what tells it apart: sample products,
the price range of its singles, the first day Cardmarket added one of its products and the
set of ours its linked cards suggest.
"""
import re

import sqlalchemy as sa

from app import db
from app.models.cardmarket import RbcmExpansion, RbcmPrice, RbcmProduct, RbcmProductCardMap
from app.models.set import RbSet
from app.services import cardmarket_log

# The sample products of an expansion: its dearest singles, then its dearest sealed products
SAMPLE_SINGLES, SAMPLE_SEALED = 3, 2

_ISO_DAY = re.compile(r'\d{4}-\d{2}-\d{2}')


class NotFound(Exception):
    """The expansion does not exist."""


class NotMapped(Exception):
    """The expansion has no set to unmap."""


def _latest_date():
    return db.session.execute(sa.select(sa.func.max(RbcmProduct.rbprd_date))).scalar()


def _latest():
    return sa.select(sa.func.max(RbcmProduct.rbprd_date)).scalar_subquery()


def _on_latest(select, expansion_id=None):
    """`select` over the `rbcm_products` of the latest date, of one expansion or all."""
    select = select.where(RbcmProduct.rbprd_date == _latest())
    if expansion_id is not None:
        select = select.where(RbcmProduct.rbprd_id_expansion == expansion_id)
    return select


def _priced(select, expansion_id=None):
    """`_on_latest` with the low price of the same day (outer join: unpriced stay)."""
    return _on_latest(
        select.select_from(RbcmProduct).outerjoin(RbcmPrice, sa.and_(
            RbcmPrice.rbprc_date == RbcmProduct.rbprd_date,
            RbcmPrice.rbprc_id_product == RbcmProduct.rbprd_id_product)),
        expansion_id)


def _money(value):
    return None if value is None else float(value)


def _rows(expansion_id=None, unmapped_only=False):
    """`(expansion, set name, products, singles, min low, max low, first added)` rows:
    unmapped first, then by id. One statement: the figures of the latest product date are
    a grouped subquery; the low prices are of its singles only."""
    single = RbcmProduct.rbprd_type == 'single'
    single_low = sa.case((single, RbcmPrice.rbprc_low))
    counts = (_priced(
        sa.select(RbcmProduct.rbprd_id_expansion.label('expansion'),
                  sa.func.count().label('products'),
                  sa.func.sum(sa.case((single, 1), else_=0)).label('singles'),
                  sa.func.min(single_low).label('low_min'),
                  sa.func.max(single_low).label('low_max'),
                  sa.func.min(RbcmProduct.rbprd_date_added).label('added')))
        .group_by(RbcmProduct.rbprd_id_expansion)
        .subquery())
    where = []
    if expansion_id is not None:
        where.append(RbcmExpansion.rbexp_id == expansion_id)
    if unmapped_only:
        where.append(RbcmExpansion.rbexp_rbset_id.is_(None))
    return db.session.execute(
        sa.select(RbcmExpansion, RbSet.rbset_name, counts.c.products, counts.c.singles,
                  counts.c.low_min, counts.c.low_max, counts.c.added)
        .outerjoin(RbSet, RbSet.rbset_id == RbcmExpansion.rbexp_rbset_id)
        .outerjoin(counts, counts.c.expansion == RbcmExpansion.rbexp_id)
        .where(*where)
        .order_by(RbcmExpansion.rbexp_rbset_id.is_not(None), RbcmExpansion.rbexp_id)).all()


def _samples(expansion_id=None) -> dict[int, list[dict]]:
    """Per expansion, the `SAMPLE_SINGLES` dearest singles then the `SAMPLE_SEALED` dearest
    sealed products of the latest date (low price of that day, unpriced last, then by
    product id). One statement: a window rank per expansion and type."""
    single = RbcmProduct.rbprd_type == 'single'
    low = RbcmPrice.rbprc_low
    ranked = _priced(
        sa.select(RbcmProduct.rbprd_id_expansion.label('expansion'),
                  RbcmProduct.rbprd_id_product.label('id_product'),
                  RbcmProduct.rbprd_name.label('name'), RbcmProduct.rbprd_type.label('type'),
                  low.label('low'), single.label('single'),
                  sa.func.row_number().over(
                      partition_by=(RbcmProduct.rbprd_id_expansion, single),
                      order_by=(low.is_(None), low.desc(), RbcmProduct.rbprd_id_product))
                  .label('rank')),
        expansion_id).where(RbcmProduct.rbprd_id_expansion.is_not(None)).subquery()
    rows = db.session.execute(
        sa.select(ranked.c.expansion, ranked.c.id_product, ranked.c.name, ranked.c.type,
                  ranked.c.low)
        .where(sa.or_(sa.and_(ranked.c.single, ranked.c.rank <= SAMPLE_SINGLES),
                      sa.and_(sa.not_(ranked.c.single), ranked.c.rank <= SAMPLE_SEALED)))
        .order_by(ranked.c.expansion, ranked.c.single.desc(), ranked.c.rank)).all()
    samples: dict[int, list[dict]] = {}
    for expansion, id_product, name, type_, price in rows:
        samples.setdefault(expansion, []).append(
            {'id_product': id_product, 'name': name, 'type': type_,
             'low_price': _money(price)})
    return samples


NO_SUGGESTION = {'suggested_set_id': None, 'suggested_set_name': None,
                 'suggested_confidence': None, 'suggested_count': None, 'linked_count': 0}


def _suggestions(expansion_id=None) -> dict[int, dict]:
    """Per expansion, the set of ours its card links of the latest date point to most often
    (a tie goes to the lower set id) and how many of its products are linked. One
    statement: links counted per expansion and set."""
    rows = db.session.execute(_on_latest(
        sa.select(RbcmProduct.rbprd_id_expansion, RbcmProductCardMap.rbpcm_rbset_id,
                  RbSet.rbset_name, sa.func.count())
        .join(RbcmProductCardMap,
              RbcmProductCardMap.rbpcm_id_product == RbcmProduct.rbprd_id_product)
        .outerjoin(RbSet, RbSet.rbset_id == RbcmProductCardMap.rbpcm_rbset_id), expansion_id)
        .group_by(RbcmProduct.rbprd_id_expansion, RbcmProductCardMap.rbpcm_rbset_id,
                  RbSet.rbset_name)).all()
    per_expansion: dict[int, list] = {}
    for expansion, set_id, set_name, count in rows:
        per_expansion.setdefault(expansion, []).append((set_id, set_name, count))
    suggestions = {}
    for expansion, sets in per_expansion.items():
        linked = sum(count for _, _, count in sets)
        ours = sorted((one for one in sets if one[1] is not None),
                      key=lambda one: (-one[2], one[0]))
        suggestion = {**NO_SUGGESTION, 'linked_count': linked}
        if ours:
            set_id, set_name, count = ours[0]
            suggestion.update(suggested_set_id=set_id, suggested_set_name=set_name,
                              suggested_confidence=round(count / linked, 3),
                              suggested_count=count)
        suggestions[expansion] = suggestion
    return suggestions


def _first_seen(added: str | None) -> str | None:
    """The day of a Cardmarket `dateAdded` ("2025-07-14 16:11:32"); null when not a date."""
    return added[:10] if added and _ISO_DAY.match(added) else None


def _items(expansion_id=None, unmapped_only=False) -> list[dict]:
    """The items of the list; three statements whatever the number of expansions."""
    rows = _rows(expansion_id, unmapped_only)
    samples = _samples(expansion_id)
    suggestions = _suggestions(expansion_id)
    items = []
    for expansion, set_name, products, singles, low_min, low_max, added in rows:
        products, singles = products or 0, singles or 0
        items.append({
            'id': expansion.rbexp_id, 'name': expansion.rbexp_name,
            'products_count': products, 'singles_count': singles,
            'sealed_count': products - singles,
            'mapped_set_id': expansion.rbexp_rbset_id, 'mapped_set_name': set_name,
            'sample_products': samples.get(expansion.rbexp_id, []),
            'price_range': (None if low_min is None
                            else {'min': _money(low_min), 'max': _money(low_max)}),
            'first_seen': _first_seen(added),
            **suggestions.get(expansion.rbexp_id, NO_SUGGESTION)})
    return items


def expansion_item(expansion_id: int) -> dict:
    """One expansion as the list shows it."""
    return _items(expansion_id)[0]


def list_expansions(unmapped_only: bool = False) -> dict:
    """`{items, sets, meta: {unmapped, total, date}}`; six statements whatever the size."""
    items = _items(unmapped_only=unmapped_only)
    sets = db.session.execute(
        sa.select(RbSet.rbset_id, RbSet.rbset_name, RbSet.rbset_outdat)
        .order_by(RbSet.rbset_outdat.is_(None), RbSet.rbset_outdat.desc(), RbSet.rbset_id)
    ).all()
    date = _latest_date()
    return {
        'items': items,
        'sets': [{'id': set_id, 'name': name,
                  'release_date': released.isoformat() if released else None}
                 for set_id, name, released in sets],
        'meta': {'unmapped': cardmarket_log.unmapped_expansions_count(), 'total': len(items),
                 'date': cardmarket_log.iso(date) if date else None},
    }


def get(expansion_id: int) -> RbcmExpansion:
    expansion = db.session.get(RbcmExpansion, expansion_id)
    if expansion is None:
        raise NotFound(expansion_id)
    return expansion


def map_to(expansion: RbcmExpansion, set_id: str) -> str | None:
    """Map the expansion to `set_id` (a set that exists); returns the previous set id."""
    previous = expansion.rbexp_rbset_id
    expansion.rbexp_rbset_id = set_id
    db.session.flush()
    return previous


def unmap(expansion_id: int) -> tuple[RbcmExpansion, str]:
    """Remove the mapping; returns the expansion and the set it was mapped to."""
    expansion = get(expansion_id)
    previous = expansion.rbexp_rbset_id
    if previous is None:
        raise NotMapped(expansion_id)
    expansion.rbexp_rbset_id = None
    db.session.flush()
    return expansion, previous
