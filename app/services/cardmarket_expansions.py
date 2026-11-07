"""Cardmarket expansions (CM-d): every expansion with its products on the latest load and
its mapping to a set of ours, and the map / unmap writes. No Flask request objects.

`rbcm_expansions.rbexp_rbset_id` is a soft FK to `rbset` (NULL = not mapped). The matcher
prefers cards of the mapped set and `products_refresh` gives products the set of their
expansion; prices never depend on it. The writes only change the row: the views audit and
commit, so a failed write leaves nothing behind.
"""
import sqlalchemy as sa

from app import db
from app.models.cardmarket import RbcmExpansion, RbcmProduct
from app.models.set import RbSet
from app.services import cardmarket_log


class NotFound(Exception):
    """The expansion does not exist."""


class NotMapped(Exception):
    """The expansion has no set to unmap."""


def _latest_date():
    return db.session.execute(sa.select(sa.func.max(RbcmProduct.rbprd_date))).scalar()


def _rows(where=()):
    """`(expansion, set name, products, singles, sealed)` rows: unmapped first, then by id.
    One statement: the counts of the latest product date are a grouped subquery."""
    latest = sa.select(sa.func.max(RbcmProduct.rbprd_date)).scalar_subquery()
    counts = (
        sa.select(RbcmProduct.rbprd_id_expansion.label('expansion'),
                  sa.func.count().label('products'),
                  sa.func.sum(sa.case((RbcmProduct.rbprd_type == 'single', 1), else_=0))
                  .label('singles'))
        .where(RbcmProduct.rbprd_date == latest)
        .group_by(RbcmProduct.rbprd_id_expansion)
        .subquery())
    return db.session.execute(
        sa.select(RbcmExpansion, RbSet.rbset_name, counts.c.products, counts.c.singles)
        .outerjoin(RbSet, RbSet.rbset_id == RbcmExpansion.rbexp_rbset_id)
        .outerjoin(counts, counts.c.expansion == RbcmExpansion.rbexp_id)
        .where(*where)
        .order_by(RbcmExpansion.rbexp_rbset_id.is_not(None), RbcmExpansion.rbexp_id)).all()


def _item(row) -> dict:
    expansion, set_name, products, singles = row
    products, singles = products or 0, singles or 0
    return {'id': expansion.rbexp_id, 'name': expansion.rbexp_name,
            'products_count': products, 'singles_count': singles,
            'sealed_count': products - singles,
            'mapped_set_id': expansion.rbexp_rbset_id, 'mapped_set_name': set_name}


def expansion_item(expansion_id: int) -> dict:
    """One expansion as the list shows it."""
    return _item(_rows((RbcmExpansion.rbexp_id == expansion_id,))[0])


def list_expansions(unmapped_only: bool = False) -> dict:
    """`{items, sets, meta: {unmapped, total, date}}`; four statements whatever the size."""
    where = (RbcmExpansion.rbexp_rbset_id.is_(None),) if unmapped_only else ()
    items = [_item(row) for row in _rows(where)]
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
