"""Missing printings (CM-m): card groups with more Cardmarket products than catalog cards.

Cardmarket lists three printings of each Radiance legend (Rare, Showcase and a third, dearer
one) while Riot's gallery, so the catalog, has two (`RAD-141`, `RAD-169`): two unlinked
products for one free card is ambiguous by design (owner feedback 2026-11-24). Owner answer
(2026-11-24): the third printing is the SIGNED card, id `<id>s` (`RAD-169s`).

`plan` reads the latest load: the single products of the expansions mapped to a set, grouped
as the matcher groups them (`(set, Cardmarket card group)`; products without a card group are
skipped as the matcher skips them; ignored products do not count). The cards of a group are the
cards of that set found by the matcher's name index (`_build_card_index`, legends by their
tags too). A group is listed when its unlinked products outnumber the free slots
(`_expand_slots`, a common or uncommon has two) of those cards, the signed copy of the
highest-rank printing left aside. Promo sets (base id + X) and PLAT are left out: their missing
cards are the promo-card plan's (`app/services/promo_cards.py`).

Each group proposes ONE new card, the signed copy of the highest-rank plain printing `H` (an
all-digit id, by `card_rank_key`): id `H.id + 's'`, every card field of `H` but the image
(`promo_cards.CLONE_FIELDS`), rarity `Showcase`. A group gets no proposal (`manual`) when it
is unclear: no plain printing, `H` is a common or uncommon (its products are a normal and a
foil one), `H` has a letter variant other than the signed one, the unlinked products exceed
the free slots by more than one, the id is taken by a card of another name or the copy does
not pass the card checks. `exists`: the signed card is in the catalog already (Auto-match
links it). `create` makes the proposed cards through `catalog_admin.create_cards` (the checks
of `POST /admin/cards`); it never links (Auto-match does, CM-m S6). No Flask request objects;
the view audits and commits.
"""
import re
from collections import defaultdict

import sqlalchemy as sa
from pydantic import ValidationError

from app import db
from app.models.card import RbCard
from app.models.cardmarket import RbcmExpansion, RbcmIgnored, RbcmProduct, RbcmProductCardMap
from app.models.set import RbSet
from app.schemas.admin import AdminCardCreate
from app.services import cardmarket_matcher as matcher
from app.services import catalog_admin
from app.services.cardmarket_log import iso
from app.services.promo_cards import CLONE_FIELDS, PLATED_SET, base_of

SIGNED_SUFFIX = 's'
SIGNED_RARITY = 'Showcase'

CREATE, EXISTS, MANUAL = 'create', 'exists', 'manual'
# Why a group has its status: the proposed card is a copy of `H` (`clone`) or is in the catalog
# (`in_catalog`); a manual group has no all-digit printing (`no_plain_printing`), a common or
# uncommon top printing (`foil_pair`), a letter variant of `H` other than the signed one
# (`letter_variant`), more than one extra product (`several_extra_products`), the proposed id
# held by a card of another name (`id_taken`) or a copy that fails the card checks
# (`invalid_base`).
CLONE, IN_CATALOG = 'clone', 'in_catalog'
NO_PLAIN, FOIL_PAIR, LETTER_VARIANT, SEVERAL_EXTRA, ID_TAKEN, INVALID_BASE = (
    'no_plain_printing', 'foil_pair', 'letter_variant', 'several_extra_products', 'id_taken',
    'invalid_base')

_PLAIN_ID = re.compile(r'^\d+$')


class ItemsRefused(Exception):
    """Some cards of a create call are not proposed by the current list (`unknown`, as
    `SET-ID`); nothing is written."""

    def __init__(self, message: str, unknown: list):
        super().__init__(message)
        self.message, self.unknown = message, unknown


def _ref(set_id: str, card_id: str) -> str:
    return f'{set_id}-{card_id}'


def _card(card) -> dict:
    return {'set_id': card.rbcar_rbset_id, 'card_id': card.rbcar_id, 'name': card.rbcar_name,
            'rarity': card.rbcar_rarity}


def _unique(cards) -> list:
    seen, result = set(), []
    for card in cards:
        key = (card.rbcar_rbset_id, card.rbcar_id)
        if key not in seen:
            seen.add(key)
            result.append(card)
    return result


class _Load:
    """One read of the latest load: products, links, ignored pairs, sets, cards and prices.
    Eight statements whatever the number of products, groups and sets."""

    def __init__(self):
        self.date = db.session.execute(sa.select(sa.func.max(RbcmProduct.rbprd_date))).scalar()
        self.sets, self.products, self.links, self.cards, self.prices = {}, [], {}, [], {}
        if self.date is None:
            return
        exp_to_set = dict(db.session.execute(
            sa.select(RbcmExpansion.rbexp_id, RbcmExpansion.rbexp_rbset_id)
            .where(RbcmExpansion.rbexp_rbset_id.isnot(None))).all())
        self.sets = {row.rbset_id: row for row in db.session.execute(sa.select(RbSet)).scalars()}
        wanted = {set_id for set_id in set(exp_to_set.values())
                  if set_id in self.sets and set_id != PLATED_SET
                  and base_of(set_id) not in self.sets}
        exps = [exp for exp, set_id in exp_to_set.items() if set_id in wanted]
        if not exps:
            return
        ignored = sa.exists().where(RbcmIgnored.rbig_id_product == RbcmProduct.rbprd_id_product,
                                    RbcmIgnored.rbig_name == RbcmProduct.rbprd_name)
        rows = db.session.execute(
            sa.select(RbcmProduct).where(
                RbcmProduct.rbprd_date == self.date, RbcmProduct.rbprd_type == 'single',
                RbcmProduct.rbprd_id_metacard.isnot(None),
                RbcmProduct.rbprd_id_expansion.in_(exps), ~ignored)
            .order_by(RbcmProduct.rbprd_id_product)).scalars().all()
        self.products = [(exp_to_set[p.rbprd_id_expansion], p) for p in rows]
        self.links = {row.rbpcm_id_product: row for row in db.session.execute(
            sa.select(RbcmProductCardMap)).scalars()}
        self.cards = db.session.execute(
            sa.select(RbCard).where(RbCard.rbcar_rbset_id.in_(wanted))).scalars().all()
        self.prices = matcher._get_latest_prices([p.rbprd_id_product for p in rows])

    def price(self, product):
        value = self.prices.get(product.rbprd_id_product)
        return float(value) if value else None

    def taken(self) -> set:
        return {(link.rbpcm_rbset_id, link.rbpcm_rbcar_id, link.rbpcm_foil)
                for link in self.links.values()}


def _groups(load: _Load) -> list[dict]:
    """The listed groups with their decision, by set id, then name, then card group."""
    by_set = defaultdict(list)
    for card in load.cards:
        by_set[card.rbcar_rbset_id].append(card)
    index = {set_id: matcher._build_card_index(cards) for set_id, cards in by_set.items()}
    ids = {set_id: {card.rbcar_id.lower(): card for card in cards}
           for set_id, cards in by_set.items()}
    taken = load.taken()
    grouped = defaultdict(list)
    for set_id, product in load.products:
        grouped[(set_id, product.rbprd_id_metacard)].append(product)

    result = []
    for (set_id, metacard), products in grouped.items():
        names = {matcher.normalize_name(p.rbprd_name) for p in products} - {''}
        cards = _unique(card for name in sorted(names)
                        for card in index.get(set_id, {}).get(name, []))
        if not cards:
            continue
        group = _decide(load, set_id, metacard, products, cards, ids.get(set_id, {}), taken)
        if group is not None:
            result.append(group)
    return sorted(result, key=lambda g: (g['set_id'], g['name'].lower(), g['metacard']))


def _decide(load, set_id, metacard, products, cards, set_ids, taken) -> dict | None:
    """One group, or None when its unlinked products fit the free slots of its cards."""
    cards = sorted(cards, key=matcher.card_rank_key)
    plain = [card for card in cards if _PLAIN_ID.match(card.rbcar_id or '')]
    top = plain[-1] if plain else None
    key = f'{top.rbcar_id}{SIGNED_SUFFIX}'.lower() if top is not None else None
    signed = set_ids.get(key) if key is not None else None
    base = [card for card in cards if card is not signed]
    free = sum(len(matcher._expand_slots(card, taken=taken)) for card in base)
    unlinked = [p for p in products if p.rbprd_id_product not in load.links]
    if len(unlinked) <= free:
        return None
    variants = [] if top is None else [
        card_id for card_id in set_ids
        if card_id != key and re.match(rf'^{re.escape(top.rbcar_id.lower())}[a-z]+$', card_id)]

    clone, proposed = None, None
    if top is None:
        status, reason = MANUAL, NO_PLAIN
    elif len(matcher._expand_slots(top)) != 1:
        status, reason = MANUAL, FOIL_PAIR
    elif variants:
        status, reason = MANUAL, LETTER_VARIANT
    elif len(unlinked) - free != 1:
        status, reason = MANUAL, SEVERAL_EXTRA
    elif signed is not None and signed in cards:
        status, reason = EXISTS, IN_CATALOG
        proposed = {'set_id': set_id, 'card_id': signed.rbcar_id, 'rarity': signed.rbcar_rarity}
    elif signed is not None:
        status, reason = MANUAL, ID_TAKEN
    else:
        clone = _clone(top, set_id, key)
        if clone is None:
            status, reason = MANUAL, INVALID_BASE
        else:
            status, reason = CREATE, CLONE
            proposed = {'set_id': set_id, 'card_id': clone.card_id, 'rarity': SIGNED_RARITY}

    ordered = sorted(products, key=lambda p: (matcher.price_order(load.price(p)),
                                              p.rbprd_id_product))
    return {
        'set_id': set_id, 'metacard': metacard, 'name': ordered[0].rbprd_name,
        'products': [{'id': p.rbprd_id_product, 'name': p.rbprd_name, 'price': load.price(p),
                      'linked': _link(load.links.get(p.rbprd_id_product))} for p in ordered],
        'cards': [_card(card) for card in cards],
        'base': _card(top) if top is not None else None,
        'proposed': proposed, 'status': status, 'reason': reason,
        '_clone': clone,
        '_unlinked': [p.rbprd_id_product for p in ordered
                      if p.rbprd_id_product not in load.links],
    }


def _link(link) -> dict | None:
    if link is None:
        return None
    return {'set_id': link.rbpcm_rbset_id, 'card_id': link.rbpcm_rbcar_id,
            'foil': link.rbpcm_foil}


def _clone(top: RbCard, set_id: str, key: str):
    """The `AdminCardCreate` of the signed copy of `top`, or None when it fails the checks
    (an id over 10 characters, a field out of range)."""
    fields = {field: getattr(top, catalog_admin.card_column(field)) for field in CLONE_FIELDS}
    fields['rarity'] = SIGNED_RARITY
    try:
        return AdminCardCreate(set_id=set_id, card_id=key, **fields)
    except ValidationError:
        return None


def _public(group: dict) -> dict:
    return {key: value for key, value in group.items()
            if not key.startswith('_') and key != 'set_id'}


def plan() -> dict:
    """`{date, sets: [{set_id, set_name, groups}], summary {groups, cards_to_create, exists,
    manual}}`; each group `{metacard, name, products [{id, name, price, linked}] (by price,
    unpriced last), cards [{set_id, card_id, name, rarity}] (by rank), base (the printing
    copied, or null), proposed {set_id, card_id, rarity} | null, status, reason}`. Writes
    nothing; nine statements (with the session user) whatever the size."""
    load = _Load()
    found = _groups(load)
    by_set = defaultdict(list)
    for group in found:
        by_set[group['set_id']].append(_public(group))
    count = defaultdict(int)
    for group in found:
        count[group['status']] += 1
    return {
        'date': iso(load.date) if load.date else None,
        'sets': [{'set_id': set_id, 'set_name': load.sets[set_id].rbset_name,
                  'groups': groups} for set_id, groups in sorted(by_set.items())],
        'summary': {'groups': len(found), 'cards_to_create': count[CREATE],
                    'exists': count[EXISTS], 'manual': count[MANUAL]},
    }


def create(items) -> dict:
    """Create the proposed cards `items` (`(set_id, card_id)`, any case; repeats ignored) in
    the caller's transaction through `catalog_admin.create_cards`; a proposal whose card is
    in the catalog (`exists`) is skipped. ItemsRefused (a card the current list does not
    propose; nothing written). Returns `{created, skipped, audit}`. Does not commit."""
    proposals = {}
    for group in _groups(_Load()):
        if group['status'] in (CREATE, EXISTS):
            proposals[(group['set_id'], group['proposed']['card_id'].lower())] = group
    wanted = list(dict.fromkeys((set_id.upper(), card_id.lower()) for set_id, card_id in items))
    unknown = sorted(_ref(*key) for key in wanted if key not in proposals)
    if unknown:
        raise ItemsRefused('These cards are not proposed by the missing printings list: '
                           + ', '.join(unknown) + '.', unknown)
    chosen = [proposals[key] for key in wanted]
    to_create = [group for group in chosen if group['status'] == CREATE]
    skipped = [group for group in chosen if group['status'] == EXISTS]
    cards = catalog_admin.create_cards([group['_clone'] for group in to_create])
    created = [{'set_id': card.rbcar_rbset_id, 'card_id': card.rbcar_id,
                'name': card.rbcar_name, 'rarity': card.rbcar_rarity,
                'copy_of': {'set_id': group['base']['set_id'],
                            'card_id': group['base']['card_id']},
                'product_ids': group['_unlinked']}
               for card, group in zip(cards, to_create)]
    return {
        'created': created,
        'skipped': [{'set_id': group['set_id'], 'card_id': group['proposed']['card_id'],
                     'reason': group['reason']} for group in skipped],
        'audit': {'created': len(created), 'skipped': len(skipped),
                  'cards': [_ref(one['set_id'], one['card_id']) for one in created][:200]},
    }
