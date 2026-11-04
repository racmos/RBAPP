"""The common deck text format (F5-e, F5-R10): parse, resolve, place and format, pure.

The format every deck site exports (owner sample `docs/requirements/F5/samples/
deck-export-text-1.txt`): blocks `Legend:`, `Champion:`, `MainDeck:`, `Battlefields:`,
`Rune Pool:` and `Sideboard:`, each with `N Card Name` lines. Nothing here touches Flask or the
database: the caller passes the catalog (`{(set, id): card}` with the rules engine fields,
`deck_migration.catalog_card`) and the base printings.

Import (owner, 2026-11-04): the text always loads. Nothing is dropped silently: every line that
does not land as written gives a warning `{line, text, reason_code, params}`; a card in a block
its type does not belong to stays in that block (`wrong_zone`, legality flags it) and hard
limits are kept and reported (`hard_limit`). Only unknown or ambiguous names stay out of the
content (a content ref must name a printing).

Export: blocks in the order above, a blank line between blocks, empty blocks omitted, the
workbench never exported. Lines keep the content order (the order the deck was imported or
built in), one line per name with its total; a legend prints `Tag, Name` (the catalog stores
legends with the bare name and the champion in the tags, F5-a L14).
"""
import re
import unicodedata

from app.services import deck_rules
from app.services.bans import name_key

FORMATS = ('auto', 'text')
REASON_CODES = ('no_zone', 'zone_unknown', 'quantity_invalid', 'unknown_card',
                'ambiguous_card', 'wrong_zone', 'slot_taken', 'hard_limit')
# Export order and header of each block.
BLOCKS = (('legend', 'Legend'), ('champion', 'Champion'), ('main', 'MainDeck'),
          ('battlefields', 'Battlefields'), ('runes', 'Rune Pool'), ('sideboard', 'Sideboard'))
QTY_MAX = 99
SLOT_ZONES = ('legend', 'champion')

_HEADERS = {
    'legend': ('legend', 'legends', 'leyenda', 'leyendas'),
    'champion': ('champion', 'champions', 'chosen champion', 'campeón', 'campeon',
                 'campeones'),
    'main': ('maindeck', 'main deck', 'main', 'mazo principal'),
    'battlefields': ('battlefield', 'battlefields', 'campo de batalla', 'campos de batalla'),
    'runes': ('rune pool', 'runes', 'rune', 'runa', 'runas'),
    'sideboard': ('sideboard', 'side board', 'banquillo'),
}
_HEADER_ZONE = {alias: zone for zone, aliases in _HEADERS.items() for alias in aliases}
_QTY_LINE = re.compile(r'^(\d+)\s*[xX]?\s+(.+)$')
_PAREN = re.compile(r'^(.*?)\s*\(([^()]*)\)\s*$')
_CARD_ID = re.compile(r'^([A-Za-z0-9]+)[- ]([A-Za-z0-9*]+)$')
_COLONS = ':：'
_LINES = re.compile(r'\r\n|\r|\n')


def _warning(line, text, code, params=None):
    return {'line': line, 'text': text, 'reason_code': code, 'params': params or {}}


# --- parse -----------------------------------------------------------------------------------

def _header(text):
    """`(is_header, zone)`: a known header gives its zone, any other `...:` line None."""
    bare = ' '.join(text.rstrip(_COLONS).split()).casefold()
    if bare in _HEADER_ZONE:
        return True, _HEADER_ZONE[bare]
    if text[-1] in _COLONS and not text[0].isdigit():
        return True, None
    return False, None


def parse_text(text):
    """`{blocks, lines: [{line, zone, qty, name}], warnings}` of a deck text.

    Lines are 1-based. A line before any header, or after an unknown one, has zone None
    (`no_zone`); the same name twice in a block is one line (first line number, quantities
    added); a quantity outside 1..99 is `quantity_invalid` and the line is skipped.
    """
    blocks, lines, warnings, merged = [], [], [], {}
    zone = None
    for number, raw in enumerate(_LINES.split(text), start=1):
        stripped = raw.strip()
        if not stripped:
            continue
        is_header, header_zone = _header(stripped)
        if is_header:
            zone = header_zone
            if zone is None:
                warnings.append(_warning(number, stripped, 'zone_unknown'))
            elif zone not in blocks:
                blocks.append(zone)
            continue
        match = _QTY_LINE.match(stripped)
        qty, name = (int(match.group(1)), match.group(2).strip()) if match else (1, stripped)
        if not 1 <= qty <= QTY_MAX:
            warnings.append(_warning(number, stripped, 'quantity_invalid'))
            continue
        if zone is None:
            warnings.append(_warning(number, stripped, 'no_zone'))
        key = (zone, name_key(name))
        if key in merged:
            merged[key]['qty'] += qty
            continue
        merged[key] = {'line': number, 'zone': zone, 'qty': qty, 'name': name,
                       'text': stripped}
        lines.append(merged[key])
    return {'blocks': blocks, 'lines': lines, 'warnings': warnings}


# --- resolve ---------------------------------------------------------------------------------

def _fold(key):
    """`key` without accents (the last resort of the name match)."""
    return ''.join(c for c in unicodedata.normalize('NFKD', key)
                   if not unicodedata.combining(c))


class Resolver:
    """Card text -> printing: an explicit id (`SET-ID`, also in a final parenthesis), else the
    `name_key` of the name, else a legend written `Tag, Name`, else the name without accents.
    A name gives its base printing (`base_keys`), else its first printing by (set, id)."""

    def __init__(self, cards, base_keys):
        self.by_id, self.by_name, self.by_fold, self.legends = {}, {}, {}, {}
        for key in sorted(cards):
            card = cards[key]
            self.by_id[(key[0].casefold(), key[1].casefold())] = key
            nkey = name_key(card['name'])
            self.by_name.setdefault(nkey, []).append(key)
            self.by_fold.setdefault(_fold(nkey), set()).add(nkey)
            if card.get('type') == 'Legend':
                for tag in card.get('tags') or []:
                    self.legends.setdefault((name_key(tag), nkey), nkey)
        self.base_keys = base_keys

    def _pick(self, nkey):
        keys = self.by_name[nkey]
        return next((key for key in keys if key in self.base_keys), keys[0])

    def _id(self, text):
        match = _CARD_ID.match(text.strip())
        return self.by_id.get((match.group(1).casefold(), match.group(2).casefold())) \
            if match else None

    def resolve(self, text):
        """`(key, None)` or `(None, 'unknown_card' | 'ambiguous_card')`."""
        paren = _PAREN.match(text)
        if paren:
            key = self._id(paren.group(2))
            if key:
                return key, None
            text = paren.group(1) or text
        key = self._id(text)
        if key:
            return key, None
        nkey = name_key(text)
        if nkey in self.by_name:
            return self._pick(nkey), None
        if ',' in nkey:
            tag, rest = nkey.split(',', 1)
            legend = self.legends.get((tag.strip(), rest.strip()))
            if legend:
                return self._pick(legend), None
        folded = self.by_fold.get(_fold(nkey), set())
        if len(folded) == 1:
            return self._pick(next(iter(folded))), None
        return None, 'ambiguous_card' if folded else 'unknown_card'


# --- place -----------------------------------------------------------------------------------

def _zone_by_type(card):
    if card.get('type') == 'Legend':
        return 'legend'
    if deck_rules.is_champion_unit(card):
        return 'champion'
    if card.get('type') == 'Battlefield':
        return 'battlefields'
    if card.get('type') == 'Rune':
        return 'runes'
    return 'main'


def _empty():
    return {'v': 2, 'legend': None, 'champion': None, 'main': [], 'runes': [],
            'battlefields': [], 'sideboard': [], 'workbench': []}


def _add_line(content, zone, key, qty):
    for item in content[zone]:
        if (item['set'], item['id']) == key:
            item['qty'] += qty
            return
    content[zone].append({'set': key[0], 'id': key[1], 'qty': qty})


def build_content(parsed, resolver, cards):
    """`(content v2, warnings, counts)` of a parsed text.

    Blocks are kept as written; a line without a block goes where its type belongs. Legend
    and champion take one card: the other copies of a legend go to the workbench, those of a
    champion block to the main deck (`slot_taken`). Battlefields keep every copy. Warnings
    come in line order, then the hard limits (`hard_limit_violations`). `counts` are
    `{lines, copies, unresolved}` (copies placed or not)."""
    content, warnings = _empty(), list(parsed['warnings'])
    copies = unresolved = 0
    for item in parsed['lines']:
        key, problem = resolver.resolve(item['name'])
        if key is None:
            warnings.append(_warning(item['line'], item['text'], problem))
            unresolved += item['qty']
            continue
        card = cards[key]
        zone, qty = item['zone'], item['qty']
        copies += qty
        if zone is None:
            zone = _zone_by_type(card)
        elif zone != 'workbench' and deck_rules._fit_reason(card, zone, None, []) == 'type':
            warnings.append(_warning(item['line'], item['text'], 'wrong_zone',
                                     {'name': card['name'], 'zone': zone}))
        ref = {'set': key[0], 'id': key[1]}
        if zone in SLOT_ZONES:
            if content[zone] is None:
                content[zone] = ref
                qty -= 1
            if qty:
                to = 'workbench' if zone == 'legend' else 'main'
                _add_line(content, to, key, qty)
                warnings.append(_warning(item['line'], item['text'], 'slot_taken',
                                         {'name': card['name'], 'zone': zone, 'to': to,
                                          'qty': qty}))
        elif zone == 'battlefields':
            content[zone].extend(dict(ref) for _ in range(qty))
        else:
            _add_line(content, zone, key, qty)
    warnings.sort(key=lambda w: w['line'])
    for violation in deck_rules.hard_limit_violations(content, cards):
        name = f': {violation["name"]}' if 'name' in violation else ''
        warnings.append(_warning(None, f'{violation["rule"]} (max {violation["max"]}){name}',
                                 'hard_limit', violation))
    return content, warnings, {'lines': len(parsed['lines']), 'copies': copies,
                               'unresolved': unresolved}


# --- format ----------------------------------------------------------------------------------

def card_label(card, zone=None):
    """The text name of a card: a legend `Tag, Name` with its first tag, unless the name
    already starts with one of its tags."""
    name = card['name']
    tags = card.get('tags') or []
    if card.get('type') != 'Legend' or not tags:
        return name
    if any(name_key(name).startswith(name_key(tag) + ',') for tag in tags):
        return name
    return f'{tags[0]}, {name}'


def format_text(content, cards):
    """The deck as text (module docstring); `''` for an empty deck. A printing missing from
    `cards` prints as `SET-ID` (the import resolves it back)."""
    out = []
    for zone, header in BLOCKS:
        value = content.get(zone)
        items = ([dict(value, qty=1)] if value else []) if zone in SLOT_ZONES else \
            [dict(item, qty=item.get('qty', 1)) for item in value or []]
        totals = {}
        for item in items:
            key = (item['set'], item['id'])
            label = card_label(cards[key]) if key in cards else f'{key[0]}-{key[1]}'
            totals[label] = totals.get(label, 0) + item['qty']
        if totals:
            out.append(f'{header}:\n' + ''.join(f'{qty} {label}\n'
                                                for label, qty in totals.items()))
    return '\n'.join(out)
