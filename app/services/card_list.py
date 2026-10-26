"""Catalog list query: filters, facets, sort and pagination (F2-c S2-S9)."""
import math

from sqlalchemy import case, func, tuple_

from app import db
from app.models import RbCard, RbCollection, RbSet, RbcmPrice
from app.schemas.game_domain import CARD_TYPES, DOMAINS, RARITIES, SUPERTYPES
from app.schemas.validators import CardListQuery
from app.services import bans as bans_service
from app.services import catalog, pricing


_SORT_FIELDS = ('energy', 'power', 'might')
_RANGE_PAIRS = [
    ('energy', 'energy_min', 'energy_max'),
    ('power', 'power_min', 'power_max'),
    ('might', 'might_min', 'might_max'),
]


def _price_as_of() -> str | None:
    latest = db.session.query(func.max(RbcmPrice.rbprc_date)).scalar()
    if not latest:
        return None
    return f'{latest[0:4]}-{latest[4:6]}-{latest[6:8]}'


def _parse_card(card: RbCard, set_rank: dict[str, int]) -> dict:
    parsed_type, supertype = catalog.parse_type(card.rbcar_type)
    domains = catalog.parse_domains(card.rbcar_domain)
    tags = catalog.parse_tags(card.rbcar_tags)
    return {
        'card': card,
        'set_id_lower': (card.rbcar_rbset_id or '').casefold(),
        'name_lower': (card.rbcar_name or '').casefold(),
        'ability_lower': (card.rbcar_ability or '').casefold(),
        'type': parsed_type,
        'type_lower': (parsed_type or '').casefold(),
        'supertype': supertype,
        'supertype_lower': (supertype or '').casefold(),
        'domains': domains,
        'domains_lower': {d.casefold() for d in domains},
        'tags': tags,
        'tags_lower': {t.casefold() for t in tags},
        'foilable': catalog.is_foilable(parsed_type, card.rbcar_rarity),
        'number': catalog.card_number(card.rbcar_id),
        'rarity_rank': catalog.rarity_rank(card.rbcar_rarity),
        'rarity_lower': (card.rbcar_rarity or '').casefold(),
        'natural_key': catalog.natural_key(set_rank.get(card.rbcar_rbset_id), card.rbcar_id),
        'key': f'{card.rbcar_rbset_id}-{card.rbcar_id}',
    }


def _price_inputs(parsed: list[dict]) -> list[tuple[str, str, str | None, bool]]:
    return [
        (p['card'].rbcar_rbset_id, p['card'].rbcar_id,
         p['card'].rbcar_rarity, p['foilable'])
        for p in parsed
    ]


def _range_conflict(query: CardListQuery) -> bool:
    for _attr, min_attr, max_attr in _RANGE_PAIRS:
        lo = getattr(query, min_attr)
        hi = getattr(query, max_attr)
        if lo is not None and hi is not None and lo > hi:
            return True
    if (query.price_min is not None and query.price_max is not None
            and query.price_min > query.price_max):
        return True
    return False


def _matches(query: CardListQuery, p: dict, prices: dict, bans: dict,
             base_keys: set, owned_counts: dict) -> bool:
    card = p['card']
    key = (card.rbcar_rbset_id, card.rbcar_id)

    q = (query.q or '').strip().casefold()
    if q:
        key_text = f'{card.rbcar_rbset_id}-{card.rbcar_id}'.casefold()
        number_match = (q.isdigit() and p['number'] is not None
                        and str(p['number']) == q)
        if not (q in p['name_lower']
                or any(q in tag for tag in p['tags_lower'])
                or q == (card.rbcar_id or '').casefold()
                or q == key_text
                or number_match):
            return False

    text = (query.text or '').casefold()
    if text and text not in p['ability_lower']:
        return False

    if query.set and p['set_id_lower'] not in {s.casefold() for s in query.set}:
        return False

    if query.rarity and p['rarity_lower'] not in {r.casefold() for r in query.rarity}:
        return False

    if query.type and p['type_lower'] not in {t.casefold() for t in query.type}:
        return False

    if query.supertype:
        wanted = {s.casefold() for s in query.supertype}
        if p['supertype_lower'] not in wanted:
            return False

    if query.exclude_supertype:
        unwanted = {s.casefold() for s in query.exclude_supertype}
        if p['supertype'] is not None and p['supertype_lower'] in unwanted:
            return False

    if query.tag:
        wanted = {t.casefold() for t in query.tag}
        if not wanted & p['tags_lower']:
            return False

    if query.domain:
        wanted = {d.casefold() for d in query.domain}
        card_domains = p['domains_lower']
        if query.domain_match == 'any':
            if not (wanted & card_domains):
                return False
        elif query.domain_match == 'all':
            if not wanted <= card_domains:
                return False
        else:  # subset
            if card_domains and not card_domains <= wanted:
                return False

    for attr, min_attr, max_attr in _RANGE_PAIRS:
        lo = getattr(query, min_attr)
        hi = getattr(query, max_attr)
        if lo is not None or hi is not None:
            value = getattr(card, f'rbcar_{attr}')
            if value is None:
                return False
            if lo is not None and value < lo:
                return False
            if hi is not None and value > hi:
                return False

    if query.price_min is not None or query.price_max is not None:
        summary = prices.get(key)
        market = summary.get('market') if summary else None
        if market is None:
            return False
        if query.price_min is not None and market < query.price_min:
            return False
        if query.price_max is not None and market > query.price_max:
            return False

    if query.banned_in:
        card_bans = bans_service.card_bans(card.rbcar_name, bans)
        if query.banned_in == 'any':
            if not any(card_bans.values()):
                return False
        elif not card_bans.get(query.banned_in):
            return False

    if query.base_only and key not in base_keys:
        return False

    owned = owned_counts.get(key, {'total': 0, 'foil': 0})
    if query.owned == 'owned' and owned['total'] <= 0:
        return False
    if query.owned == 'missing' and owned['total'] != 0:
        return False

    return True


def _main_value(p: dict, sort: str, prices: dict):
    card = p['card']
    key = (card.rbcar_rbset_id, card.rbcar_id)
    if sort == 'number':
        return p['natural_key']
    if sort == 'name':
        return p['name_lower']
    if sort == 'rarity':
        return p['rarity_rank']
    if sort == 'price':
        return (prices.get(key) or {}).get('market')
    if sort == 'trend_7d':
        return (prices.get(key) or {}).get('trend_7d_pct')
    if sort == 'trend_30d':
        return (prices.get(key) or {}).get('trend_30d_pct')
    if sort == 'energy':
        return card.rbcar_energy
    if sort == 'power':
        return card.rbcar_power
    if sort == 'might':
        return card.rbcar_might
    return p['natural_key']


def _apply_sort(parsed: list[dict], sort: str, direction: str, prices: dict) -> list[dict]:
    with_value = []
    for p in parsed:
        v = _main_value(p, sort, prices)
        with_value.append((p, v))
    nulls = [p for p, v in with_value if v is None]
    vals = [(p, v) for p, v in with_value if v is not None]
    # Stable sort: tiebreak by natural_key ascending first, then the main key.
    vals.sort(key=lambda pv: pv[0]['natural_key'])
    vals.sort(key=lambda pv: pv[1], reverse=(direction == 'desc'))
    nulls.sort(key=lambda p: p['natural_key'])
    return [p for p, _ in vals] + nulls


def _ordered_counts(facet: str, counts: dict, set_rank: dict[str, int]) -> dict | list:
    if facet == 'tag':
        items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:30]
        return [{'tag': tag, 'count': count} for tag, count in items]

    if facet == 'set':
        known_order = sorted(set_rank, key=lambda s: (set_rank[s], s))
    elif facet == 'domain':
        known_order = list(DOMAINS)
    elif facet == 'type':
        known_order = list(CARD_TYPES)
    elif facet == 'supertype':
        known_order = list(SUPERTYPES)
    elif facet == 'rarity':
        known_order = list(RARITIES)
    else:
        known_order = []

    known_lower = {k.casefold() for k in known_order}
    ordered = []
    for key in known_order:
        if key in counts:
            ordered.append((key, counts[key]))
    unknown = [(k, c) for k, c in counts.items() if k.casefold() not in known_lower]
    unknown.sort(key=lambda kv: kv[0].casefold())
    ordered.extend(unknown)
    return {k: c for k, c in ordered}


def _count_values(facet: str, parsed: list[dict]) -> dict:
    counts: dict[str, int] = {}
    if facet == 'set':
        for p in parsed:
            counts[p['card'].rbcar_rbset_id] = counts.get(p['card'].rbcar_rbset_id, 0) + 1
    elif facet == 'domain':
        for p in parsed:
            for d in p['domains']:
                counts[d] = counts.get(d, 0) + 1
    elif facet == 'type':
        for p in parsed:
            if p['type'] is not None:
                counts[p['type']] = counts.get(p['type'], 0) + 1
    elif facet == 'supertype':
        for p in parsed:
            if p['supertype'] is not None:
                counts[p['supertype']] = counts.get(p['supertype'], 0) + 1
    elif facet == 'rarity':
        for p in parsed:
            if p['card'].rbcar_rarity is not None:
                counts[p['card'].rbcar_rarity] = counts.get(p['card'].rbcar_rarity, 0) + 1
    elif facet == 'tag':
        for p in parsed:
            for tag in p['tags']:
                counts[tag] = counts.get(tag, 0) + 1
    return counts


def _facet_query(query: CardListQuery, facet: str) -> CardListQuery:
    """Return a copy of `query` with that facet's own parameter removed."""
    data = query.model_dump()
    if facet == 'set':
        data['set'] = []
    elif facet == 'domain':
        data['domain'] = []
    elif facet == 'type':
        data['type'] = []
    elif facet == 'supertype':
        data['supertype'] = []
    elif facet == 'rarity':
        data['rarity'] = []
    elif facet == 'tag':
        data['tag'] = []
    return CardListQuery(**data)


def _owned_counts(parsed: list[dict], username: str | None) -> dict:
    """One batched query summing the current user's quantities per printing."""
    if not parsed or not username:
        return {}
    keys = [(p['card'].rbcar_rbset_id, p['card'].rbcar_id) for p in parsed]
    rows = db.session.query(
        RbCollection.rbcol_rbset_id,
        RbCollection.rbcol_rbcar_id,
        func.sum(RbCollection.rbcol_quantity).label('total'),
        func.sum(case((RbCollection.rbcol_foil == 'S',
                       RbCollection.rbcol_quantity), else_=0)).label('foil'),
    ).filter(
        RbCollection.rbcol_user == username,
        tuple_(RbCollection.rbcol_rbset_id,
               RbCollection.rbcol_rbcar_id).in_(keys),
    ).group_by(
        RbCollection.rbcol_rbset_id,
        RbCollection.rbcol_rbcar_id,
    ).all()
    return {
        (set_id, card_id): {'total': int(total or 0), 'foil': int(foil or 0)}
        for set_id, card_id, total, foil in rows
    }


def _compute_facets(parsed: list[dict], query: CardListQuery, prices: dict,
                    bans: dict, base_keys: set, owned_counts: dict,
                    set_rank: dict[str, int]) -> dict:
    facets = {}
    for facet in ('set', 'domain', 'type', 'supertype', 'rarity', 'tag'):
        qf = _facet_query(query, facet)
        matched = [p for p in parsed if _matches(qf, p, prices, bans, base_keys, owned_counts)]
        counts = _count_values(facet, matched)
        facets[facet] = _ordered_counts(facet, counts, set_rank)
    return facets


def search_cards(query: CardListQuery, username: str | None = None) -> dict:
    """Return `{items: [CardSummary, ...], meta: {...}}` for the catalog list."""
    all_sets = db.session.query(RbSet).all()
    set_rank = catalog.set_order(all_sets)
    all_cards = db.session.query(RbCard).all()
    base_keys = catalog.base_printing_keys(all_cards, set_rank)
    bans = bans_service.ban_map()

    parsed = [_parse_card(card, set_rank) for card in all_cards]

    owned_counts = _owned_counts(parsed, username)
    for p in parsed:
        p['owned'] = owned_counts.get(
            (p['card'].rbcar_rbset_id, p['card'].rbcar_id),
            {'total': 0, 'foil': 0},
        )

    if _range_conflict(query):
        return {
            'items': [],
            'meta': {
                'page': query.page,
                'per_page': query.per_page,
                'total': 0,
                'pages': 0,
                'facets': _compute_facets(parsed, query, {}, bans, base_keys,
                                          owned_counts, set_rank),
                'price_as_of': _price_as_of(),
            },
        }

    has_price_bounds = query.price_min is not None or query.price_max is not None
    has_price_sort = query.sort in ('price', 'trend_7d', 'trend_30d')

    if has_price_bounds:
        # Price filtering needs every card priced; facets are correct by default.
        all_prices = pricing.price_summaries(_price_inputs(parsed))
        filtered = [p for p in parsed
                    if _matches(query, p, all_prices, bans, base_keys, owned_counts)]
    elif has_price_sort:
        # Apply every filter except price bounds (none here), price only matches,
        # then sort by the requested price field.
        non_price_query = query.model_copy(update={'price_min': None,
                                                   'price_max': None})
        pre_price = [p for p in parsed
                     if _matches(non_price_query, p, {}, bans, base_keys,
                                 owned_counts)]
        all_prices = pricing.price_summaries(_price_inputs(pre_price))
        filtered = pre_price
    else:
        all_prices = {}
        filtered = [p for p in parsed
                    if _matches(query, p, all_prices, bans, base_keys, owned_counts)]

    sorted_cards = _apply_sort(filtered, query.sort, query.dir, all_prices)

    total = len(sorted_cards)
    per_page = query.per_page
    pages = math.ceil(total / per_page) if total else 0
    start = (query.page - 1) * per_page
    page_cards = sorted_cards[start:start + per_page]

    page_prices = all_prices if has_price_bounds or has_price_sort else \
        pricing.price_summaries(_price_inputs(page_cards))

    items = []
    for p in page_cards:
        card = p['card']
        key = (card.rbcar_rbset_id, card.rbcar_id)
        items.append(catalog.card_summary(
            card,
            set_rank=set_rank,
            base_keys=base_keys,
            price=page_prices.get(key),
            bans=bans,
            owned=p['owned'],
        ))

    facet_prices = all_prices if has_price_bounds or has_price_sort else {}
    facets = _compute_facets(parsed, query, facet_prices, bans, base_keys,
                             owned_counts, set_rank)

    return {
        'items': items,
        'meta': {
            'page': query.page,
            'per_page': per_page,
            'total': total,
            'pages': pages,
            'facets': facets,
            'price_as_of': _price_as_of(),
        },
    }
