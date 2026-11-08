"""Cardmarket matching workbench (CM-b): unmatched products with suggestions, candidates,
link / unlink / relink, the links browser, the ignore list, the auto-match preview /
apply and the review list. No Flask request objects; the views audit and commit.

Port of the old Jinja price tools (removed with the Jinja web, PR 3/3 of its retirement).
A link is one `rbcm_product_card_map`
row: a Cardmarket product id to a card and a foil slot (`N`, `S` or null; two nulls are
the same slot). Products (`rbproducts`) are keyed by the Cardmarket id itself, so a
non-single is linked by identity and there is no product link to write.

Unmatched is `cardmarket_log.unmatched_clauses` (one definition); clear and doubtful
cases are `daily_prices.classify_unmapped` (the decision the daily job takes).
"""
import difflib
from collections import Counter

import sqlalchemy as sa
from sqlalchemy.orm import aliased

from app import db
from app.models.card import RbCard
from app.models.cardmarket import (RbcmExpansion, RbcmIgnored, RbcmPrice, RbcmProduct,
                                   RbcmProductCardMap, RbProducts)
from app.services import cardmarket_matcher as matcher
from app.services import daily_prices
from app.services.cardmarket_log import iso, unmatched_clauses

MANUAL_CONFIDENCE = 1.0
SUGGESTIONS = 3
CANDIDATES = 20
# difflib ratio a normalised name needs to be suggested when no name matches exactly.
CLOSE_CUTOFF = 0.75
# Score factor of a card outside the set of the product's expansion.
OTHER_SET = 0.9


class NotFound(Exception):
    """The Cardmarket product, or its link, does not exist."""


class UnknownCard(Exception):
    """The card of a link is not in the catalog."""


class LinkConflict(Exception):
    """The product is already linked (`field='id_product'`) or the card slot is taken
    (`field='card'`); `params` go to the error body."""

    def __init__(self, message: str, params: dict):
        super().__init__(message)
        self.message, self.params = message, params


def _float(value):
    return float(value) if value is not None else None


def _like(text: str) -> str:
    return f'%{text}%'


def latest_date() -> str | None:
    return db.session.execute(sa.select(sa.func.max(RbcmProduct.rbprd_date))).scalar()


def _lows_at_latest_price_date(ids) -> dict:
    """`{id: low}` at the newest `rbcm_price` date (the legacy unmatched/ignored price)."""
    if not ids:
        return {}
    latest = sa.select(sa.func.max(RbcmPrice.rbprc_date)).scalar_subquery()
    return {pid: _float(low) for pid, low in db.session.execute(
        sa.select(RbcmPrice.rbprc_id_product, RbcmPrice.rbprc_low).where(
            RbcmPrice.rbprc_date == latest, RbcmPrice.rbprc_id_product.in_(ids))).all()}


def _latest_lows(ids) -> dict:
    """`{id: (low, date)}` at each product's own newest price date (the legacy mappings
    browser price)."""
    if not ids:
        return {}
    newest = (sa.select(RbcmPrice.rbprc_id_product.label('pid'),
                        sa.func.max(RbcmPrice.rbprc_date).label('day'))
              .where(RbcmPrice.rbprc_id_product.in_(ids))
              .group_by(RbcmPrice.rbprc_id_product).subquery())
    return {pid: (_float(low), day) for pid, low, day in db.session.execute(
        sa.select(RbcmPrice.rbprc_id_product, RbcmPrice.rbprc_low, RbcmPrice.rbprc_date)
        .join(newest, sa.and_(newest.c.pid == RbcmPrice.rbprc_id_product,
                              newest.c.day == RbcmPrice.rbprc_date))).all()}


def _expansion(product, expansion) -> dict | None:
    if product.rbprd_id_expansion is None:
        return None
    return {'id': product.rbprd_id_expansion,
            'name': expansion.rbexp_name if expansion else None,
            'set_id': expansion.rbexp_rbset_id if expansion else None}


class _Suggester:
    """Candidate cards of a Cardmarket product by its normalised name, as the matcher
    indexes them (legend cards also under `tags, name` and `name, tags`). Three
    statements: the card index, the expansion sets and the taken slots."""

    def __init__(self):
        self.index = matcher._build_card_index()
        self.keys = list(self.index)
        self.exp_to_set = matcher._get_expansion_to_set_map()
        self.taken = set(db.session.execute(sa.select(
            RbcmProductCardMap.rbpcm_rbset_id, RbcmProductCardMap.rbpcm_rbcar_id,
            RbcmProductCardMap.rbpcm_foil)).all())

    def cards(self, product, limit: int) -> list[tuple]:
        """`[(card, score)]`, best first: an exact normalised name scores 1.0, a close
        one its difflib ratio; a card outside the expansion's set scores x0.9."""
        name = matcher.normalize_name(product.rbprd_name)
        if not name:
            return []
        scored = {}
        if name in self.index:
            matches = [(name, 1.0)]
        else:
            matches = [(key, difflib.SequenceMatcher(None, name, key).ratio())
                       for key in difflib.get_close_matches(name, self.keys, n=limit,
                                                            cutoff=CLOSE_CUTOFF)]
        set_id = self.exp_to_set.get(product.rbprd_id_expansion or 0)
        for key, ratio in matches:
            for card in self.index[key]:
                score = ratio * (OTHER_SET if set_id and card.rbcar_rbset_id != set_id else 1)
                ident = (card.rbcar_rbset_id, card.rbcar_id)
                if ident not in scored or scored[ident][1] < score:
                    scored[ident] = (card, round(score, 2))
        ranked = sorted(scored.values(), key=lambda pair: (-pair[1],
                                                           matcher.card_rank_key(pair[0])))
        return ranked[:limit]

    def free_foils(self, card) -> list:
        return [foil for _card, foil in matcher._expand_slots(card, taken=self.taken)]

    def suggestion(self, card, score) -> dict:
        return {'kind': 'card', 'id': f'{card.rbcar_rbset_id}-{card.rbcar_id}',
                'name': card.rbcar_name, 'set': card.rbcar_rbset_id,
                'number': card.rbcar_id, 'score': score, 'free_foils': self.free_foils(card)}


def _product_suggestion(product: RbProducts) -> dict:
    return {'kind': 'product', 'id': product.rbpdt_id_product, 'name': product.rbpdt_name,
            'set': product.rbpdt_id_set, 'number': None, 'score': 1.0, 'free_foils': []}


# --- unmatched ---------------------------------------------------------------

def list_unmatched(params) -> tuple[list, int, str | None]:
    """Unmatched products of the latest date (`unmatched_clauses`), by name then id, with
    the low price at the newest price date (legacy), the first date the id was seen and
    up to three suggestions. Nine statements (with the session user) whatever the page size."""
    date = latest_date()
    where = list(unmatched_clauses())
    if params.type:
        where.append(RbcmProduct.rbprd_type == params.type)
    if params.q:
        where.append(sa.or_(RbcmProduct.rbprd_name.ilike(_like(params.q)),
                            sa.cast(RbcmProduct.rbprd_id_product, sa.Text)
                            .ilike(_like(params.q))))
    if params.category:
        where.append(RbcmProduct.rbprd_category_name.ilike(_like(params.category)))
    total = db.session.execute(
        sa.select(sa.func.count()).select_from(RbcmProduct).where(*where)).scalar_one()
    earlier = aliased(RbcmProduct)
    first_seen = (sa.select(sa.func.min(earlier.rbprd_date))
                  .where(earlier.rbprd_id_product == RbcmProduct.rbprd_id_product)
                  .scalar_subquery())
    rows = db.session.execute(
        sa.select(RbcmProduct, RbcmExpansion, first_seen.label('first_seen'))
        .outerjoin(RbcmExpansion, RbcmExpansion.rbexp_id == RbcmProduct.rbprd_id_expansion)
        .where(*where)
        .order_by(RbcmProduct.rbprd_name, RbcmProduct.rbprd_id_product)
        .limit(params.per_page).offset((params.page - 1) * params.per_page)).all()
    if not rows:
        return [], total, date and iso(date)
    lows = _lows_at_latest_price_date([r.RbcmProduct.rbprd_id_product for r in rows])
    singles = any(r.RbcmProduct.rbprd_type == 'single' for r in rows)
    suggester = _Suggester() if singles else None
    others = [r.RbcmProduct.rbprd_id_product for r in rows
              if r.RbcmProduct.rbprd_type != 'single']
    products = {}
    if others:
        products = {p.rbpdt_id_product: p for p in db.session.execute(
            sa.select(RbProducts).where(RbProducts.rbpdt_id_product.in_(others))).scalars()}
    items = []
    for row in rows:
        product = row.RbcmProduct
        if product.rbprd_type == 'single':
            suggestions = [suggester.suggestion(card, score)
                           for card, score in suggester.cards(product, SUGGESTIONS)]
        else:
            same = products.get(product.rbprd_id_product)
            suggestions = [_product_suggestion(same)] if same else []
        items.append({
            'id_product': product.rbprd_id_product, 'name': product.rbprd_name,
            'type': product.rbprd_type, 'category': product.rbprd_category_name,
            'expansion': _expansion(product, row.RbcmExpansion),
            'low_price': lows.get(product.rbprd_id_product),
            'first_seen_date': iso(row.first_seen), 'suggestions': suggestions})
    return items, total, iso(date)


def _latest_product(id_product: int):
    """`(RbcmProduct, RbcmExpansion | None)` of the newest row of a Cardmarket id, or None."""
    return db.session.execute(
        sa.select(RbcmProduct, RbcmExpansion)
        .outerjoin(RbcmExpansion, RbcmExpansion.rbexp_id == RbcmProduct.rbprd_id_expansion)
        .where(RbcmProduct.rbprd_id_product == id_product)
        .order_by(RbcmProduct.rbprd_date.desc()).limit(1)).first()


def _link_brief(link) -> dict | None:
    if link is None:
        return None
    return {'set_id': link.rbpcm_rbset_id, 'card_id': link.rbpcm_rbcar_id,
            'foil': link.rbpcm_foil, 'match_type': link.rbpcm_match_type}


def _product_item(product: RbProducts) -> dict:
    return {'id': product.rbpdt_id_product, 'name': product.rbpdt_name,
            'set_id': product.rbpdt_id_set, 'kind': product.rbpdt_kind,
            'category': product.rbpdt_category}


def candidates(id_product: int, q: str | None) -> dict | None:
    """What a Cardmarket product can be linked to: cards found by `q` (name or
    `SET-ID`, at most 20) or, without `q`, the suggested cards; for a non-single also the
    products (by name, or the product of the same id). None when the id is unknown."""
    found = _latest_product(id_product)
    if found is None:
        return None
    product, expansion = found
    if q:
        cards = db.session.execute(
            sa.select(RbCard).where(sa.or_(
                RbCard.rbcar_name.ilike(_like(q)),
                (RbCard.rbcar_rbset_id + '-' + RbCard.rbcar_id).ilike(_like(q))))
            .order_by(RbCard.rbcar_name, RbCard.rbcar_rbset_id, RbCard.rbcar_id)
            .limit(CANDIDATES)).scalars().all()
    else:
        cards = [card for card, _score in _Suggester().cards(product, CANDIDATES)]
    links = {}
    if cards:
        keys = [(c.rbcar_rbset_id, c.rbcar_id) for c in cards]
        for link in db.session.execute(
                sa.select(RbcmProductCardMap).where(sa.tuple_(
                    RbcmProductCardMap.rbpcm_rbset_id, RbcmProductCardMap.rbpcm_rbcar_id)
                    .in_(keys)).order_by(RbcmProductCardMap.rbpcm_id_product)).scalars():
            links.setdefault((link.rbpcm_rbset_id, link.rbpcm_rbcar_id), []).append(
                {'id_product': link.rbpcm_id_product, 'foil': link.rbpcm_foil})
    products = []
    if product.rbprd_type != 'single':
        if q:
            query = (sa.select(RbProducts).where(RbProducts.rbpdt_name.ilike(_like(q)))
                     .order_by(RbProducts.rbpdt_name, RbProducts.rbpdt_id_product)
                     .limit(CANDIDATES))
        else:
            query = sa.select(RbProducts).where(RbProducts.rbpdt_id_product == id_product)
        products = [_product_item(p) for p in db.session.execute(query).scalars()]
    return {
        'product': {'id_product': product.rbprd_id_product, 'name': product.rbprd_name,
                    'type': product.rbprd_type, 'category': product.rbprd_category_name,
                    'expansion': _expansion(product, expansion),
                    'date': iso(product.rbprd_date),
                    'link': _link_brief(db.session.get(RbcmProductCardMap, id_product))},
        'cards': [{'set_id': c.rbcar_rbset_id, 'card_id': c.rbcar_id, 'name': c.rbcar_name,
                   'rarity': c.rbcar_rarity, 'type': c.rbcar_type, 'image_src': c.image_src,
                   'links': links.get((c.rbcar_rbset_id, c.rbcar_id), [])} for c in cards],
        'products': products,
    }


# --- links -------------------------------------------------------------------

def link_item(link: RbcmProductCardMap) -> dict:
    """One link with its product (newest row), card name and newest price."""
    found = _latest_product(link.rbpcm_id_product)
    product = found[0] if found else None
    card = db.session.get(RbCard, (link.rbpcm_rbset_id, link.rbpcm_rbcar_id))
    low, day = _latest_lows([link.rbpcm_id_product]).get(link.rbpcm_id_product, (None, None))
    return _item(link, product.rbprd_name if product else None,
                 product.rbprd_type if product else None,
                 bool(product) and product.rbprd_date == latest_date(),
                 card.rbcar_name if card else None, low, day)


def _item(link, name, type_, in_latest, card_name, low, day) -> dict:
    return {'id_product': link.rbpcm_id_product, 'product_name': name,
            'product_type': type_, 'in_latest_load': bool(in_latest),
            'set_id': link.rbpcm_rbset_id, 'card_id': link.rbpcm_rbcar_id,
            'card_name': card_name, 'foil': link.rbpcm_foil,
            'match_type': link.rbpcm_match_type,
            'confidence': _float(link.rbpcm_confidence),
            'low_price': low, 'price_date': iso(day) if day else None}


def _slot_holder(set_id, card_id, foil, other_than: int):
    """The link of another product on the same card and foil slot (two nulls are the
    same slot), as the legacy map checks it."""
    query = sa.select(RbcmProductCardMap).where(
        RbcmProductCardMap.rbpcm_rbset_id == set_id,
        RbcmProductCardMap.rbpcm_rbcar_id == card_id,
        RbcmProductCardMap.rbpcm_id_product != other_than,
        RbcmProductCardMap.rbpcm_foil.is_(None) if foil is None
        else RbcmProductCardMap.rbpcm_foil == foil)
    return db.session.execute(query.limit(1)).scalar()


def _check_target(id_product, set_id, card_id, foil):
    if db.session.get(RbCard, (set_id, card_id)) is None:
        raise UnknownCard(f'{set_id}-{card_id}')
    holder = _slot_holder(set_id, card_id, foil, id_product)
    if holder is not None:
        label = {'N': ' (normal)', 'S': ' (foil)'}.get(foil or '', '')
        raise LinkConflict(
            f'Card {set_id}-{card_id}{label} is already linked to Cardmarket product '
            f'{holder.rbpcm_id_product}. Unlink that one first or choose another card '
            f'or foil.', {'field': 'card', 'linked_id_product': holder.rbpcm_id_product})


def _new_link(id_product, set_id, card_id, foil) -> RbcmProductCardMap:
    link = RbcmProductCardMap(
        rbpcm_id_product=id_product, rbpcm_rbset_id=set_id, rbpcm_rbcar_id=card_id,
        rbpcm_foil=foil, rbpcm_match_type='manual', rbpcm_confidence=MANUAL_CONFIDENCE)
    db.session.add(link)
    db.session.flush()
    return link


def link(id_product: int, set_id: str, card_id: str, foil) -> RbcmProductCardMap:
    """Link a Cardmarket product to a card slot (`manual`, confidence 1.0). Raises
    NotFound (unknown product), UnknownCard, LinkConflict (already linked: unlink
    first; or the slot belongs to another product). Does not commit."""
    if _latest_product(id_product) is None:
        raise NotFound(id_product)
    if db.session.get(RbCard, (set_id, card_id)) is None:
        raise UnknownCard(f'{set_id}-{card_id}')
    existing = db.session.get(RbcmProductCardMap, id_product)
    if existing is not None:
        raise LinkConflict(
            f'Cardmarket product {id_product} is already linked to '
            f'{existing.rbpcm_rbset_id}-{existing.rbpcm_rbcar_id}. Unlink it first.',
            {'field': 'id_product', 'set_id': existing.rbpcm_rbset_id,
             'card_id': existing.rbpcm_rbcar_id, 'foil': existing.rbpcm_foil})
    _check_target(id_product, set_id, card_id, foil)
    return _new_link(id_product, set_id, card_id, foil)


def unlink(id_product: int) -> dict:
    """Remove the link of a Cardmarket product and return it as it was (so it can be
    posted back). Raises NotFound. Does not commit."""
    existing = db.session.get(RbcmProductCardMap, id_product)
    if existing is None:
        raise NotFound(id_product)
    item = link_item(existing)
    db.session.delete(existing)
    db.session.flush()
    return item


def relink(id_product: int, set_id: str, card_id: str, foil) -> tuple[dict, RbcmProductCardMap]:
    """Unlink and link to the new target in the caller's transaction: `(previous item,
    new link)`. Raises NotFound (no link), UnknownCard, LinkConflict (the slot belongs
    to another product); nothing is changed then. Does not commit."""
    existing = db.session.get(RbcmProductCardMap, id_product)
    if existing is None:
        raise NotFound(id_product)
    _check_target(id_product, set_id, card_id, foil)
    previous = link_item(existing)
    db.session.delete(existing)
    db.session.flush()
    return previous, _new_link(id_product, set_id, card_id, foil)


def list_links(params) -> tuple[list, int, int]:
    """Links (every `rbcm_product_card_map` row) with the newest product row, card and
    price; `conflicts` keeps the card slots held by more than one product. Returns
    `(items, total, conflict slots)`; five statements (with the session user) whatever
    the page size."""
    newest = aliased(RbcmProduct)
    name = (sa.select(newest.rbprd_name)
            .where(newest.rbprd_id_product == RbcmProductCardMap.rbpcm_id_product)
            .order_by(newest.rbprd_date.desc()).limit(1).scalar_subquery())
    type_ = (sa.select(newest.rbprd_type)
             .where(newest.rbprd_id_product == RbcmProductCardMap.rbpcm_id_product)
             .order_by(newest.rbprd_date.desc()).limit(1).scalar_subquery())
    latest = sa.select(sa.func.max(RbcmProduct.rbprd_date)).scalar_subquery()
    in_latest = sa.exists().where(
        newest.rbprd_id_product == RbcmProductCardMap.rbpcm_id_product,
        newest.rbprd_date == latest)
    slot = (RbcmProductCardMap.rbpcm_rbset_id, RbcmProductCardMap.rbpcm_rbcar_id,
            sa.func.coalesce(RbcmProductCardMap.rbpcm_foil, ''))
    shared = sa.select(*slot).group_by(*slot).having(sa.func.count() > 1)

    where = []
    if params.q:
        like = _like(params.q)
        where.append(sa.or_(name.ilike(like),
                            sa.cast(RbcmProductCardMap.rbpcm_id_product, sa.Text).ilike(like),
                            RbCard.rbcar_name.ilike(like),
                            RbcmProductCardMap.rbpcm_rbcar_id.ilike(like)))
    if params.set:
        where.append(RbcmProductCardMap.rbpcm_rbset_id.ilike(_like(params.set)))
    if params.foil == 'none':
        where.append(RbcmProductCardMap.rbpcm_foil.is_(None))
    elif params.foil:
        where.append(RbcmProductCardMap.rbpcm_foil == params.foil)
    if params.match_type:
        where.append(RbcmProductCardMap.rbpcm_match_type == params.match_type)
    if params.conflicts:
        where.append(sa.tuple_(*slot).in_(shared))

    card_join = sa.and_(RbCard.rbcar_rbset_id == RbcmProductCardMap.rbpcm_rbset_id,
                        RbCard.rbcar_id == RbcmProductCardMap.rbpcm_rbcar_id)
    total = db.session.execute(
        sa.select(sa.func.count()).select_from(RbcmProductCardMap)
        .outerjoin(RbCard, card_join).where(*where)).scalar_one()
    conflict_slots = db.session.execute(
        sa.select(sa.func.count()).select_from(shared.subquery())).scalar_one()
    order = ((*slot, RbcmProductCardMap.rbpcm_id_product) if params.conflicts
             else (sa.func.lower(name), RbcmProductCardMap.rbpcm_id_product))
    rows = db.session.execute(
        sa.select(RbcmProductCardMap, RbCard.rbcar_name, name.label('name'),
                  type_.label('type'), in_latest.label('in_latest'))
        .outerjoin(RbCard, card_join).where(*where).order_by(*order)
        .limit(params.per_page).offset((params.page - 1) * params.per_page)).all()
    lows = _latest_lows([r.RbcmProductCardMap.rbpcm_id_product for r in rows])
    items = [_item(r.RbcmProductCardMap, r.name, r.type, r.in_latest, r.rbcar_name,
                   *lows.get(r.RbcmProductCardMap.rbpcm_id_product, (None, None)))
             for r in rows]
    return items, total, conflict_slots


# --- ignore list -------------------------------------------------------------

def _ignored_item(row, lows) -> dict:
    return {'id_product': row.rbig_id_product, 'name': row.rbig_name,
            'low_price': lows.get(row.rbig_id_product),
            'ignored_at': row.rbig_ignored_at.isoformat() if row.rbig_ignored_at else None}


def list_ignored() -> list[dict]:
    """The ignore list, newest first, with the low price at the newest price date."""
    rows = db.session.execute(sa.select(RbcmIgnored).order_by(
        RbcmIgnored.rbig_ignored_at.desc(), RbcmIgnored.rbig_id_product,
        RbcmIgnored.rbig_name)).scalars().all()
    lows = _lows_at_latest_price_date([r.rbig_id_product for r in rows])
    return [_ignored_item(r, lows) for r in rows]


def ignore(id_product: int, name: str) -> tuple[dict, bool]:
    """Add `(id, name)` to the ignore list unless present: `(item, created)`. Does not
    commit."""
    row = db.session.get(RbcmIgnored, (id_product, name))
    created = row is None
    if created:
        row = RbcmIgnored(rbig_id_product=id_product, rbig_name=name)
        db.session.add(row)
        db.session.flush()
        db.session.refresh(row)
    return _ignored_item(row, _lows_at_latest_price_date([id_product])), created


def unignore(id_product: int, name: str | None) -> list[dict]:
    """Remove `(id, name)`, or every name of the id, from the ignore list; the removed
    pairs (empty when none). Does not commit."""
    query = sa.select(RbcmIgnored).where(RbcmIgnored.rbig_id_product == id_product)
    if name is not None:
        query = query.where(RbcmIgnored.rbig_name == name)
    rows = db.session.execute(query.order_by(RbcmIgnored.rbig_name)).scalars().all()
    for row in rows:
        db.session.delete(row)
    db.session.flush()
    return [{'id_product': r.rbig_id_product, 'name': r.rbig_name} for r in rows]


# --- auto-match --------------------------------------------------------------

def _proposal_items(links, date) -> list[dict]:
    """The clear-case links `[(id, (set, card, foil))]` with product and card names."""
    if not links:
        return []
    ids = [id_product for id_product, _slot in links]
    names = dict(db.session.execute(
        sa.select(RbcmProduct.rbprd_id_product, RbcmProduct.rbprd_name).where(
            RbcmProduct.rbprd_date == date, RbcmProduct.rbprd_id_product.in_(ids))).all())
    keys = [(set_id, card_id) for _id, (set_id, card_id, _foil) in links]
    cards = {(set_id, card_id): name for set_id, card_id, name in db.session.execute(
        sa.select(RbCard.rbcar_rbset_id, RbCard.rbcar_id, RbCard.rbcar_name).where(
            sa.tuple_(RbCard.rbcar_rbset_id, RbCard.rbcar_id).in_(keys))).all()}
    lows = _lows_at_latest_price_date(ids)
    return [{'id_product': id_product, 'product_name': names.get(id_product),
             'low_price': lows.get(id_product), 'set_id': set_id, 'card_id': card_id,
             'card_name': cards.get((set_id, card_id)), 'foil': foil}
            for id_product, (set_id, card_id, foil) in links]


def _decide():
    date = latest_date()
    if date is None:
        return None, {'links': [], 'review': [], 'proposed': 0}
    return date, daily_prices.classify_unmapped(date)


def preview() -> dict:
    """What `daily_prices` would do now with the latest load, without writing: the clear
    links, the doubtful cases (first 200) and the counts."""
    date, decided = _decide()
    review = decided['review']
    return {'date': date and iso(date), 'proposed': decided['proposed'],
            'clear': len(decided['links']), 'doubtful': len(review),
            'links': _proposal_items(decided['links'], date),
            'review': review[:daily_prices.REVIEW_LIMIT], 'review_total': len(review)}


def apply(max_groups: int) -> dict:
    """Link the first `max_groups` clear cases of the latest load (each one is a
    one-product group) as the daily job does. Does not commit."""
    date, decided = _decide()
    chosen = decided['links'][:max_groups]
    daily_prices.add_links(chosen)
    db.session.flush()
    return {'date': date and iso(date), 'linked': len(chosen),
            'clear': len(decided['links']),
            'remaining_clear': len(decided['links']) - len(chosen),
            'doubtful': len(decided['review']),
            'links': _proposal_items(chosen, date)}


def review(params) -> tuple[list, dict]:
    """The doubtful cases of the latest load, live (manual links leave it at once),
    optionally of one reason, paged: `(items, meta)`."""
    date, decided = _decide()
    reasons = Counter(item['reason'] for item in decided['review'])
    items = [item for item in decided['review']
             if params.reason is None or item['reason'] == params.reason]
    start = (params.page - 1) * params.per_page
    total = len(items)
    return items[start:start + params.per_page], {
        'page': params.page, 'per_page': params.per_page, 'total': total,
        'pages': max((total + params.per_page - 1) // params.per_page, 1),
        'date': date and iso(date), 'reasons': dict(reasons)}
