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
from app.models.cardmarket import RbcmPrice, RbcmProductCardMap

PREMIUM_RARITIES = frozenset({'rare', 'epic', 'showcase'})

_PREMIUM_ORDER = ('rbprc_avg7_foil', 'rbprc_avg7', 'rbprc_low_foil', 'rbprc_low')
_COMMON_ORDER = ('rbprc_avg7', 'rbprc_avg7_foil', 'rbprc_low', 'rbprc_low_foil')


def resolve_price(price_row, *, rarity: Optional[str], foil: Optional[str]) -> Optional[float]:
    """The unit price of one card from its `rbcm_price` row, or None.

    `price_row` is an RbcmPrice (or anything with the four `rbprc_*` attributes)
    or None. `foil` is 'S' for foil; any other value is non-foil.
    """
    if not price_row:
        return None
    premium = (rarity or '').lower() in PREMIUM_RARITIES or foil == 'S'
    for column in (_PREMIUM_ORDER if premium else _COMMON_ORDER):
        value = getattr(price_row, column)
        if value:                       # NULL and 0 are both "missing"
            return float(value)
    return None


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


def latest_price_for_card(rbset_id: str, rbcar_id: str, *, rarity: Optional[str],
                          foil: str = 'N') -> Optional[float]:
    """The price of a card from the newest `rbcm_price` row of its product, or None."""
    id_product = canonical_product_id(rbset_id, rbcar_id, foil)
    if id_product is None:
        return None
    row = (RbcmPrice.query.filter_by(rbprc_id_product=id_product)
           .order_by(RbcmPrice.rbprc_date.desc()).first())
    return resolve_price(row, rarity=rarity, foil=foil)
