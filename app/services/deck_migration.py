"""Copy of the legacy decks into decks v2 (F5-c, F5-R7): `flask decks migrate [--dry-run]`.

`route_deck` is pure: one legacy `rbdck_cards` value (`{"main": [line], "sideboard": [line]}`)
plus the catalog give the v2 content (`app/schemas/deck_content.py`), the notes that explain
every card that did not land where it was, and the lines that could not be stored. Card
classes (token, Champion Unit, shared tag), sizes and hard limits come from the rules engine
(`app/services/deck_rules.py`, `DECK_RULES`); nothing here re-states a rule.

Routing of the legacy main deck, in line order: the first Legend is the legend; the first
Champion Unit sharing a tag with it is the champion (one copy; the other copies and the
other champions stay in the main deck); Battlefields fill the 3 battlefield slots with
distinct names; Runes fill the 12 runes; tokens, extra legends and the battlefield and rune
overflow go to the workbench; the rest is the main deck. The legacy sideboard stays the
sideboard up to 10 cards (tokens and overflow go to the workbench). A line whose card is not
in the catalog, or that is not a `{set, id, qty}` line, is left out of the content (a v2
version only holds resolvable cards), listed in `unresolved` and named in the version note.

`plan_migration` / `apply_plan` copy every `rbdecks` row once (tracked by
`rbdkv_legacy_id`): one head per (user, name) with the mode of the latest row, one version
per row with its seq. `rbdecks` is only read.
"""
import json

from app import db
from app.models import RbCard, RbDeck, RbDeckHead, RbDeckVersion, User
from app.models.deck_v2 import NAME_MAX_LENGTH, NOTE_MAX_LENGTH
from app.schemas.deck_content import empty_content, validate_content
from app.schemas.game_domain import DECK_RULES, GAME_MODES
from app.services import deck_rules
from app.services.bans import name_key
from app.services.catalog import parse_domains, parse_tags, parse_type

LEGACY_ZONES = ('main', 'sideboard')
DEFAULT_MODE = GAME_MODES[0]
_MOVED = {
    'legend': 'extra legend {label} x{qty} -> workbench',
    'battlefield': 'battlefield {label} x{qty} -> workbench',
    'token': 'token {label} x{qty} ({zone}) -> workbench',
    'rune': 'rune over %d: {label} x{qty} -> workbench' % DECK_RULES['runes'],
    'sideboard': 'sideboard over %d: {label} x{qty} -> workbench' % DECK_RULES['sideboard'],
}


# --- catalog -------------------------------------------------------------------------------

def catalog_card(card):
    """The fields the rules engine reads, parsed like `CardSummary` (`catalog.py`)."""
    card_type, supertype = parse_type(card.rbcar_type)
    return {'name': card.rbcar_name, 'type': card_type, 'supertype': supertype,
            'domains': parse_domains(card.rbcar_domain), 'tags': parse_tags(card.rbcar_tags)}


def load_catalog():
    """`{(set_id, card_id): card}` for every card of the catalog."""
    return {(c.rbcar_rbset_id, c.rbcar_id): catalog_card(c)
            for c in RbCard.query.order_by(RbCard.rbcar_rbset_id, RbCard.rbcar_id)}


# --- routing (pure) --------------------------------------------------------------------------

def _qty(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, str) and value.isdigit():
        value = int(value)
    return value if isinstance(value, int) and value >= 1 else None


def _label(key, card=None):
    return f'{key[0]}-{key[1]}' + (f' "{card["name"]}"' if card else '')


def _parse(raw):
    """`(entries, problems)`: `entries` are `[zone, key, card-or-None, qty, label]` in zone
    and line order (`card` None = an unresolved line, `label` says why); `problems` are
    the unresolved parts that are not lines (another shape, an unknown key)."""
    entries, problems = [], []
    if raw is None:
        return entries, problems
    if not isinstance(raw, dict):
        return entries, [('deck', 'cards are not an object')]
    for zone in LEGACY_ZONES:
        lines = raw.get(zone)
        if lines is None:
            continue
        if not isinstance(lines, list):
            problems.append((zone, f'{zone} is not a list'))
            continue
        for item in lines:
            if (isinstance(item, dict) and isinstance(item.get('set'), str)
                    and isinstance(item.get('id'), str) and _qty(item.get('qty'))):
                key, qty = (item['set'], item['id']), _qty(item['qty'])
                entries.append([zone, key, None, qty, f'{_label(key)} x{qty}'])
            else:
                text = json.dumps(item, sort_keys=True, ensure_ascii=False, default=str)
                entries.append([zone, None, None, 0, f'invalid line {text}'])
    problems += [(key, f'unknown key "{key}"') for key in sorted(raw, key=str)
                 if key not in LEGACY_ZONES]
    return entries, problems


class _Router:
    def __init__(self, cards):
        self.cards = cards
        self.zones = {zone: {} for zone in ('main', 'runes', 'sideboard', 'workbench')}
        self.battlefields = []
        self.moved = {}          # (kind, key, zone) -> [label, qty], first-seen order
        self.notes = []          # (order, text) for the unresolved lines, kept in place
        self.unresolved = []

    def put(self, zone, key, qty):
        if qty > 0:
            self.zones[zone][key] = self.zones[zone].get(key, 0) + qty

    def to_workbench(self, kind, key, card, qty, zone):
        if qty <= 0:
            return
        self.put('workbench', key, qty)
        entry = self.moved.setdefault((kind, key, zone), [_label(key, card), 0])
        entry[1] += qty
        self.notes.append(('moved', (kind, key, zone)))

    def left_out(self, zone, label, why):
        self.unresolved.append({'zone': zone, 'label': label})
        self.notes.append(('text', f'unresolved {label} ({zone}): {why}'))

    def lines(self, zone):
        return [{'set': key[0], 'id': key[1], 'qty': qty}
                for key, qty in self.zones[zone].items()]

    def rendered_notes(self):
        out, seen = [], set()
        for kind, value in self.notes:
            if kind == 'text':
                out.append(value)
            elif value not in seen:
                seen.add(value)
                label, qty = self.moved[value]
                out.append(_MOVED[value[0]].format(label=label, qty=qty, zone=value[2]))
        return out


def route_deck(raw, cards):
    """`{content, notes, unresolved}` for one legacy `rbdck_cards` value (F5-R7).

    `content` is v2 content holding only cards of `cards`; `notes` explain, in line order,
    each card moved to the workbench, each line left out, an empty champion slot and the
    hard limits the content still breaks; `unresolved` lists `{zone, label}` of what was
    left out. Neither input is modified.
    """
    entries, problems = _parse(raw)
    router = _Router(cards)
    for entry in entries:
        if entry[1] is not None:
            entry[2] = cards.get(entry[1])
    resolved = [e for e in entries if e[2] is not None]
    main = [e for e in resolved if e[0] == 'main' and not deck_rules.is_token(e[2])]

    legend = next((e for e in main if e[2].get('type') == 'Legend'), None)
    champion = None
    if legend:
        legend[3] -= 1
        champion = next((e for e in main if deck_rules.is_champion_unit(e[2])
                         and deck_rules.share_tag(e[2], legend[2]) and e[3] > 0), None)
        if champion:
            champion[3] -= 1

    sideboard_room = DECK_RULES['sideboard']
    for zone, key, card, qty, label in entries:
        if key is None:
            router.left_out(zone, label, 'left out')
        elif card is None:
            router.left_out(zone, label, 'not in the catalog, left out')
        elif deck_rules.is_token(card):
            router.to_workbench('token', key, card, qty, zone)
        elif zone == 'sideboard':
            take = min(qty, sideboard_room)
            sideboard_room -= take
            router.put('sideboard', key, take)
            router.to_workbench('sideboard', key, card, qty - take, zone)
        elif card.get('type') == 'Legend':
            router.to_workbench('legend', key, card, qty, zone)
        elif card.get('type') == 'Battlefield':
            for _copy in range(qty):
                names = {name_key(cards[(ref['set'], ref['id'])]['name'])
                         for ref in router.battlefields}
                if (name_key(card['name']) not in names
                        and len(router.battlefields) < DECK_RULES['battlefields']):
                    router.battlefields.append({'set': key[0], 'id': key[1]})
                else:
                    router.to_workbench('battlefield', key, card, 1, zone)
        elif card.get('type') == 'Rune':
            take = min(qty, DECK_RULES['runes'] - sum(router.zones['runes'].values()))
            router.put('runes', key, take)
            router.to_workbench('rune', key, card, qty - take, zone)
        else:
            router.put('main', key, qty)
    for zone, label in problems:
        router.left_out(zone, label, 'left out')

    content = empty_content()
    content.update(main=router.lines('main'), runes=router.lines('runes'),
                   battlefields=router.battlefields, sideboard=router.lines('sideboard'),
                   workbench=router.lines('workbench'))
    if legend:
        content['legend'] = {'set': legend[1][0], 'id': legend[1][1]}
    if champion:
        content['champion'] = {'set': champion[1][0], 'id': champion[1][1]}
    content = validate_content(content)

    notes = router.rendered_notes()
    if not entries and not problems:
        notes.append('no cards')
    if legend and not champion:
        notes.append('no Champion Unit shares a tag with the legend: champion left empty')
    elif not legend and any(deck_rules.is_champion_unit(e[2]) for e in main):
        notes.append('no legend: champion left empty')
    for limit in deck_rules.hard_limit_violations(content, cards):
        name = f': "{limit["name"]}"' if 'name' in limit else ''
        notes.append(f'hard limit {limit["rule"]} (max {limit["max"]}){name}')
    return {'content': content, 'notes': notes, 'unresolved': router.unresolved}


# --- plan, report, apply ---------------------------------------------------------------------

def _plural(count, word):
    return f'{count} {word}' + ('' if count == 1 else 's')


def _slot(content, zone, cards):
    ref = content[zone]
    if not ref:
        return 'none'
    key = (ref['set'], ref['id'])
    return _label(key, cards[key])


def _summary(content, cards):
    done = deck_rules.completeness(content)
    sized = '; '.join(f'{zone} {done[zone]["have"]}/{done[zone]["need"]}'
                      for zone in ('main', 'runes', 'battlefields', 'sideboard'))
    workbench = sum(line['qty'] for line in content['workbench'])
    return (f'legend {_slot(content, "legend", cards)}; '
            f'champion {_slot(content, "champion", cards)}; {sized}; workbench {workbench}')


def _version_note(legacy_id, unresolved):
    note = f'Migrated from rbdecks #{legacy_id}.'
    if unresolved:
        note += ' Left out: ' + ', '.join(u['label'] for u in unresolved) + '.'
    return note if len(note) <= NOTE_MAX_LENGTH else note[:NOTE_MAX_LENGTH - 1] + '…'


def _free_name(name, user_id, taken):
    """`(name, notes)`: the legacy name cut to the column size, made unique for the user."""
    notes = []
    if len(name) > NAME_MAX_LENGTH:
        name = name[:NAME_MAX_LENGTH]
        notes.append(f'name longer than {NAME_MAX_LENGTH} characters: shortened')
    candidate, n = name, 1
    while (user_id, candidate) in taken:
        n += 1
        suffix = f' ({n})'
        candidate = name[:NAME_MAX_LENGTH - len(suffix)] + suffix
    if candidate != name:
        notes.append(f'name taken: renamed to "{candidate}"')
    taken.add((user_id, candidate))
    return candidate, notes


def plan_migration(cards=None):
    """What `apply_plan` would do, one entry per legacy (user, name) in code-point order.

    Entry: `{user, legacy_name, status: new|update|current|skipped, name, mode, user_id,
    head_id, created_at, updated_at, notes, versions}`; version: `{legacy_id, seq,
    created_at, content, notes, unresolved, note, summary}`. Reads only.
    """
    cards = load_catalog() if cards is None else cards
    groups = {}
    for row in RbDeck.query.order_by(RbDeck.id):
        groups.setdefault((row.rbdck_user, row.rbdck_name), []).append(row)
    users = {u.username: u.id for u in User.query}
    copied = {legacy_id for (legacy_id,) in db.session.query(RbDeckVersion.rbdkv_legacy_id)
              if legacy_id is not None}
    heads = RbDeckHead.query.all()
    by_legacy = {(h.rbdkh_user_id, h.rbdkh_legacy_name): h for h in heads
                 if h.rbdkh_legacy_name is not None}
    taken_names = {(h.rbdkh_user_id, h.rbdkh_name) for h in heads}

    plan = []
    for (user, legacy_name) in sorted(groups):
        rows = sorted(groups[(user, legacy_name)], key=lambda r: (r.rbdck_seq or 1, r.id))
        entry = {'user': user, 'legacy_name': legacy_name, 'user_id': users.get(user),
                 'head_id': None, 'notes': [], 'versions': []}
        plan.append(entry)
        if entry['user_id'] is None:
            entry['status'] = 'skipped'
            continue
        head = by_legacy.get((entry['user_id'], legacy_name))
        pending = [r for r in rows if r.id not in copied]
        if head is not None:
            entry.update(status='update' if pending else 'current', name=head.rbdkh_name,
                         mode=head.rbdkh_mode, head_id=head.rbdkh_id)
            seqs = {seq for (seq,) in db.session.query(RbDeckVersion.rbdkv_seq).filter(
                RbDeckVersion.rbdkv_deck_id == head.rbdkh_id)}
        else:
            name, notes = _free_name(legacy_name, entry['user_id'], taken_names)
            mode = rows[-1].rbdck_mode
            if mode not in GAME_MODES:
                notes.append(f'mode {json.dumps(mode)} is not a game mode: {DEFAULT_MODE}')
                mode = DEFAULT_MODE
            entry.update(status='new', name=name, mode=mode, notes=notes,
                         created_at=min(r.rbdck_snapshot for r in rows))
            seqs = set()
        for row in pending:
            notes, seq = [], row.rbdck_seq or 1
            if seq in seqs:
                new_seq = max(seqs) + 1
                notes.append(f'seq {seq} taken: stored as {new_seq}')
                seq = new_seq
            seqs.add(seq)
            routed = route_deck(row.rbdck_cards, cards)
            notes += routed['notes']
            if row.rbdck_description:
                notes.append('description not copied (it stays in rbdecks)')
            entry['versions'].append({
                'legacy_id': row.id, 'seq': seq, 'created_at': row.rbdck_snapshot,
                'content': routed['content'], 'notes': notes,
                'unresolved': routed['unresolved'],
                'note': _version_note(row.id, routed['unresolved']),
                'summary': _summary(routed['content'], cards)})
    return plan


def unresolved_count(plan):
    return sum(len(v['unresolved']) for entry in plan for v in entry['versions'])


def report_lines(plan):
    """The per-deck report `flask decks migrate` prints, ending with the totals line."""
    out, counts = [], {'new': 0, 'update': 0, 'current': 0, 'skipped': 0}
    for entry in plan:
        counts[entry['status']] += 1
        status = entry['status']
        n = len(entry['versions'])
        what = {'new': f'new deck "{entry.get("name")}", mode {entry.get("mode")}, '
                       f'{_plural(n, "version")}',
                'update': f'{_plural(n, "new version")} for deck "{entry.get("name")}"',
                'current': 'up to date',
                'skipped': 'user not found, skipped'}[status]
        out.append(f'Deck {entry["user"]} / "{entry["legacy_name"]}": {what}')
        out += [f'  - {note}' for note in entry['notes']]
        for version in entry['versions']:
            out.append(f'  seq {version["seq"]} (rbdecks #{version["legacy_id"]}, '
                       f'{version["created_at"]:%Y-%m-%d %H:%M}): {version["summary"]}')
            out += [f'    - {note}' for note in version['notes']]
    versions = sum(len(entry['versions']) for entry in plan)
    out.append(f'Total: {_plural(len(plan), "deck")} ({counts["new"]} new, '
               f'{counts["update"]} updated, {counts["current"]} up to date, '
               f'{counts["skipped"]} skipped), {_plural(versions, "version")}, '
               f'{_plural(unresolved_count(plan), "unresolved line")}.')
    return out


def apply_plan(plan):
    """Write the plan in the caller's transaction (the caller commits or rolls back).
    Returns `{created, updated, versions}`."""
    result = {'created': 0, 'updated': 0, 'versions': 0}
    for entry in plan:
        if entry['status'] not in ('new', 'update'):
            continue
        if entry['status'] == 'new':
            head = RbDeckHead(rbdkh_user_id=entry['user_id'], rbdkh_name=entry['name'],
                              rbdkh_mode=entry['mode'], rbdkh_visibility='private',
                              rbdkh_legacy_name=entry['legacy_name'],
                              rbdkh_created_at=entry['created_at'],
                              rbdkh_updated_at=entry['created_at'])
            db.session.add(head)
            db.session.flush()
            result['created'] += 1
        else:
            head = db.session.get(RbDeckHead, entry['head_id'])
            result['updated'] += 1
        for version in entry['versions']:
            db.session.add(RbDeckVersion(
                rbdkv_deck_id=head.rbdkh_id, rbdkv_seq=version['seq'],
                rbdkv_content=version['content'], rbdkv_note=version['note'],
                rbdkv_legacy_id=version['legacy_id'], rbdkv_created_at=version['created_at']))
            head.rbdkh_updated_at = max(head.rbdkh_updated_at, version['created_at'])
            result['versions'] += 1
        db.session.flush()
        current = (RbDeckVersion.query.filter_by(rbdkv_deck_id=head.rbdkh_id)
                   .order_by(RbDeckVersion.rbdkv_seq.desc()).first())
        head.rbdkh_current_version_id = current.rbdkv_id
    db.session.flush()
    return result
