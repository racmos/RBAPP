"""Collection read model: groups, lines, prices, totals, facets (F3-b).

`list_collection` returns what `GET /collection` serves. Everything is computed in
Python from the user's lines (one query) and the catalog, the way the cards list does,
so the number of SQL statements does not depend on the size of the collection.

Filters on a line (foil, selling, condition, language, purchase price) drop lines;
filters on a card (text, set, domain, type, rarity) drop groups. A group lists, and
adds up, only the lines that match.
"""
import math
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select

from app import db
from app.models import RbCard, RbCollection, RbKeepPlayset, RbSet, RbUserPrefs
from app.schemas.game_domain import CONDITIONS, LANGUAGES, RARITIES
from app.schemas.validators import CollectionListQuery
from app.services import bans as bans_service
from app.services import card_list, catalog, collection_rules, pricing

CENT = Decimal('0.01')
TENTH = Decimal('0.1')
FACETS = ('set', 'rarity', 'condition', 'language', 'foil')


def _dec(value) -> Decimal | None:
    if value is None or isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _round(value: Decimal, places: Decimal) -> Decimal:
    return value.quantize(places, rounding=ROUND_HALF_UP)


def _money(value: Decimal | None) -> float | None:
    return None if value is None else float(_round(value, CENT))


def _iso_utc(moment) -> str | None:
    return moment.strftime('%Y-%m-%dT%H:%M:%SZ') if moment is not None else None


class _Line:
    """One collection row, as plain values, with the numbers derived from its market price."""
    __slots__ = ('id', 'key', 'qty', 'condition', 'language', 'selling', 'sell_qty', 'chadat',
                 'parsed', 'foil', 'purchase', 'sell_price', 'market', 'value', 'pl_abs', 'pl_pct')

    def __init__(self, row, parsed, market):
        self.id = row.rbcol_id
        self.key = (row.rbcol_rbset_id, row.rbcol_rbcar_id)
        self.qty = row.rbcol_quantity
        self.condition = row.rbcol_condition
        self.language = row.rbcol_language
        self.selling = row.rbcol_selling
        self.sell_qty = row.rbcol_sell_qty
        self.chadat = row.rbcol_chadat
        self.parsed = parsed
        self.foil = row.rbcol_foil == 'S'
        self.purchase = _dec(row.rbcol_purchase_price)
        self.sell_price = _dec(row.rbcol_sell_price)
        self.market = market
        self.value = self.pl_abs = self.pl_pct = None
        if market is not None:
            self.value = (market * self.qty).quantize(CENT, ROUND_HALF_UP)
            purchase = self.purchase
            if purchase is not None and purchase > 0:
                gain = market - purchase
                self.pl_abs = (gain * self.qty).quantize(CENT, ROUND_HALF_UP)
                self.pl_pct = (gain / purchase * 100).quantize(TENTH, ROUND_HALF_UP)


_LINE_COLUMNS = (
    RbCollection.rbcol_id, RbCollection.rbcol_rbset_id, RbCollection.rbcol_rbcar_id,
    RbCollection.rbcol_foil, RbCollection.rbcol_quantity, RbCollection.rbcol_condition,
    RbCollection.rbcol_language, RbCollection.rbcol_purchase_price, RbCollection.rbcol_selling,
    RbCollection.rbcol_sell_qty, RbCollection.rbcol_sell_price, RbCollection.rbcol_chadat)


def _markets(prices: dict) -> dict:
    """`{(set, card, foil): Decimal | None}` from `price_summaries`: one conversion per printing."""
    markets = {}
    for key, price in prices.items():
        for foil, field in ((False, 'market'), (True, 'market_foil')):
            markets[(*key, foil)] = _dec(price.get(field)) if price is not None else None
    return markets


def _failed(query, line: _Line) -> frozenset[str]:
    """The filters this line does not satisfy (empty = it matches). Computed once per line:
    a facet counts the lines that fail nothing but its own filter."""
    parsed = line.parsed
    failed = set()
    if not card_list.text_matches(query.q, parsed):
        failed.add('q')
    if query.set and parsed['set_id_lower'] not in {s.casefold() for s in query.set}:
        failed.add('set')
    if query.rarity and parsed['rarity_lower'] not in {r.casefold() for r in query.rarity}:
        failed.add('rarity')
    if query.type and parsed['type_lower'] not in {t.casefold() for t in query.type}:
        failed.add('type')
    if query.domain and not {d.casefold() for d in query.domain} & parsed['domains_lower']:
        failed.add('domain')
    if (query.foil == 'foil' and not line.foil) or (query.foil == 'nonfoil' and line.foil):
        failed.add('foil')
    if (query.selling == 'yes') != (line.selling == 'Y') and query.selling != 'any':
        failed.add('selling')
    if query.condition and (line.condition or '').casefold() not in {
            c.casefold() for c in query.condition}:
        failed.add('condition')
    if query.language and (line.language or '').casefold() not in {
            c.casefold() for c in query.language}:
        failed.add('language')
    if (query.has_purchase == 'yes') != (line.purchase is not None) \
            and query.has_purchase != 'any':
        failed.add('has_purchase')
    return frozenset(failed)


def _group(lines: list[_Line]) -> dict[tuple, list[_Line]]:
    groups: dict[tuple, list[_Line]] = {}
    for line in lines:  # lines arrive ordered by rbcol_id
        groups.setdefault((*line.key, line.foil), []).append(line)
    return groups


def _sum(values):
    values = [v for v in values if v is not None]
    return sum(values, Decimal(0)) if values else None


def _ordered(counts: dict, known) -> dict:
    lowered = {k.casefold() for k in known}
    ordered = {k: counts[k] for k in known if k in counts}
    for extra in sorted((k for k in counts if k.casefold() not in lowered), key=str.casefold):
        ordered[extra] = counts[extra]
    return ordered


def _facets(lines, failed, set_rank) -> dict:
    """Disjunctive group counts: each facet counts the lines that satisfy every filter but
    its own, so the options of a filter stay visible while it is applied."""
    clean = [line for line, misses in zip(lines, failed) if not misses]
    only: dict[str, list] = {facet: [] for facet in FACETS}
    for line, misses in zip(lines, failed):
        if len(misses) == 1:
            (name,) = misses
            if name in only:
                only[name].append(line)
    getters = {
        'set': lambda line: line.key[0],
        'rarity': lambda line: line.parsed['card'].rbcar_rarity,
        'condition': lambda line: line.condition,
        'language': lambda line: line.language,
        'foil': lambda line: 'foil' if line.foil else 'nonfoil',
    }
    counts = {}
    for facet in FACETS:
        get = getters[facet]
        seen: dict = {}
        for line in clean + only[facet]:
            value = get(line)
            if value is not None:
                seen.setdefault(value, set()).add((*line.key, line.foil))
        counts[facet] = {value: len(groups) for value, groups in seen.items()}
    foil = {'foil': counts['foil'].get('foil', 0), 'nonfoil': counts['foil'].get('nonfoil', 0)}
    return {
        'set': _ordered(counts['set'], sorted(set_rank, key=lambda s: (set_rank[s], s))),
        'rarity': _ordered(counts['rarity'], RARITIES),
        'condition': _ordered(counts['condition'], CONDITIONS),
        'language': _ordered(counts['language'], LANGUAGES),
        'foil': foil,
    }


def _totals(lines: list[_Line]) -> dict:
    qty = sum(line.qty for line in lines)
    foil_qty = sum(line.qty for line in lines if line.foil)
    costs = [line.purchase * line.qty for line in lines
             if line.purchase is not None]
    selling = Decimal(0)
    for line in lines:
        if line.selling != 'Y':
            continue
        unit = line.sell_price if line.sell_price is not None else line.market
        if unit is not None:
            selling += unit * line.sell_qty
    pl = _sum(line.pl_abs for line in lines)
    return {
        'lines': len(lines),
        'qty': qty,
        'unique': len({line.key for line in lines}),
        'value': _money(_sum(line.value for line in lines) or Decimal(0)),
        'cost': _money(sum(costs, Decimal(0))) if costs else None,
        'pl': _money(pl),
        'selling_value': _money(selling),
        'foil_pct': float(_round(Decimal(foil_qty) * 100 / qty, TENTH)) if qty else 0.0,
    }


def _sort_value(sort, members, price_of):
    first = members[0]
    card = first.parsed['card']
    if sort == 'name':
        return first.parsed['name_lower']
    if sort == 'qty':
        return sum(m.qty for m in members)
    if sort == 'price':
        return first.market
    if sort == 'value':
        return _sum(m.value for m in members)
    if sort == 'pl':
        return _sum(m.pl_abs for m in members)
    if sort == 'trend_7d':
        return (price_of(first.key) or {}).get('trend_7d_pct')
    if sort == 'updated':
        return max(m.chadat for m in members)
    if sort == 'rarity':
        return catalog.rarity_rank(card.rbcar_rarity)
    return None


def _order_groups(groups, sort, direction, price_of):
    def natural(item):
        _, members = item
        return (members[0].parsed['natural_key'], members[0].foil)

    items = sorted(groups.items(), key=natural)
    if sort == 'number':
        return list(reversed(items)) if direction == 'desc' else items
    valued = [(item, _sort_value(sort, item[1], price_of)) for item in items]
    present = [pair for pair in valued if pair[1] is not None]
    absent = [pair[0] for pair in valued if pair[1] is None]
    present.sort(key=lambda pair: pair[1], reverse=(direction == 'desc'))
    return [pair[0] for pair in present] + absent


def _line_json(line: _Line) -> dict:
    return {
        'id': line.id,
        'foil': line.foil,
        'qty': line.qty,
        'condition': line.condition,
        'language': line.language,
        'purchase_price': _money(line.purchase),
        'selling': line.selling == 'Y',
        'sell_qty': line.sell_qty,
        'sell_price': _money(line.sell_price),
        'updated_at': _iso_utc(line.chadat),
        'market': _money(line.market),
        'value': _money(line.value),
        'pl_abs': _money(line.pl_abs),
        'pl_pct': float(line.pl_pct) if line.pl_pct is not None else None,
    }


def list_collection(query: CollectionListQuery, user) -> dict:
    """`{items: [CollectionGroup], meta: {...}}` for one user (F3-b S1-S6)."""
    sets = db.session.query(RbSet).all()
    set_rank = catalog.set_order(sets)
    all_cards = db.session.query(RbCard).all()
    base_keys = catalog.base_printing_keys(all_cards, set_rank)
    bans = bans_service.ban_map()
    cards = {(card.rbcar_rbset_id, card.rbcar_id): card for card in all_cards}

    rows = db.session.execute(
        select(*_LINE_COLUMNS)
        .where(RbCollection.rbcol_user == user.username)
        .order_by(RbCollection.rbcol_id)).all()

    parsed_by_key = {}
    for row in rows:
        key = (row.rbcol_rbset_id, row.rbcol_rbcar_id)
        if key not in parsed_by_key and key in cards:
            parsed = card_list.parse_card(cards[key], set_rank)
            parsed['name_key'] = catalog.name_key(cards[key].rbcar_name)
            parsed_by_key[key] = parsed
    prices = pricing.price_summaries(
        (key[0], key[1], p['card'].rbcar_rarity, p['foilable'])
        for key, p in parsed_by_key.items())
    price_of = prices.get

    markets = _markets(prices)
    lines = []
    for row in rows:
        key = (row.rbcol_rbset_id, row.rbcol_rbcar_id)
        if key in parsed_by_key:
            lines.append(_Line(row, parsed_by_key[key],
                               markets.get((*key, row.rbcol_foil == 'S'))))

    # Playset (S4): everything the user owns of a name, whatever the filters say.
    kept_by_name: dict[str, int] = {}
    for line in lines:
        name = line.parsed['name_key']
        kept_by_name[name] = kept_by_name.get(name, 0) + (line.qty - line.sell_qty)
    kept_names = set(db.session.execute(
        select(RbKeepPlayset.rbkps_name_key).where(RbKeepPlayset.rbkps_user_id == user.id)
    ).scalars())
    size = collection_rules.playset_size(db.session.get(RbUserPrefs, user.id))

    failed = [_failed(query, line) for line in lines]
    matching = [line for line, misses in zip(lines, failed) if not misses]
    groups = _group(matching)
    ordered = _order_groups(groups, query.sort, query.dir, price_of)

    total = len(ordered)
    pages = math.ceil(total / query.per_page) if total else 0
    start = (query.page - 1) * query.per_page
    owned: dict[tuple, dict] = {}
    for line in lines:
        entry = owned.setdefault(line.key, {'total': 0, 'foil': 0})
        entry['total'] += line.qty
        if line.foil:
            entry['foil'] += line.qty

    items = []
    for (set_id, card_id, foil), members in ordered[start:start + query.per_page]:
        first = members[0]
        name = first.parsed['name_key']
        keep = name in kept_names
        items.append({
            'key': f"{set_id}-{card_id}:{'S' if foil else 'N'}",
            'card': catalog.card_summary(
                first.parsed['card'], set_rank=set_rank, base_keys=base_keys,
                price=price_of((set_id, card_id)), bans=bans, owned=owned[(set_id, card_id)]),
            'foil': foil,
            'qty': sum(m.qty for m in members),
            'sell_qty': sum(m.sell_qty for m in members),
            'value': _money(_sum(m.value for m in members)),
            'lines': [_line_json(m) for m in members],
            'keep_playset': keep,
            'playset_short': keep and kept_by_name[name] < size,
        })

    return {
        'items': items,
        'meta': {
            'page': query.page,
            'per_page': query.per_page,
            'total_groups': total,
            'pages': pages,
            'totals': _totals(matching),
            'facets': _facets(lines, failed, set_rank),
            'price_as_of': pricing.price_as_of(),
            'playset_size': size,
        },
    }


def user_value_summaries() -> dict[str, dict]:
    """`{username: {value, cost, qty, unique, unpriced}}` for every user with a collection line,
    priced exactly like `list_collection` (F4-c, D-F4-5): value = sum of market x quantity over
    the priced lines, cost = sum of purchase price x quantity (None when no line has one),
    unpriced = lines without a market price. One pass over all lines, a fixed number of queries.
    """
    cards = {(c.rbcar_rbset_id, c.rbcar_id): c for c in db.session.query(RbCard).all()}
    rows = db.session.execute(
        select(RbCollection.rbcol_user, *_LINE_COLUMNS).order_by(RbCollection.rbcol_id)).all()
    printings = {}
    for row in rows:
        key = (row.rbcol_rbset_id, row.rbcol_rbcar_id)
        card = cards.get(key)
        if card is not None and key not in printings:
            card_type, _ = catalog.parse_type(card.rbcar_type)
            printings[key] = (key[0], key[1], card.rbcar_rarity,
                              catalog.is_foilable(card_type, card.rbcar_rarity))
    markets = _markets(pricing.price_summaries(printings.values()))

    summaries: dict[str, dict] = {}
    seen: dict[str, set] = {}
    for row in rows:
        key = (row.rbcol_rbset_id, row.rbcol_rbcar_id)
        if key not in printings:
            continue
        line = _Line(row, None, markets.get((*key, row.rbcol_foil == 'S')))
        summary = summaries.setdefault(row.rbcol_user, {
            'value': Decimal(0), 'cost': None, 'qty': 0, 'unique': 0, 'unpriced': 0})
        seen.setdefault(row.rbcol_user, set()).add(key)
        summary['qty'] += line.qty
        if line.value is None:
            summary['unpriced'] += 1
        else:
            summary['value'] += line.value
        if line.purchase is not None:
            summary['cost'] = (summary['cost'] or Decimal(0)) + line.purchase * line.qty
    for username, summary in summaries.items():
        summary['unique'] = len(seen[username])
        summary['value'] = _round(summary['value'], CENT)
        if summary['cost'] is not None:
            summary['cost'] = _round(summary['cost'], CENT)
    return summaries


def markets_for(cards) -> dict:
    """`{(set, card, foil): Decimal | None}` for the printings of `cards`, priced in one batch."""
    printings = {}
    for card in cards:
        key = (card.rbcar_rbset_id, card.rbcar_id)
        if key not in printings:
            card_type, _ = catalog.parse_type(card.rbcar_type)
            printings[key] = (key[0], key[1], card.rbcar_rarity,
                              catalog.is_foilable(card_type, card.rbcar_rarity))
    return _markets(pricing.price_summaries(printings.values()))


def line_payloads(pairs) -> list[dict]:
    """`CollectionLine` plus `set_id` and `card_id` for `(collection row, card)` pairs (F3-c S1),
    priced in one batch. The rows may be ORM entities or anything with the `rbcol_*` columns."""
    pairs = list(pairs)
    markets = markets_for(card for _, card in pairs)
    payloads = []
    for row, card in pairs:
        key = (card.rbcar_rbset_id, card.rbcar_id)
        line = _Line(row, None, markets.get((*key, row.rbcol_foil == 'S')))
        payloads.append({**_line_json(line), 'set_id': key[0], 'card_id': key[1]})
    return payloads


def market_price(card, foil: bool) -> Decimal | None:
    """The market price of a printing for one foil, as `Decimal` (None when unpriced)."""
    return markets_for([card]).get((card.rbcar_rbset_id, card.rbcar_id, foil))
