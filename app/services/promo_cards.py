"""Missing promo cards (CM-h) and plated cards (CM-k). No Flask request objects; the views
audit and commit.

Riot's gallery does not publish the promo sets (OGNX, SFDX, UNLX, ...), so after the
production reset they have no cards and their Cardmarket products cannot be matched. Owner
rule (2026-11-23): a promo card has the SAME card id as its base card, in the set whose id is
the base set id followed by `X` (OGN/035 Vayne, Hunter -> OGNX/035). Other sets (PROK, ...)
have another convention and are refused until the owner gives it.

Plated cards (CM-k, owner decision 2026-11-24): set `PLAT` (Cardmarket 'Plated Legends - Metal
Cards') holds metal copies of cards of other sets, coded `PLAT-<origin set>-<number>` and stored
as set PLAT with the card id `<origin set><number>` in lower case (SFD/189 -> PLAT/sfd189; card
ids are letters and digits only). Its product names do not carry the origin set, so each
unmatched PLAT single looks for its ORIGIN card by name (the matcher's name index, legends by
their tags too) among the plain printings (all-digit ids, no rune) of every set but PLAT and the
promo sets: exactly one is the card to copy, none or several leave the product to the admin
(`no_base_card`, `ambiguous_base` with the `candidates`). A PLAT card of the product's name (or
of the proposed id) is in the catalog already. One product per plated card: the cheapest gets
it, the others are `no_slot`. A PLAT plan has no base set (`base` null).

For a promo set with a mapped Cardmarket expansion, `plan` lists the unmatched singles of the
latest load of its expansions (not linked, not ignored) and pairs them with the base cards of
the same name as the matcher pairs products with cards (`app/services/cardmarket_matcher.py`):
products by price ascending, the cards by `card_rank_key` of the promo card they become, a
common or uncommon card absorbing two products (its N and S slots) and every other card,
runes included, one. `create` makes the promo cards as copies of their base cards (every
card field but the image) through `catalog_admin.create_cards`, the same creation and checks
as `POST /admin/cards`; a card that exists is skipped, never overwritten. Auto-match links the
products afterwards (`daily_prices.classify_unmapped`).
"""
import re
from collections import defaultdict
from types import SimpleNamespace

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

PROMO_SUFFIX = 'X'
# The card fields a promo card copies from its base card: everything but the image (the
# owner uploads the promo images later).
CLONE_FIELDS = ('name', 'domain', 'type', 'tags', 'energy', 'power', 'might', 'ability',
                'rarity', 'artist')

CREATE, EXISTS, MANUAL = 'create', 'exists', 'manual'
# Why an item has its status: the promo card is a copy of its base card (`clone`) or is in the
# catalog (`in_catalog`); a manual product has no base card of its name (`no_base_card`), comes
# after the last slot of its cards (`no_slot`), has no Cardmarket card group (`no_metacard`,
# the matcher skips it) or its base card does not pass the card checks (`invalid_base`).
# A PLAT product (CM-k) can also have several origin cards of its name (`ambiguous_base`).
CLONE, IN_CATALOG = 'clone', 'in_catalog'
NO_BASE_CARD, NO_SLOT, NO_METACARD, INVALID_BASE, AMBIGUOUS_BASE = (
    'no_base_card', 'no_slot', 'no_metacard', 'invalid_base', 'ambiguous_base')
# The set of the plated cards (CM-k, owner decision 2026-11-24).
PLATED_SET = 'PLAT'
_PLAIN_ID = re.compile(r'^\d+$')

_MANUAL_TEXT = {
    NO_SLOT: 'no card slot left: link it by hand',
    NO_BASE_CARD: 'no card of this name in {base}',
    NO_METACARD: 'Cardmarket gives it no card group',
    INVALID_BASE: 'its base card cannot be copied',
}
_PLATED_TEXT = {
    NO_SLOT: 'no card slot left: link it by hand',
    NO_BASE_CARD: 'no card of this name in any set',
    AMBIGUOUS_BASE: 'several cards of this name: {candidates}',
    INVALID_BASE: 'its origin card cannot be copied',
}


class SetRefused(Exception):
    """The set is unknown, not a promo set, without its base set or without a mapped
    Cardmarket expansion; `message` says which."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ProductsRefused(Exception):
    """Some products of a create call are not unmatched products of the set (`unknown`) or
    get no promo card (`manual`); nothing is written."""

    def __init__(self, message: str, unknown: list, manual: list):
        super().__init__(message)
        self.message, self.unknown, self.manual = message, unknown, manual


def base_of(set_id: str) -> str | None:
    """`OGN` for `OGNX`; None when the id is not a promo id (it must end with `X`)."""
    if len(set_id) > 1 and set_id.endswith(PROMO_SUFFIX):
        return set_id[:-len(PROMO_SUFFIX)]
    return None


def _set_header(promo: RbSet, base: RbSet | None, expansions: list) -> dict:
    return {'id': promo.rbset_id, 'name': promo.rbset_name,
            'base': base.rbset_id if base is not None else None,
            'base_name': base.rbset_name if base is not None else None,
            'expansions': sorted(expansions)}


def _all_sets() -> dict:
    return {row.rbset_id: row for row in db.session.execute(sa.select(RbSet)).scalars()}


def _check_set(set_id: str) -> tuple[RbSet, RbSet | None, list, dict]:
    """`(promo set, base set, mapped expansion ids, every set by id)` of a usable promo set or
    of PLAT (no base set), or SetRefused. Two statements."""
    base_id = base_of(set_id)
    sets = _all_sets()
    if set_id not in sets:
        raise SetRefused(f"Set '{set_id}' does not exist.")
    if set_id != PLATED_SET:
        if base_id is None:
            raise SetRefused(f'{set_id} is not a promo set: a promo set id is its base set id '
                             f'followed by X (OGN -> OGNX).')
        if base_id not in sets:
            raise SetRefused(f'The base set {base_id} of {set_id} does not exist.')
    expansions = list(db.session.execute(
        sa.select(RbcmExpansion.rbexp_id).where(RbcmExpansion.rbexp_rbset_id == set_id))
        .scalars())
    if not expansions:
        raise SetRefused(f'No Cardmarket expansion is mapped to {set_id}: map it in the '
                         f'Expansions tab first.')
    return sets[set_id], sets.get(base_id) if set_id != PLATED_SET else None, expansions, sets


def _latest_date():
    return db.session.execute(sa.select(sa.func.max(RbcmProduct.rbprd_date))).scalar()


class _Plans:
    """The plans of several promo sets `[(promo, base, expansion ids)]` (PLAT: base None)
    from one read of the latest load: products, the cards of the base and promo sets (every
    card when PLAT is one of them: its origins can be in any set), the taken slots of the
    promo sets and the prices. Six statements whatever the number of sets and products.
    `set_ids` = every set id (the promo sets are never origins of a plated card)."""

    def __init__(self, promos, set_ids=()):
        self.date = _latest_date()
        self.promos = promos
        self.set_ids = set(set_ids)
        exp_to_set = {exp: promo.rbset_id for promo, _base, exps in promos for exp in exps}
        self.products = defaultdict(list)
        if self.date is None or not exp_to_set:
            self.cards, self.index, self.taken, self.prices = [], {}, set(), {}
            return
        mapped = sa.exists().where(
            RbcmProductCardMap.rbpcm_id_product == RbcmProduct.rbprd_id_product)
        ignored = sa.exists().where(RbcmIgnored.rbig_id_product == RbcmProduct.rbprd_id_product,
                                    RbcmIgnored.rbig_name == RbcmProduct.rbprd_name)
        rows = db.session.execute(
            sa.select(RbcmProduct).where(
                RbcmProduct.rbprd_date == self.date, RbcmProduct.rbprd_type == 'single',
                RbcmProduct.rbprd_id_expansion.in_(list(exp_to_set)), ~mapped, ~ignored)
            .order_by(RbcmProduct.rbprd_id_product)).scalars().all()
        for product in rows:
            self.products[exp_to_set[product.rbprd_id_expansion]].append(product)
        cards = sa.select(RbCard)
        if all(base is not None for _p, base, _e in promos):
            cards = cards.where(RbCard.rbcar_rbset_id.in_(
                {promo.rbset_id for promo, _b, _e in promos}
                | {base.rbset_id for _p, base, _e in promos}))
        self.cards = db.session.execute(cards).scalars().all()
        self.index = matcher._build_card_index(self.cards)
        self.taken = set(db.session.execute(sa.select(
            RbcmProductCardMap.rbpcm_rbset_id, RbcmProductCardMap.rbpcm_rbcar_id,
            RbcmProductCardMap.rbpcm_foil).where(
                RbcmProductCardMap.rbpcm_rbset_id.in_(
                    [promo.rbset_id for promo, _b, _e in promos]))).all())
        self.prices = matcher._get_latest_prices([p.rbprd_id_product for p in rows])

    def price(self, product):
        value = self.prices.get(product.rbprd_id_product)
        return float(value) if value is not None else None

    def items(self, promo: RbSet, base: RbSet | None) -> list[dict]:
        """The items of one promo set: one per promo card (the products it absorbs), one per
        manual product; by product name, then price. PLAT (base None): `_plated_items`."""
        if base is None:
            return _sorted_items(self._plated_items(promo))
        p_id, b_id = promo.rbset_id, base.rbset_id
        in_promo = {card.rbcar_id.lower(): card for card in self.cards
                    if card.rbcar_rbset_id == p_id}
        groups, loose = defaultdict(list), []
        for product in self.products.get(p_id, []):
            if product.rbprd_id_metacard:
                groups[product.rbprd_id_metacard].append(product)
            else:
                loose.append(product)
        targets, manual = {}, []
        for products in groups.values():
            self._pair(products, p_id, b_id, in_promo, targets, manual)
        manual.extend((product, NO_METACARD, None) for product in loose)

        items = [self._target_item(target, p_id) for target in targets.values()]
        items.extend(self._manual_item(product, reason, card)
                     for product, reason, card in manual)
        return _sorted_items(items)

    def _plated_items(self, plated: RbSet) -> list[dict]:
        """The items of PLAT (CM-k): each unmatched single (a card group is not needed) finds
        its plated card through its one origin card, or the PLAT card of its name; one product
        per plated card, the cheapest, the others `no_slot`."""
        p_id = plated.rbset_id
        promo_ids = {set_id for set_id in self.set_ids if base_of(set_id) in self.set_ids}
        origins = matcher._build_card_index([
            card for card in self.cards
            if card.rbcar_rbset_id != p_id and card.rbcar_rbset_id not in promo_ids
            and _PLAIN_ID.match(card.rbcar_id or '') and not matcher._is_rune(card)])
        in_plated = [card for card in self.cards if card.rbcar_rbset_id == p_id]
        by_name = matcher._build_card_index(in_plated)
        by_id = {card.rbcar_id.lower(): card for card in in_plated}
        targets, manual = {}, []
        for product in self.products.get(p_id, []):
            name = matcher.normalize_name(product.rbprd_name)
            found = _unique(origins.get(name, [])) if name else []
            base = found[0] if len(found) == 1 else None
            key = f'{base.rbcar_rbset_id}{base.rbcar_id}'.lower() if base is not None else None
            same_name = sorted(_unique(by_name.get(name, [])) if name else [],
                               key=lambda card: card.rbcar_id)
            if key is not None and key in by_id:
                card = by_id[key]
            elif same_name:
                card = same_name[0]
            elif base is not None:
                card = None
            else:
                reason = AMBIGUOUS_BASE if found else NO_BASE_CARD
                manual.append((product, reason, None,
                               sorted(found, key=lambda c: (c.rbcar_rbset_id, c.rbcar_id))))
                continue
            key = card.rbcar_id.lower() if card is not None else key
            entry = targets.setdefault(key, {'key': key, 'card': card, 'base': base,
                                             'products': []})
            entry['base'] = entry['base'] or base
            entry['products'].append(product)
        items = []
        for target in targets.values():
            products = sorted(target['products'],
                              key=lambda p: (self.price(p) or 0.0, p.rbprd_id_product))
            shape = target['card'] or _clone_shape(target['base'], p_id, target['key'])
            slots = matcher._expand_slots(shape, taken=self.taken)
            if slots:
                target['products'] = [(products[0], slots[0][1])]
                items.append({**self._target_item(target, p_id), 'candidates': []})
                products = products[1:]
            manual.extend((product, NO_SLOT, target['base'], []) for product in products)
        items.extend({**self._manual_item(product, reason, base),
                      'candidates': [_card_brief(card) for card in candidates]}
                     for product, reason, base, candidates in manual)
        return items

    def _pair(self, products, p_id, b_id, in_promo, targets, manual):
        """Pair the products of one card group with the promo cards of their name: the base
        cards copied (or the promo card already there), ranked as the promo card."""
        names = {matcher.normalize_name(p.rbprd_name) for p in products} - {''}
        found, seen = [], set()
        for name in sorted(names):
            for card in self.index.get(name, []):
                key = (card.rbcar_rbset_id, card.rbcar_id)
                if key not in seen:
                    seen.add(key)
                    found.append(card)
        group_targets = {}
        for card in found:
            if card.rbcar_rbset_id == p_id:
                group_targets.setdefault(card.rbcar_id.lower(), {'card': card, 'base': None})
        for base in (card for card in found if card.rbcar_rbset_id == b_id):
            key = base.rbcar_id.lower()
            if key in group_targets:
                group_targets[key]['base'] = group_targets[key]['base'] or base
            elif key in in_promo:                     # the id is taken by another promo card
                group_targets[key] = {'card': in_promo[key], 'base': base}
            else:
                group_targets[key] = {'card': None, 'base': base}
        ordered = sorted(group_targets.items(), key=lambda pair: matcher.card_rank_key(
            pair[1]['card'] or _clone_shape(pair[1]['base'], p_id, pair[0])))
        prices = sorted(products, key=lambda p: (self.price(p) or 0.0, p.rbprd_id_product))
        if not ordered:
            manual.extend((product, NO_BASE_CARD, None) for product in prices)
            return
        slots = []
        for key, target in ordered:
            shape = target['card'] or _clone_shape(target['base'], p_id, key)
            slots.extend((key, target, foil)
                         for _card, foil in matcher._expand_slots(shape, taken=self.taken))
        for product, (key, target, foil) in zip(prices, slots):
            entry = targets.setdefault(key, {'key': key, 'card': target['card'],
                                             'base': target['base'], 'products': []})
            entry['base'] = entry['base'] or target['base']
            entry['products'].append((product, foil))
        last_base = next((target['base'] for _key, target in reversed(ordered)
                          if target['base'] is not None), None)
        manual.extend((product, NO_SLOT, last_base) for product in prices[len(slots):])

    def _target_item(self, target, p_id) -> dict:
        products = sorted(target['products'],
                          key=lambda pair: (self.price(pair[0]) or 0.0, pair[0].rbprd_id_product))
        first = products[0][0]
        base = target['base']
        if target['card'] is not None:
            status, reason, clone = EXISTS, IN_CATALOG, None
        else:
            clone = _clone_body(base, p_id, target['key'])
            status, reason = (CREATE, CLONE) if clone is not None else (MANUAL, INVALID_BASE)
        return {
            'product_id': first.rbprd_id_product,
            'product_ids': [product.rbprd_id_product for product, _foil in products],
            'product_name': first.rbprd_name, 'price': self.price(first),
            'expansion_id': first.rbprd_id_expansion,
            'products': [{'id': product.rbprd_id_product, 'name': product.rbprd_name,
                          'price': self.price(product), 'foil': foil}
                         for product, foil in products],
            'base': _card_brief(base),
            'proposed': (None if status == MANUAL else
                         {'set_id': p_id, 'card_id': target['card'].rbcar_id
                          if target['card'] is not None else target['key']}),
            'status': status, 'reason': reason, '_clone': clone,
        }

    def _manual_item(self, product, reason, base) -> dict:
        return {
            'product_id': product.rbprd_id_product, 'product_ids': [product.rbprd_id_product],
            'product_name': product.rbprd_name, 'price': self.price(product),
            'expansion_id': product.rbprd_id_expansion,
            'products': [{'id': product.rbprd_id_product, 'name': product.rbprd_name,
                          'price': self.price(product), 'foil': None}],
            'base': _card_brief(base), 'proposed': None,
            'status': MANUAL, 'reason': reason, '_clone': None,
        }


def _sorted_items(items: list[dict]) -> list[dict]:
    """By product name, then price (unpriced last), then product id."""
    return sorted(items, key=lambda item: (item['product_name'].lower(), item['price'] is None,
                                           item['price'] or 0, item['product_id']))


def _unique(cards) -> list:
    seen, result = set(), []
    for card in cards:
        key = (card.rbcar_rbset_id, card.rbcar_id)
        if key not in seen:
            seen.add(key)
            result.append(card)
    return result


def _manual_text(item: dict, base: RbSet | None) -> str:
    """Why a product gets no card, for the 400 of `create`."""
    if base is None:
        return _PLATED_TEXT[item['reason']].format(candidates=', '.join(
            f"{one['set_id']}-{one['card_id']}" for one in item.get('candidates', [])))
    return _MANUAL_TEXT[item['reason']].format(base=base.rbset_id)


def _clone_shape(base: RbCard, p_id: str, key: str):
    """What the matcher reads of the promo card a base card becomes (rank and slots)."""
    return SimpleNamespace(rbcar_rbset_id=p_id, rbcar_id=key, rbcar_rarity=base.rbcar_rarity,
                           rbcar_type=base.rbcar_type, rbcar_name=base.rbcar_name)


def _clone_body(base: RbCard, p_id: str, key: str):
    """The `AdminCardCreate` of the copy of `base` in the promo set, or None when the base card
    does not pass the card checks."""
    try:
        return AdminCardCreate(set_id=p_id, card_id=key, **{
            field: getattr(base, catalog_admin.card_column(field)) for field in CLONE_FIELDS})
    except ValidationError:
        return None


def _card_brief(card) -> dict | None:
    if card is None:
        return None
    return {'set_id': card.rbcar_rbset_id, 'card_id': card.rbcar_id, 'name': card.rbcar_name,
            'rarity': card.rbcar_rarity, 'type': card.rbcar_type}


def _public(item: dict) -> dict:
    return {key: value for key, value in item.items() if not key.startswith('_')}


def _summary(items) -> dict:
    count = defaultdict(int)
    for item in items:
        count[item['status']] += len(item['product_ids'])
    return {'cards_to_create': sum(1 for item in items if item['status'] == CREATE),
            'products_to_create': count[CREATE], 'exists': count[EXISTS],
            'manual': count[MANUAL], 'products': sum(count.values())}


def promo_sets() -> dict:
    """The usable promo sets (an id ending with X, its base set, a mapped expansion) and PLAT
    (with a mapped expansion; base null), by id, with the products whose card is missing and
    the cards to create. Eight statements whatever the number of sets and products."""
    by_set = defaultdict(list)
    for exp_id, set_id in db.session.execute(
            sa.select(RbcmExpansion.rbexp_id, RbcmExpansion.rbexp_rbset_id)
            .where(RbcmExpansion.rbexp_rbset_id.isnot(None))).all():
        by_set[set_id].append(exp_id)
    sets = _all_sets() if by_set else {}
    promos = []
    for set_id in sorted(by_set):
        if set_id not in sets:
            continue
        if set_id == PLATED_SET:
            promos.append((sets[set_id], None, by_set[set_id]))
        elif base_of(set_id) in sets:
            promos.append((sets[set_id], sets[base_of(set_id)], by_set[set_id]))
    plans = _Plans(promos, sets)
    result = []
    for promo, base, exps in promos:
        summary = _summary(plans.items(promo, base))
        result.append({**_set_header(promo, base, exps),
                       'products_missing': summary['products_to_create'],
                       'cards_to_create': summary['cards_to_create']})
    return {'date': iso(plans.date) if plans.date else None, 'sets': result}


def _plan(set_id: str):
    promo, base, exps, sets = _check_set(set_id)
    plans = _Plans([(promo, base, exps)], sets)
    return promo, base, exps, plans.date, plans.items(promo, base)


def plan(set_id: str) -> dict:
    """The plan of one promo set or of PLAT: `{set, date, items, summary}` (a PLAT item also
    has `candidates`: the origin cards of an `ambiguous_base` product); SetRefused for a set
    that is not a usable promo set. Eight statements whatever the number of products. Writes
    nothing."""
    promo, base, exps, date, items = _plan(set_id)
    return {'set': _set_header(promo, base, exps), 'date': iso(date) if date else None,
            'items': [_public(item) for item in items], 'summary': _summary(items)}


def create(set_id: str, product_ids) -> dict:
    """Create the promo cards of the items holding `product_ids` (any product of an item
    chooses its card) in the caller's transaction, through `catalog_admin.create_cards`; an
    item whose card exists is skipped. SetRefused, ProductsRefused (unknown or manual products,
    nothing written). Returns `{created, skipped, audit}` (`audit` = the details of the one
    audit row of the call). Does not commit."""
    promo, base, _exps, _date, items = _plan(set_id)
    by_product = {pid: item for item in items for pid in item['product_ids']}
    wanted = list(dict.fromkeys(product_ids))
    unknown = sorted(pid for pid in wanted if pid not in by_product)
    manual = sorted(pid for pid in wanted
                    if pid in by_product and by_product[pid]['status'] == MANUAL)
    if unknown or manual:
        parts = []
        noun = 'promo card' if base is not None else 'plated card'
        if manual:
            parts.append(f'These products get no {noun}: ' + ', '.join(
                f'{pid} ({_manual_text(by_product[pid], base)})' for pid in manual) + '.')
        if unknown:
            parts.append(f'These products are not unmatched products of {promo.rbset_id}: '
                         + ', '.join(str(pid) for pid in unknown) + '.')
        raise ProductsRefused(' '.join(parts), unknown, manual)

    chosen = list({id(by_product[pid]): by_product[pid] for pid in wanted}.values())
    to_create = [item for item in chosen if item['status'] == CREATE]
    skipped = [item for item in chosen if item['status'] == EXISTS]
    cards = catalog_admin.create_cards([item['_clone'] for item in to_create])
    created = [{'set_id': card.rbcar_rbset_id, 'card_id': card.rbcar_id, 'name': card.rbcar_name,
                'base': {'set_id': item['base']['set_id'], 'card_id': item['base']['card_id']},
                'product_ids': item['product_ids']}
               for card, item in zip(cards, to_create)]
    return {
        'created': created,
        'skipped': [{'set_id': item['proposed']['set_id'],
                     'card_id': item['proposed']['card_id'], 'reason': item['reason'],
                     'product_ids': item['product_ids']} for item in skipped],
        'audit': {'set_id': promo.rbset_id, 'base': base.rbset_id if base is not None else None,
                  'created': len(created),
                  'skipped': len(skipped), 'products': len(wanted),
                  'cards': [card['card_id'] for card in created][:200]},
    }
