"""Deck rules engine (F5-a, F5-R2): the game rules of a v2 deck, as pure functions.

Nothing here touches Flask, the request or the database: the caller passes the deck
(content v2, F5-R6), the catalog subset it references and the bans. The TypeScript port
(F5-b, `frontend/src/decks/rules/`) implements the same functions against the same cases
(`tests/fixtures/deck_rules_cases.json`); the server stays authoritative.

- `deck`: `{"v": 2, "legend": ref|None, "champion": ref|None, "main": [line],
  "runes": [line], "battlefields": [ref], "sideboard": [line], "workbench": [line]}` with
  `ref = {"set", "id"}` and `line = {"set", "id", "qty"}`; a missing zone is empty.
- `cards`: `{(set_id, card_id): card}`, `card` with the `CardSummary` fields `name`, `type`,
  `supertype` (str|None), `domains` and `tags` (lists). Every card the deck or the call
  references must be there (`UnknownCard` otherwise). Iteration order matters only to
  `auto_runes` (first rune of a colour).
- `bans`: `{name: [modes]}`, names matched with `name_key` (the `ban_map` keys are).

Rule values come from `DECK_RULES`. Soft rules are `validate` issues (they never block a
save); hard limits (F5-R9) are `hard_limit_violations`, and `can_add` / `can_move` refuse
both the hard limits and the cards that do not fit a zone. Names: printings of a name are
one card (`name_key`); names sort by `name_sort_key` (D-F5-7).
"""
from copy import deepcopy
from math import floor

from app.schemas.game_domain import DECK_RULES, DOMAINS, GAME_MODES
from app.services.bans import name_key

# Issue codes in report order (F5-R2).
ISSUE_CODES = ('legend_missing', 'champion_missing', 'champion_tag', 'main_size',
               'runes_count', 'rune_off_identity', 'battlefields_count',
               'battlefields_duplicate', 'sideboard_size', 'copies_over', 'workbench_over',
               'card_off_identity', 'token_in_deck', 'banned')

# Hard limit rules in report order (F5-R9): `deck_limit_exceeded` params `{rule, max, name?}`.
HARD_RULES = ('copies', 'sideboard', 'workbench', 'battlefields', 'runes', 'token')

# Display order of the zones (design-handoff §3.7.1); "first occurrence" follows it.
ZONE_ORDER = ('legend', 'champion', 'battlefields', 'main', 'sideboard', 'runes', 'workbench')
ADD_ZONES = ('main', 'sideboard', 'workbench', 'runes', 'battlefields')
MOVE_ZONES = ('main', 'sideboard', 'workbench')
# Zones whose copies count for the copy limit, plus the chosen champion (product.md).
COPY_ZONES = ('main', 'sideboard', 'workbench')
# Types that never go in the main deck or the sideboard.
NOT_IN_DECK_TYPES = ('Legend', 'Battlefield', 'Rune')
COLORLESS = 'Colorless'


class UnknownCard(KeyError):
    """A deck or call references a card missing from `cards`; `args[0]` is `(set, id)`."""


# --- names and cards -------------------------------------------------------------------

def name_sort_key(name):
    """D-F5-7: `name_key` in code-point order, ties by the raw name in code-point order."""
    return (name_key(name), name)


def sort_names(names):
    """`names` sorted by `name_sort_key` (no locale collation)."""
    return sorted(names, key=name_sort_key)


def _card(cards, ref):
    key = (ref['set'], ref['id'])
    if key not in cards:
        raise UnknownCard(key)
    return cards[key]


def _supertypes(card):
    return (card.get('supertype') or '').split()


def is_token(card):
    """"Token Unit", "Token Battlefield", ... or a bare "Token" (no base type)."""
    return 'Token' in _supertypes(card) or card.get('type') == 'Token'


def is_champion_unit(card):
    return 'Champion' in _supertypes(card) and card.get('type') == 'Unit'


def colours(card):
    """The domains of a card without Colorless, in card order."""
    return [domain for domain in card.get('domains') or [] if domain != COLORLESS]


def rune_colour(card):
    domains = card.get('domains') or []
    return domains[0] if domains else None


def share_tag(a, b):
    return bool(set(a.get('tags') or []) & set(b.get('tags') or []))


def _zone(deck, zone):
    return deck.get(zone) or []


def _total(deck, zone):
    return sum(line['qty'] for line in _zone(deck, zone))


def _entries(deck, cards):
    """`(zone, ref, card, qty)` for every card of the deck, in ZONE_ORDER."""
    out = []
    for zone in ZONE_ORDER:
        if zone in ('legend', 'champion'):
            if deck.get(zone):
                out.append((zone, deck[zone], _card(cards, deck[zone]), 1))
        else:
            for line in _zone(deck, zone):
                out.append((zone, line, _card(cards, line), line.get('qty', 1)))
    return out


def identity(deck, cards):
    """The legend's colours (its domains without Colorless); `[]` without a legend."""
    return colours(_card(cards, deck['legend'])) if deck.get('legend') else []


def copies(deck, cards):
    """`{name_key: [name, count]}` over main + sideboard + workbench + the chosen champion;
    `name` is the first occurrence in ZONE_ORDER."""
    counts = {}
    for zone, _ref, card, qty in _entries(deck, cards):
        if zone == 'champion' or zone in COPY_ZONES:
            entry = counts.setdefault(name_key(card['name']), [card['name'], 0])
            entry[1] += qty
    return counts


def _copies_of(deck, cards, name, zones, champion=True):
    key = name_key(name)
    count = sum(line['qty'] for zone in zones for line in _zone(deck, zone)
                if name_key(_card(cards, line)['name']) == key)
    if champion and deck.get('champion'):
        count += name_key(_card(cards, deck['champion'])['name']) == key
    return count


def _workbench_names(deck, cards):
    return {name_key(_card(cards, line)['name']) for line in _zone(deck, 'workbench')}


def _size(have, need):
    return {'have': have, 'need': need, 'missing': max(0, need - have),
            'over': max(0, have - need)}


def _missing_slot():
    return {'have': 0, 'need': 1, 'missing': 1}


def _refusal(code, params):
    return {'ok': False, 'code': code, 'params': params}


def _off_identity(card, zone, reason):
    return {'name': card['name'], 'zone': zone, 'reason': reason}


def _fit_reason(card, zone, legend, cols):
    """Why `card` does not fit `zone` (`'type'`, `'domain'`, `'tag'`), or None.

    The type rules always apply; colour and Signature tag only with a legend (`legend`).
    Tokens are reported apart (`token_in_deck`) and never reach here.
    """
    card_type = card.get('type')
    if zone == 'legend':
        return None if card_type == 'Legend' else 'type'
    if zone == 'champion':
        return None if is_champion_unit(card) else 'type'
    if zone == 'battlefields':
        return None if card_type == 'Battlefield' else 'type'
    if zone == 'runes':
        return None if card_type == 'Rune' else 'type'
    if zone in ('main', 'sideboard'):
        if card_type in NOT_IN_DECK_TYPES:
            return 'type'
        if legend is None:
            return None
        if 'Signature' in _supertypes(card) and not share_tag(card, legend):
            return 'tag'
        if any(domain not in cols for domain in colours(card)):
            return 'domain'
    return None


# --- validate ----------------------------------------------------------------------------

def validate(deck, cards, bans, mode):
    """`{legal, issues: [{code, params}], completeness}` of `deck` in `mode`.

    `legal` is true only without issues. Issues come in ISSUE_CODES order, then by
    `name_sort_key` of `params.name`, then by ZONE_ORDER of `params.zone`. The workbench
    only counts for `copies_over` and `workbench_over`. `completeness` says, per section,
    how many cards it has and is missing.
    """
    if mode not in GAME_MODES:
        raise ValueError(f'unknown game mode: {mode}')
    legend = _card(cards, deck['legend']) if deck.get('legend') else None
    champion = _card(cards, deck['champion']) if deck.get('champion') else None
    cols = colours(legend) if legend else []
    found = {}

    def add(code, params):
        key = (code, name_key(params['name']) if 'name' in params else '', params.get('zone'))
        found.setdefault(key, {'code': code, 'params': params})

    if legend is None:
        add('legend_missing', _missing_slot())
    if champion is None:
        add('champion_missing', _missing_slot())
    elif legend is not None and not is_token(champion) and is_champion_unit(champion) \
            and not share_tag(champion, legend):
        add('champion_tag', {'name': champion['name']})

    main = _total(deck, 'main')
    if main != DECK_RULES['main_size']:
        add('main_size', _size(main, DECK_RULES['main_size']))
    runes = _total(deck, 'runes')
    if runes != DECK_RULES['runes']:
        add('runes_count', _size(runes, DECK_RULES['runes']))
    battlefields = len(_zone(deck, 'battlefields'))
    if battlefields != DECK_RULES['battlefields']:
        add('battlefields_count', _size(battlefields, DECK_RULES['battlefields']))
    seen_fields = set()
    for ref in _zone(deck, 'battlefields'):
        card = _card(cards, ref)
        key = name_key(card['name'])
        if key in seen_fields:
            add('battlefields_duplicate', {'name': _first_name(deck, cards, card, 'battlefields')})
        seen_fields.add(key)
    sideboard = _total(deck, 'sideboard')
    if sideboard != DECK_RULES['sideboard']:
        add('sideboard_size', _size(sideboard, DECK_RULES['sideboard']))

    for name, count in copies(deck, cards).values():
        if count > DECK_RULES['copies_max']:
            add('copies_over', {'name': name, 'count': count, 'max': DECK_RULES['copies_max']})
    workbench = len(_workbench_names(deck, cards))
    if workbench > DECK_RULES['workbench_max']:
        add('workbench_over', {'count': workbench, 'max': DECK_RULES['workbench_max']})

    for zone, _ref, card, _qty in _entries(deck, cards):
        if zone == 'workbench':
            continue
        if is_token(card):
            add('token_in_deck', {'name': card['name'], 'zone': zone})
            continue
        reason = _fit_reason(card, zone, legend, cols)
        if reason is not None:
            add('card_off_identity', _off_identity(card, zone, reason))
        elif zone == 'runes' and legend is not None and rune_colour(card) not in cols:
            add('rune_off_identity', {'name': card['name']})

    banned = {name_key(name): modes for name, modes in (bans or {}).items()}
    for zone, _ref, card, _qty in _entries(deck, cards):
        if zone != 'workbench' and mode in banned.get(name_key(card['name']), ()):
            add('banned', {'name': card['name'], 'mode': mode})

    issues = sorted(found.values(), key=_issue_order)
    return {'legal': not issues, 'issues': issues, 'completeness': completeness(deck)}


def _first_name(deck, cards, card, zone):
    key = name_key(card['name'])
    for ref in _zone(deck, zone):
        name = _card(cards, ref)['name']
        if name_key(name) == key:
            return name
    return card['name']


def _issue_order(issue):
    params = issue['params']
    zone = params.get('zone')
    return (ISSUE_CODES.index(issue['code']),
            name_sort_key(params['name']) if 'name' in params else ('', ''),
            ZONE_ORDER.index(zone) if zone in ZONE_ORDER else -1)


def completeness(deck):
    """`{section: {have, need, missing}}` for legend, champion, main, runes, battlefields
    and sideboard; `have` counts every card in the section, fitting or not."""
    def entry(have, need):
        return {'have': have, 'need': need, 'missing': max(0, need - have)}

    return {'legend': entry(1 if deck.get('legend') else 0, 1),
            'champion': entry(1 if deck.get('champion') else 0, 1),
            'main': entry(_total(deck, 'main'), DECK_RULES['main_size']),
            'runes': entry(_total(deck, 'runes'), DECK_RULES['runes']),
            'battlefields': entry(len(_zone(deck, 'battlefields')), DECK_RULES['battlefields']),
            'sideboard': entry(_total(deck, 'sideboard'), DECK_RULES['sideboard'])}


# --- editor checks -------------------------------------------------------------------------

def can_add(deck, cards, card, zone):
    """`{ok: True}` or `{ok: False, code, params}` for one more copy of `card` in `zone`.

    Refuses the hard limits and the cards that do not fit the zone by type; the colour
    and Signature tag of main / sideboard cards are soft (validate reports them). Params
    describe the deck as it would be after the add.
    """
    if zone not in ADD_ZONES:
        raise ValueError(f'unknown zone: {zone}')
    data = _card(cards, card)
    if zone != 'workbench' and is_token(data):
        return _refusal('token_in_deck', {'name': data['name'], 'zone': zone})
    if zone != 'workbench' and _fit_reason(data, zone, None, []) == 'type':
        return _refusal('card_off_identity', _off_identity(data, zone, 'type'))
    if zone == 'runes':
        if not deck.get('legend'):
            return _refusal('legend_missing', _missing_slot())
        if rune_colour(data) not in identity(deck, cards):
            return _refusal('rune_off_identity', {'name': data['name']})
        runes = _total(deck, 'runes') + 1
        if runes > DECK_RULES['runes']:
            return _refusal('runes_count', _size(runes, DECK_RULES['runes']))
        return {'ok': True}
    if zone == 'battlefields':
        key = name_key(data['name'])
        for ref in _zone(deck, 'battlefields'):
            if name_key(_card(cards, ref)['name']) == key:
                return _refusal('battlefields_duplicate', {'name': _card(cards, ref)['name']})
        fields = len(_zone(deck, 'battlefields')) + 1
        if fields > DECK_RULES['battlefields']:
            return _refusal('battlefields_count', _size(fields, DECK_RULES['battlefields']))
        return {'ok': True}
    count = _copies_of(deck, cards, data['name'], COPY_ZONES) + 1
    if count > DECK_RULES['copies_max']:
        return _refusal('copies_over', _copies_params(deck, cards, data, count))
    return _zone_room(deck, cards, data, zone)


def can_move(deck, cards, card, from_zone, to_zone):
    """`{ok: True}` or `{ok: False, code, params}` for moving one copy of the printing
    `card` from `from_zone` to `to_zone` (main, sideboard, workbench).

    A move keeps the copy count, but the prototype rules are kept: workbench → main /
    sideboard needs room for one more copy in main + sideboard + champion, and the
    workbench holds at most 3 copies of a name.
    """
    if from_zone not in MOVE_ZONES or to_zone not in MOVE_ZONES or from_zone == to_zone:
        raise ValueError(f'unknown move: {from_zone} -> {to_zone}')
    if not any(line['set'] == card['set'] and line['id'] == card['id']
               for line in _zone(deck, from_zone)):
        raise ValueError(f'card not in {from_zone}')
    data = _card(cards, card)
    if to_zone != 'workbench' and is_token(data):
        return _refusal('token_in_deck', {'name': data['name'], 'zone': to_zone})
    if to_zone != 'workbench' and _fit_reason(data, to_zone, None, []) == 'type':
        return _refusal('card_off_identity', _off_identity(data, to_zone, 'type'))
    if from_zone == 'workbench':
        count = _copies_of(deck, cards, data['name'], ('main', 'sideboard')) + 1
    elif to_zone == 'workbench':
        count = _copies_of(deck, cards, data['name'], ('workbench',), champion=False) + 1
    else:
        count = 0
    if count > DECK_RULES['copies_max']:
        return _refusal('copies_over', _copies_params(deck, cards, data, count))
    return _zone_room(deck, cards, data, to_zone)


def _copies_params(deck, cards, data, count):
    name = copies(deck, cards).get(name_key(data['name']), [data['name']])[0]
    return {'name': name, 'count': count, 'max': DECK_RULES['copies_max']}


def _zone_room(deck, cards, data, zone):
    if zone == 'sideboard':
        sideboard = _total(deck, 'sideboard') + 1
        if sideboard > DECK_RULES['sideboard']:
            return _refusal('sideboard_size', _size(sideboard, DECK_RULES['sideboard']))
    if zone == 'workbench':
        names = _workbench_names(deck, cards)
        if name_key(data['name']) not in names and len(names) + 1 > DECK_RULES['workbench_max']:
            return _refusal('workbench_over', {'count': len(names) + 1,
                                               'max': DECK_RULES['workbench_max']})
    return {'ok': True}


# --- hard limits -----------------------------------------------------------------------------

def hard_limit_violations(deck, cards):
    """The F5-R9 hard limits `deck` breaks, as `deck_limit_exceeded` params
    `[{rule, max, name?}]` in HARD_RULES order (copies and token by `name_sort_key`)."""
    out = []
    over = [name for name, count in copies(deck, cards).values()
            if count > DECK_RULES['copies_max']]
    out += [{'rule': 'copies', 'max': DECK_RULES['copies_max'], 'name': name}
            for name in sorted(over, key=name_sort_key)]
    if _total(deck, 'sideboard') > DECK_RULES['sideboard']:
        out.append({'rule': 'sideboard', 'max': DECK_RULES['sideboard']})
    if len(_workbench_names(deck, cards)) > DECK_RULES['workbench_max']:
        out.append({'rule': 'workbench', 'max': DECK_RULES['workbench_max']})
    if len(_zone(deck, 'battlefields')) > DECK_RULES['battlefields']:
        out.append({'rule': 'battlefields', 'max': DECK_RULES['battlefields']})
    if _total(deck, 'runes') > DECK_RULES['runes']:
        out.append({'rule': 'runes', 'max': DECK_RULES['runes']})
    tokens = {}
    for zone, _ref, card, _qty in _entries(deck, cards):
        if zone != 'workbench' and is_token(card):
            tokens.setdefault(name_key(card['name']), card['name'])
    out += [{'rule': 'token', 'max': 0, 'name': name}
            for name in sorted(tokens.values(), key=name_sort_key)]
    return out


# --- deck operations -------------------------------------------------------------------------

def apply_legend(deck, cards, legend):
    """`{ok: True, deck}` with `legend` set (or removed with None), or a refusal.

    Purges the runes whose colour is not one of the new legend's colours and the champion
    when it shares no tag with it; the main deck, sideboard and workbench are untouched.
    """
    out = deepcopy(deck)
    if legend is not None:
        data = _card(cards, legend)
        if is_token(data):
            return _refusal('token_in_deck', {'name': data['name'], 'zone': 'legend'})
        if data.get('type') != 'Legend':
            return _refusal('card_off_identity', _off_identity(data, 'legend', 'type'))
    out['legend'] = deepcopy(legend)
    cols = identity(out, cards)
    out['runes'] = [line for line in _zone(out, 'runes')
                    if rune_colour(_card(cards, line)) in cols]
    if out.get('champion') and (legend is None or not share_tag(
            _card(cards, out['champion']), _card(cards, legend))):
        out['champion'] = None
    return {'ok': True, 'deck': out}


def apply_champion(deck, cards, champion):
    """`{ok: True, deck}` with `champion` chosen (or removed with None), or a refusal.

    The champion is a Champion Unit sharing a tag with the legend. When its name already
    has 3 copies in main + sideboard + workbench, copies are removed (main, then
    sideboard, then workbench; in each zone from the printing with the most copies, the
    first on ties; a line at 0 disappears) until the champion fits.
    """
    out = deepcopy(deck)
    if champion is None:
        out['champion'] = None
        return {'ok': True, 'deck': out}
    data = _card(cards, champion)
    if is_token(data):
        return _refusal('token_in_deck', {'name': data['name'], 'zone': 'champion'})
    if not is_champion_unit(data):
        return _refusal('card_off_identity', _off_identity(data, 'champion', 'type'))
    if not deck.get('legend'):
        return _refusal('legend_missing', _missing_slot())
    if not share_tag(data, _card(cards, deck['legend'])):
        return _refusal('champion_tag', {'name': data['name']})
    out['champion'] = deepcopy(champion)
    key = name_key(data['name'])
    while _copies_of(out, cards, data['name'], COPY_ZONES, champion=False) + 1 \
            > DECK_RULES['copies_max']:
        for zone in COPY_ZONES:
            lines = [line for line in _zone(out, zone)
                     if name_key(_card(cards, line)['name']) == key and line['qty'] > 0]
            if lines:
                line = max(lines, key=lambda item: item['qty'])
                line['qty'] -= 1
                if line['qty'] == 0:
                    out[zone] = [item for item in out[zone] if item is not line]
                break
    return {'ok': True, 'deck': out}


def auto_runes(deck, cards):
    """The deck with its runes balanced by colour demand (design-handoff §5.3).

    Demand of a legend colour = copies in the main deck (printing x qty) plus the chosen
    champion whose domains include it. Runes per colour = `floor(12 / colours)` without
    demand, else `max(1, floor(demand / total * 12 + 0.5))` (JS `Math.round`, never
    banker's rounding); then, over the colours ordered by runes descending (stable), one
    rune is taken from (while the sum is over 12, never below 1) or given to (while under)
    each colour in turn, at most 200 steps. Each colour uses the rune printing already in
    the deck, else the first rune of that colour in `cards` order; a colour without any
    rune card is skipped. Every previous rune is replaced. No legend or no colour: no-op.
    """
    out = deepcopy(deck)
    if not deck.get('legend'):
        return out
    rune_for = {}
    for line in _zone(deck, 'runes'):
        card = _card(cards, line)
        if card.get('type') == 'Rune':
            rune_for.setdefault(rune_colour(card), {'set': line['set'], 'id': line['id']})
    for (set_id, card_id), card in cards.items():
        if card.get('type') == 'Rune' and not is_token(card):
            rune_for.setdefault(rune_colour(card), {'set': set_id, 'id': card_id})
    cols = [colour for colour in identity(deck, cards) if colour in rune_for]
    if not cols:
        return out

    demand = {colour: 0 for colour in cols}
    counted = [(_card(cards, line), line['qty']) for line in _zone(deck, 'main')]
    if deck.get('champion'):
        counted.append((_card(cards, deck['champion']), 1))
    for card, qty in counted:
        for colour in cols:
            if colour in (card.get('domains') or []):
                demand[colour] += qty
    total = sum(demand.values())
    target = DECK_RULES['runes']
    if total == 0:
        runes = {colour: target // len(cols) for colour in cols}
    else:
        runes = {colour: max(1, floor(demand[colour] / total * target + 0.5)) for colour in cols}

    order = sorted(cols, key=lambda colour: -runes[colour])
    step = 0
    while sum(runes.values()) > target and step < 200:
        colour = order[step % len(order)]
        if runes[colour] > 1:
            runes[colour] -= 1
        step += 1
    while sum(runes.values()) < target and step < 200:
        runes[order[step % len(order)]] += 1
        step += 1

    out['runes'] = [dict(rune_for[colour], qty=runes[colour]) for colour in cols
                    if runes[colour] > 0]
    return out


def deck_domains(deck, cards):
    """The union of the domains (Colorless apart) of the legend, the champion and the main
    deck, in DOMAINS order, then unknown domains by `name_sort_key`."""
    found = set()
    for zone, _ref, card, _qty in _entries(deck, cards):
        if zone in ('legend', 'champion', 'main'):
            found.update(colours(card))
    known = [domain for domain in DOMAINS if domain in found]
    return known + sorted(found - set(DOMAINS), key=name_sort_key)
