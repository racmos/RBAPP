"""The daily Cardmarket load (F4-b): what the `daily_prices` job does after
`CardmarketLoader().run()`. No Flask request objects.

The loader and the matcher are used as the admin endpoints use them; this
module only reads what they wrote (`rbcm_load_history`, `rbcm_products`,
`rbcm_price`) and what `auto_match(dry_run=True)` proposes, and links the
clear cases itself (D-F4-2).
"""
from collections import Counter, defaultdict

import sqlalchemy as sa
from sqlalchemy.orm import aliased

from app import db
from app.models.cardmarket import (RbcmIgnored, RbcmLoadHistory, RbcmPrice, RbcmProduct,
                                   RbcmProductCardMap)
from app.services import cardmarket_matcher as matcher

# The three files of a load, in the order the loader downloads them.
FILE_TYPES = ('price_guide', 'singles', 'nonsingles')
# Items kept in the job result; `review_total` counts them all (D-F4-10).
REVIEW_LIMIT = 200
# The matcher's confidence for the pairs it proposes.
MATCHER_CONFIDENCE = 0.7


class ValidationFailed(Exception):
    """The load ran but what it left does not pass the S3 checks."""


def _count(query) -> int:
    return db.session.execute(query).scalar_one()


def _latest_history(date: str) -> dict[str, RbcmLoadHistory]:
    """The last history row of each file type on `date` (a re-run adds rows)."""
    latest = {}
    for row in db.session.execute(
            sa.select(RbcmLoadHistory).where(RbcmLoadHistory.rblh_date == date)
            .order_by(RbcmLoadHistory.rblh_id)).scalars():
        latest[row.rblh_file_type] = row
    return latest


def validate_load(date: str) -> dict:
    """The validation record of the load of `date` (YYYYMMDD); raises
    ValidationFailed when a file has no history row or no price row exists."""
    history = _latest_history(date)
    for file_type in FILE_TYPES:
        if file_type not in history:
            raise ValidationFailed(f'Validation failed: {file_type} missing for {date}')

    price_rows = _count(sa.select(sa.func.count()).select_from(RbcmPrice)
                        .where(RbcmPrice.rbprc_date == date))
    if price_rows == 0:
        raise ValidationFailed(f'Validation failed: no price rows for {date}')

    earlier = aliased(RbcmProduct)
    today = sa.select(sa.func.count()).select_from(RbcmProduct).where(
        RbcmProduct.rbprd_date == date)
    new = today.where(~sa.exists().where(
        earlier.rbprd_id_product == RbcmProduct.rbprd_id_product,
        earlier.rbprd_date < date))
    return {
        'date': date,
        'files': {file_type: {'status': history[file_type].rblh_status,
                              'rows': history[file_type].rblh_rows}
                  for file_type in FILE_TYPES},
        'price_rows': price_rows,
        'products_today': _count(today),
        'new_products': _count(new),
    }


def _proposals() -> tuple[dict[int, tuple], Counter, int]:
    """What `auto_match(dry_run=True)` would link: {product id: (set, card,
    foil)}, how many products each slot was proposed for, and the total."""
    proposed = matcher.auto_match(dry_run=True)
    pairs = {s['id_product']: (s['rbset_id'], s['rbcar_id'], s['rbpcm_foil'])
             for s in proposed['samples']}
    return pairs, Counter(pairs.values()), proposed['assigned']


class _Candidates:
    """Candidate cards of a product, found as `auto_match` finds them: the
    normalised names of its metacard group, then its expansion's set."""

    def __init__(self):
        self.cards_by_norm = matcher._build_card_index()
        self.exp_to_set = matcher._get_expansion_to_set_map()

    def set_of(self, product):
        return self.exp_to_set.get(product.rbprd_id_expansion or 0)

    def of(self, product, group):
        names = {matcher.normalize_name(p.rbprd_name) for p in group if p.rbprd_name}
        names.discard('')
        found, seen = [], set()
        for name in names:
            for card in self.cards_by_norm.get(name, []):
                key = (card.rbcar_rbset_id, card.rbcar_id)
                if key not in seen:
                    seen.add(key)
                    found.append(card)
        if not found:
            return []
        partition = [p for p in group if self.set_of(p) == self.set_of(product)]
        return list(matcher._get_partition_candidates(found, partition, self.exp_to_set))


def _review_item(product, reason: str, candidates) -> dict:
    return {
        'product_id': product.rbprd_id_product,
        'name': product.rbprd_name,
        'expansion_id': product.rbprd_id_expansion,
        'reason': reason,
        'candidates': [{'set': c.rbcar_rbset_id, 'id': c.rbcar_id, 'name': c.rbcar_name}
                       for c in sorted(candidates,
                                       key=lambda c: (c.rbcar_rbset_id, c.rbcar_id))],
    }


def match_clear_cases(date: str) -> dict:
    """Link the clear cases among the unmapped singles of `date` and list the
    rest for review (F4-b S4/S5).

    Clear case: the only unmapped product of its metacard group, with exactly
    one candidate card that still has a free slot, and a slot proposed by
    `auto_match` for no other product. It is linked to that proposal
    (`match_type='auto'`, confidence 0.7). Every other unmapped single gets a
    review reason: `ignored_pair`, `no_candidates`, `conflict` (slot taken or
    proposed twice) or `ambiguous` (several products or candidate cards).
    """
    pairs, slot_uses, proposed = _proposals()
    mapped_ids = set(db.session.execute(sa.select(RbcmProductCardMap.rbpcm_id_product)).scalars())
    taken = set(db.session.execute(sa.select(
        RbcmProductCardMap.rbpcm_rbset_id, RbcmProductCardMap.rbpcm_rbcar_id,
        RbcmProductCardMap.rbpcm_foil)).all())
    ignored = set(db.session.execute(sa.select(
        RbcmIgnored.rbig_id_product, RbcmIgnored.rbig_name)).all())
    products = [p for p in db.session.execute(
        sa.select(RbcmProduct).where(RbcmProduct.rbprd_date == date,
                                     RbcmProduct.rbprd_type == 'single')
        .order_by(RbcmProduct.rbprd_id_product)).scalars()
        if p.rbprd_id_product not in mapped_ids]

    groups = defaultdict(list)
    for p in products:
        if (p.rbprd_id_product, p.rbprd_name) not in ignored and p.rbprd_id_metacard:
            groups[p.rbprd_id_metacard].append(p)

    candidates = _Candidates()
    review, links = [], []
    for p in products:
        if (p.rbprd_id_product, p.rbprd_name) in ignored:
            review.append(_review_item(p, 'ignored_pair', candidates.of(p, [p])))
            continue
        if not p.rbprd_id_metacard:           # the matcher skips it: nothing to compare
            review.append(_review_item(p, 'no_candidates', []))
            continue
        group = groups[p.rbprd_id_metacard]
        cards = candidates.of(p, group)
        free = [c for c in cards if matcher._expand_slots(c, taken=taken)]
        slot = pairs.get(p.rbprd_id_product)
        if not cards:
            reason = 'no_candidates'
        elif not free:
            reason = 'conflict'
        elif len(group) > 1 or len(free) > 1 or slot is None:
            reason = 'ambiguous'
        elif slot_uses[slot] > 1:
            reason = 'conflict'
        else:
            links.append((p.rbprd_id_product, slot))
            continue
        review.append(_review_item(p, reason, cards))

    for id_product, (set_id, car_id, foil) in links:
        db.session.add(RbcmProductCardMap(
            rbpcm_id_product=id_product, rbpcm_rbset_id=set_id, rbpcm_rbcar_id=car_id,
            rbpcm_foil=foil, rbpcm_match_type='auto', rbpcm_confidence=MATCHER_CONFIDENCE))
    db.session.commit()
    return {
        'auto_match': {'linked': len(links), 'proposed': proposed, 'review': len(review)},
        'review': review[:REVIEW_LIMIT],
        'review_total': len(review),
    }
