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
# Why an `ambiguous` review item is ambiguous, when it is known (CM-m S1): its card group has
# more products on Cardmarket than free cards of its own set (a printing is missing).
MORE_PRINTINGS = 'more_printings_than_cards'


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


def _review_item(product, reason: str, candidates, detail=None) -> dict:
    item = {
        'product_id': product.rbprd_id_product,
        'name': product.rbprd_name,
        'expansion_id': product.rbprd_id_expansion,
        'reason': reason,
        'candidates': [{'set': c.rbcar_rbset_id, 'id': c.rbcar_id, 'name': c.rbcar_name}
                       for c in sorted(candidates,
                                       key=lambda c: (c.rbcar_rbset_id, c.rbcar_id))],
    }
    if detail is not None:
        item['reason_detail'] = MORE_PRINTINGS
        item['detail'] = detail
    return item


def _printings_detail(set_id, cards, rivals, in_set, taken) -> dict | None:
    """CM-m S1: `{products, cards, set_id}` when the product's card group has more unmapped
    products in its set (`rivals`) than free slots on the cards of that set: a printing is
    missing from the catalog. `products` counts every product of the group in the set (linked
    ones too), `cards` the cards of the set. None otherwise (no card of the set, or room)."""
    own = [card for card in cards if card.rbcar_rbset_id == set_id]
    if not own:
        return None
    free = sum(len(matcher._expand_slots(card, taken=taken)) for card in own)
    if len(rivals) <= free:
        return None
    return {'products': in_set, 'cards': len(own), 'set_id': set_id}


def _owns_the_slot(product, slot, users, candidates) -> bool:
    """Several products are proposed for one slot. The product of the card's own set owns it
    when it is the only one that comes from that set: the others reached the card through the
    promo-to-base fallback (an Origins Promo product with no promo card in our catalog proposes
    the Origins card), so they are the conflict, not the Origins product."""
    owners = [one for one in users if candidates.set_of(one) == slot[0]]
    return len(owners) == 1 and owners[0] is product


def _paired_by_rank(rivals, free, prices, taken) -> bool:
    """Several products of one set for several cards of that set: they can be paired by rank
    when there is exactly one single-slot card (rare, epic, showcase, rune: no foil twin) per
    product, the cards differ in rank (rarity, then the `a` / `s` variants) and the products
    can be ordered: the priced ones differ in price and at most one has no price. The cheaper
    product then is the card of the lower rank and the unpriced one the highest (CM-m S5,
    owner decision 2026-11-24), as `auto_match` proposes (owner rule: two printings of one
    name in one set, the lower number is the lower rarity and the dearer product is the
    higher one). Anything less certain is ambiguous."""
    slots = [matcher._expand_slots(card, taken=taken) for card in free]
    if len(free) != len(rivals) or any(len(one) != 1 for one in slots):
        return False
    if any(len(matcher._expand_slots(card)) != 1 for card in free):
        return False                      # a common or uncommon has a foil twin: not certain
    ranks = [matcher.card_rank_key(card)[0] for card in free]
    cost = [prices.get(product.rbprd_id_product) or 0.0 for product in rivals]
    priced = [value for value in cost if value > 0]
    return (len(set(ranks)) == len(ranks) and len(set(priced)) == len(priced)
            and len(cost) - len(priced) <= 1)


def classify_unmapped(date: str) -> dict:
    """Decide, without writing, what `match_clear_cases` does with the unmapped
    singles of `date`: `{links: [(product id, (set, card, foil))], review: [every
    review item], proposed: pairs auto_match proposes}` (CM-b preview and review).
    An `ambiguous` item whose card group has more products than free cards of its own set
    also carries `reason_detail: more_printings_than_cards` and `detail {products, cards,
    set_id}` (CM-m S1).

    Clear case: the only unmapped product of its metacard group in its set (the set of
    its expansion; products of other sets do not compete), with exactly
    one candidate card that still has a free slot, or several products paired with as many
    single-slot cards by rank and price (`_paired_by_rank`), and a slot proposed by
    `auto_match` for no other product. Every other unmapped single gets a
    review reason: `ignored_pair`, `no_candidates`, `conflict` (slot taken or
    proposed twice) or `ambiguous` (several products or candidate cards).
    """
    pairs, slot_uses, proposed = _proposals()
    prices = matcher._get_latest_prices()
    mapped_ids = set(db.session.execute(sa.select(RbcmProductCardMap.rbpcm_id_product)).scalars())
    taken = set(db.session.execute(sa.select(
        RbcmProductCardMap.rbpcm_rbset_id, RbcmProductCardMap.rbpcm_rbcar_id,
        RbcmProductCardMap.rbpcm_foil)).all())
    ignored = set(db.session.execute(sa.select(
        RbcmIgnored.rbig_id_product, RbcmIgnored.rbig_name)).all())
    singles = db.session.execute(
        sa.select(RbcmProduct).where(RbcmProduct.rbprd_date == date,
                                     RbcmProduct.rbprd_type == 'single')
        .order_by(RbcmProduct.rbprd_id_product)).scalars().all()
    products = [p for p in singles if p.rbprd_id_product not in mapped_ids]

    by_id = {p.rbprd_id_product: p for p in products}
    slot_users = defaultdict(list)           # slot -> the products `auto_match` proposes for it
    for id_product, one_slot in pairs.items():
        if id_product in by_id:
            slot_users[one_slot].append(by_id[id_product])

    groups = defaultdict(list)
    for p in products:
        if (p.rbprd_id_product, p.rbprd_name) not in ignored and p.rbprd_id_metacard:
            groups[p.rbprd_id_metacard].append(p)

    candidates = _Candidates()
    # every product of a card group per set, linked ones too (the counts of CM-m S1)
    group_size = Counter((p.rbprd_id_metacard, candidates.set_of(p)) for p in singles
                         if p.rbprd_id_metacard
                         and (p.rbprd_id_product, p.rbprd_name) not in ignored)
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
        # The matcher pairs products with cards inside one set (the one of the product's
        # expansion), so the products that compete for the same cards are those of the group
        # that share this product's set, not the whole metacard: a lone Origins product is clear
        # even when the metacard also has Spiritforged products.
        rivals = [q for q in group if candidates.set_of(q) == candidates.set_of(p)]
        if not cards:
            reason = 'no_candidates'
        elif not free:
            reason = 'conflict'
        elif len(rivals) == 1 and len(free) > 1:
            reason = 'ambiguous'
        elif len(rivals) > 1 and not _paired_by_rank(rivals, free, prices, taken):
            reason = 'ambiguous'
        elif slot is None:
            reason = 'ambiguous'
        elif slot_uses[slot] > 1 and not _owns_the_slot(p, slot, slot_users[slot], candidates):
            reason = 'conflict'
        else:
            links.append((p.rbprd_id_product, slot))
            continue
        detail = None
        if reason == 'ambiguous':
            own_set = candidates.set_of(p)
            detail = _printings_detail(own_set, cards, rivals,
                                       group_size[(p.rbprd_id_metacard, own_set)], taken)
        review.append(_review_item(p, reason, cards, detail))
    return {'links': links, 'review': review, 'proposed': proposed}


def add_links(links) -> None:
    """Add the clear-case links `[(product id, (set, card, foil))]` to the session
    (`match_type='auto'`, confidence 0.7); the caller commits."""
    for id_product, (set_id, car_id, foil) in links:
        db.session.add(RbcmProductCardMap(
            rbpcm_id_product=id_product, rbpcm_rbset_id=set_id, rbpcm_rbcar_id=car_id,
            rbpcm_foil=foil, rbpcm_match_type='auto', rbpcm_confidence=MATCHER_CONFIDENCE))


def match_clear_cases(date: str) -> dict:
    """Link the clear cases among the unmapped singles of `date` and list the
    rest for review (F4-b S4/S5); the decision is `classify_unmapped`.

    A clear case is linked to the `auto_match` proposal (`match_type='auto'`,
    confidence 0.7).
    """
    decided = classify_unmapped(date)
    links, review = decided['links'], decided['review']
    add_links(links)
    db.session.commit()
    return {
        'auto_match': {'linked': len(links), 'proposed': decided['proposed'],
                       'review': len(review)},
        'review': review[:REVIEW_LIMIT],
        'review_total': len(review),
    }
