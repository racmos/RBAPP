"""Card catalog helpers (F2-b S2-S4, S7): the single place that turns a raw
`rbcards` row into the clean `CardSummary` every screen uses.

Parsing follows the data as stored (IMG-2, D-F2-12): domains as written,
`rbcar_type` as "<supertype…> <Type>", tags comma-separated, ids with numeric
prefixes (`ogn_257` lives in folder `ogn/`). Base printings group all
printings of a name (F2-a `name_key`); prices and bans come from the caller.
"""
import re

from app.schemas.game_domain import CARD_TYPES, DOMAINS, RARITIES, SUPERTYPES
from app.services.bans import card_bans, name_key

_LEADING_DIGITS = re.compile(r'\d+')
_SPLIT_WORDS = re.compile(r'[\s,]+')

_COMMON_ORDER = ('common', 'uncommon')


def parse_domains(text):
    """Domains as a list, canonical casing, order kept, no duplicates."""
    if not text:
        return []
    seen = []
    for token in _SPLIT_WORDS.split(text):
        token = token.strip()
        if not token or token in seen:
            continue
        for domain in DOMAINS:
            if token.lower() == domain.lower():
                token = domain
                break
        if token not in seen:
            seen.append(token)
    return seen


def parse_type(text):
    """`(type, supertype)` from `rbcar_type`; unknown last word stays whole."""
    if not text or not text.strip():
        return None, None
    words = text.split()
    last = words[-1]
    for known in CARD_TYPES:
        if last.lower() == known.lower():
            head = []
            for word in words[:-1]:
                for supertype in SUPERTYPES:
                    if word.lower() == supertype.lower():
                        word = supertype
                        break
                head.append(word)
            return known, (' '.join(head) if head else None)
    return text.strip(), None


def parse_tags(text):
    """Comma-separated tags, stripped, no empties, order kept."""
    if not text:
        return []
    seen = []
    for tag in text.split(','):
        tag = tag.strip()
        if tag and tag not in seen:
            seen.append(tag)
    return seen


def card_number(card_id):
    """The leading digits of a card id as `int`, else `None`."""
    if not card_id:
        return None
    match = _LEADING_DIGITS.match(card_id)
    return int(match.group(0)) if match else None


def is_foilable(card_type, rarity):
    """Whether the card can exist as foil: never `Rune`, else common/uncommon."""
    if isinstance(card_type, str) and card_type.strip().lower() == 'rune':
        return False
    return isinstance(rarity, str) and rarity.strip().lower() in _COMMON_ORDER


def set_order(sets):
    """`{set_id: rank}` by release date ascending (NULL last), then set id."""
    ordered = sorted(sets, key=lambda s: (s.rbset_id or ''))
    ordered = sorted(ordered, key=lambda s: (s.rbset_outdat is None, s.rbset_outdat))
    return {s.rbset_id: rank for rank, s in enumerate(ordered)}


def natural_key(set_rank, card_id):
    """Sort key: set rank, then numeric card id (`2` before `10`, `t01` last)."""
    number = card_number(card_id)
    return (set_rank, number is None, number or 0, (card_id or '').casefold())


def rarity_rank(rarity):
    """Rank in `RARITIES` (lowest first); unknown rarities sort last."""
    if isinstance(rarity, str):
        for rank, known in enumerate(RARITIES):
            if rarity.lower() == known.lower():
                return rank
    return len(RARITIES)


def base_printing_keys(cards, set_rank):
    """`{(set_id, card_id)}` with one base printing per card name (D-F2-4).

    Candidates are the printings whose `card_id` is all digits; without any,
    every printing of the name is a candidate. The first candidate ordered by
    `(set_rank, number, card_id)` wins.
    """
    groups = {}
    for card in cards:
        groups.setdefault(name_key(card.rbcar_name), []).append(card)

    def order_key(card):
        number = card_number(card.rbcar_id)
        return (set_rank.get(card.rbcar_rbset_id, len(set_rank)),
                number if number is not None else float('inf'),
                (card.rbcar_id or '').casefold())

    bases = set()
    for group in groups.values():
        digit_only = [card for card in group
                      if isinstance(card.rbcar_id, str) and card.rbcar_id.isdigit()]
        bases.add(min(digit_only or group, key=order_key))
    return {(card.rbcar_rbset_id, card.rbcar_id) for card in bases}


def card_summary(card, *, set_rank, base_keys, price=None, bans=None, owned=None):
    """The `CardSummary` of the API contract, keys in contract order."""
    parsed_type, supertype = parse_type(card.rbcar_type)
    return {
        'set_id': card.rbcar_rbset_id,
        'card_id': card.rbcar_id,
        'key': f'{card.rbcar_rbset_id}-{card.rbcar_id}',
        'number': card_number(card.rbcar_id),
        'name': card.rbcar_name,
        'domains': parse_domains(card.rbcar_domain),
        'type': parsed_type,
        'supertype': supertype,
        'type_raw': card.rbcar_type,
        'tags': parse_tags(card.rbcar_tags),
        'energy': card.rbcar_energy,
        'power': card.rbcar_power,
        'might': card.rbcar_might,
        'rarity': card.rbcar_rarity,
        'artist': card.rbcar_artist,
        'image_src': card.image_src,
        'image_thumb_src': None,
        'foilable': is_foilable(parsed_type, card.rbcar_rarity),
        'is_base': (card.rbcar_rbset_id, card.rbcar_id) in base_keys,
        'price': price,
        'bans': card_bans(card.rbcar_name, bans),
        'owned': dict(owned) if owned is not None else {'total': 0, 'foil': 0},
    }
