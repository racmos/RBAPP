// Cards, zones and counts shared by the rule functions (the private helpers of
// `app/services/deck_rules.py`).
import { COLORLESS, COPY_ZONES, NOT_IN_DECK_TYPES, ZONE_ORDER } from './constants';
import { nameKey, splitWords } from './sortNames';
import type {
  Card,
  CardRef,
  Cards,
  DeckContent,
  DeckLine,
  FitReason,
  IssueCode,
  IssueParams,
  Refusal,
  SizeParams,
  SlotParams,
  Zone,
} from './types';

/** A deck or call references a card missing from `cards` (Python `UnknownCard`). */
export class UnknownCard extends Error {
  readonly ref: readonly [string, string];

  constructor(set: string, id: string) {
    super(`unknown card: ${set}-${id}`);
    this.name = 'UnknownCard';
    this.ref = [set, id];
  }
}

/** The `Cards` key of a printing (unambiguous whatever the set and id contain). */
export function cardKey(ref: CardRef): string {
  return JSON.stringify([ref.set, ref.id]);
}

/** The printing of a `cardKey`. */
export function refOfKey(key: string): CardRef {
  const [set, id] = JSON.parse(key) as [string, string];
  return { set, id };
}

/** `Cards` from `[ref, card]` pairs, in their order (a repeated ref keeps its first place). */
export function makeCards(entries: Iterable<readonly [CardRef, Card]>): Cards {
  const out = new Map<string, Card>();
  for (const [ref, card] of entries) out.set(cardKey(ref), card);
  return out;
}

export function getCard(cards: Cards, ref: CardRef): Card {
  const card = cards.get(cardKey(ref));
  if (card === undefined) throw new UnknownCard(ref.set, ref.id);
  return card;
}

/** A deck the operations may change: plain arrays of copied lines. */
export type DeckDraft = {
  -readonly [K in keyof DeckContent]: DeckContent[K] extends readonly (infer T)[]
    ? T[]
    : DeckContent[K];
};

/** A deep copy of plain JSON data (Python `deepcopy`). */
export function cloneData<T>(value: T): T {
  if (Array.isArray(value)) return value.map(cloneData) as T;
  if (value !== null && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [key, cloneData(item)]),
    ) as T;
  }
  return value;
}

export function cloneDeck(deck: DeckContent): DeckDraft {
  return cloneData(deck) as DeckDraft;
}

function supertypes(card: Card): string[] {
  return splitWords(card.supertype || '');
}

/** "Token Unit", "Token Battlefield", ... or a bare "Token" (no base type). */
export function isToken(card: Card): boolean {
  return supertypes(card).includes('Token') || card.type === 'Token';
}

export function isChampionUnit(card: Card): boolean {
  return supertypes(card).includes('Champion') && card.type === 'Unit';
}

export function isSignature(card: Card): boolean {
  return supertypes(card).includes('Signature');
}

/** The domains of a card without Colorless, in card order. */
export function colours(card: Card): string[] {
  return (card.domains || []).filter((domain) => domain !== COLORLESS);
}

export function runeColour(card: Card): string | null {
  const domains = card.domains || [];
  return domains.length > 0 ? domains[0] : null;
}

export function shareTag(a: Card, b: Card): boolean {
  const tags = new Set(b.tags || []);
  return (a.tags || []).some((tag) => tags.has(tag));
}

type ListZone = 'main' | 'runes' | 'battlefields' | 'sideboard' | 'workbench';

export function zoneOf(deck: DeckContent, zone: 'battlefields'): readonly CardRef[];
export function zoneOf(
  deck: DeckContent,
  zone: Exclude<ListZone, 'battlefields'>,
): readonly DeckLine[];
export function zoneOf(deck: DeckContent, zone: ListZone): readonly (CardRef | DeckLine)[];
export function zoneOf(deck: DeckContent, zone: ListZone): readonly (CardRef | DeckLine)[] {
  return deck[zone] || [];
}

export function total(deck: DeckContent, zone: Exclude<ListZone, 'battlefields'>): number {
  return zoneOf(deck, zone).reduce((sum, line) => sum + line.qty, 0);
}

export type Entry = { zone: Zone; ref: CardRef; card: Card; qty: number };

/** Every card of the deck, in ZONE_ORDER. */
export function entries(deck: DeckContent, cards: Cards): Entry[] {
  const out: Entry[] = [];
  for (const zone of ZONE_ORDER) {
    if (zone === 'legend' || zone === 'champion') {
      const ref = deck[zone];
      if (ref) out.push({ zone, ref, card: getCard(cards, ref), qty: 1 });
    } else {
      for (const line of zoneOf(deck, zone)) {
        const qty = 'qty' in line ? line.qty : 1;
        out.push({ zone, ref: line, card: getCard(cards, line), qty });
      }
    }
  }
  return out;
}

/** The legend's colours (its domains without Colorless); `[]` without a legend. */
export function identity(deck: DeckContent, cards: Cards): string[] {
  return deck.legend ? colours(getCard(cards, deck.legend)) : [];
}

/** `nameKey → {name, count}` over main + sideboard + workbench + the chosen champion; `name`
 * is the first occurrence in ZONE_ORDER. */
export function copies(
  deck: DeckContent,
  cards: Cards,
): Map<string, { name: string; count: number }> {
  const counts = new Map<string, { name: string; count: number }>();
  for (const { zone, card, qty } of entries(deck, cards)) {
    if (zone === 'champion' || (COPY_ZONES as readonly string[]).includes(zone)) {
      const key = nameKey(card.name);
      let entry = counts.get(key);
      if (!entry) {
        entry = { name: card.name, count: 0 };
        counts.set(key, entry);
      }
      entry.count += qty;
    }
  }
  return counts;
}

export function copiesOf(
  deck: DeckContent,
  cards: Cards,
  name: string,
  zones: readonly Exclude<ListZone, 'battlefields'>[],
  champion = true,
): number {
  const key = nameKey(name);
  let count = 0;
  for (const zone of zones) {
    for (const line of zoneOf(deck, zone)) {
      if (nameKey(getCard(cards, line).name) === key) count += line.qty;
    }
  }
  if (champion && deck.champion && nameKey(getCard(cards, deck.champion).name) === key) count += 1;
  return count;
}

export function workbenchNames(deck: DeckContent, cards: Cards): Set<string> {
  return new Set(zoneOf(deck, 'workbench').map((line) => nameKey(getCard(cards, line).name)));
}

export function size(have: number, need: number): SizeParams {
  return { have, need, missing: Math.max(0, need - have), over: Math.max(0, have - need) };
}

export function missingSlot(): SlotParams {
  return { have: 0, need: 1, missing: 1 };
}

export function refusal<C extends IssueCode>(code: C, params: IssueParams[C]): Refusal {
  return { ok: false, code, params } as Refusal;
}

export function offIdentity(card: Card, zone: Zone, reason: FitReason) {
  return { name: card.name, zone, reason };
}

/**
 * Why `card` does not fit `zone` (`'type'`, `'domain'`, `'tag'`), or null. The type rules
 * always apply; colour and Signature tag only with a legend. Tokens are reported apart.
 */
export function fitReason(
  card: Card,
  zone: Zone,
  legend: Card | null,
  cols: readonly string[],
): FitReason | null {
  const type = card.type;
  if (zone === 'legend') return type === 'Legend' ? null : 'type';
  if (zone === 'champion') return isChampionUnit(card) ? null : 'type';
  if (zone === 'battlefields') return type === 'Battlefield' ? null : 'type';
  if (zone === 'runes') return type === 'Rune' ? null : 'type';
  if (zone === 'main' || zone === 'sideboard') {
    if (type != null && NOT_IN_DECK_TYPES.includes(type)) return 'type';
    if (legend === null) return null;
    if (isSignature(card) && !shareTag(card, legend)) return 'tag';
    if (colours(card).some((domain) => !cols.includes(domain))) return 'domain';
  }
  return null;
}
