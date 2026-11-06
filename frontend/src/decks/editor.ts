import type {
  CardMini,
  CardSummary,
  DeckCard,
  DeckContentV2,
  DeckRef,
  DeckRefLine,
  DeckUnknownCard,
} from '@/api/types';
import { makeCards, type Cards } from './rules';
import { refKey } from './labels';

/**
 * Plain operations on a content v2 for the editor (F5-h stage 2). They never check a rule: the
 * screen asks `canAdd` / `canMove` / `applyLegend` / `applyChampion` first. Inputs are never
 * changed; every operation returns a new content.
 */

/** The cards the editor knows, keyed `"<set>-<id>"`: the deck's, plus the ones searched. */
export type CardBook = Readonly<Record<string, DeckCard>>;
export type LineZone = 'main' | 'runes' | 'sideboard' | 'workbench';
export type EditZone = LineZone | 'battlefields';

export const bookOf = (cards: Record<string, DeckCard>): CardBook => ({ ...cards });

/** The rules library's `Cards` of a book (any `DeckCard` is a valid rules card). */
export const rulesCardsOf = (book: CardBook): Cards =>
  makeCards(Object.values(book).map((card) => [{ set: card.set_id, id: card.card_id }, card]));

/** A card of `GET /cards` as a `DeckCard`. */
export function toDeckCard(card: CardSummary): DeckCard {
  return {
    set_id: card.set_id,
    card_id: card.card_id,
    key: card.key,
    name: card.name,
    domains: card.domains,
    type: card.type,
    supertype: card.supertype,
    rarity: card.rarity,
    image_src: card.image_src,
    image_thumb_src: card.image_thumb_src,
    is_base: card.is_base,
    market: card.price?.market ?? null,
    owned_total: card.owned.total,
    tags: card.tags,
    energy: card.energy,
    power: card.power,
    might: card.might,
    // the list endpoint does not count printings; the saved deck reports the real values
    variants: 1,
    keywords: [],
  };
}

/** The deck card of another printing of `card` (a `printings` item of `GET /cards/<set>/<id>`):
 *  the game facts are the card's, the printing's own are its set, id, art, rarity, price and the
 *  caller's copies. */
export function printingCard(card: DeckCard, printing: CardMini): DeckCard {
  return {
    ...card,
    set_id: printing.set_id,
    card_id: printing.card_id,
    key: printing.key,
    rarity: printing.rarity,
    image_src: printing.image_src,
    image_thumb_src: printing.image_thumb_src,
    is_base: printing.is_base,
    market: printing.market,
    owned_total: printing.owned_total,
  };
}

const same = (a: DeckRef, b: DeckRef) => a.set === b.set && a.id === b.id;
const copy = (content: DeckContentV2): DeckContentV2 => ({
  ...content,
  main: content.main.map((line) => ({ ...line })),
  runes: content.runes.map((line) => ({ ...line })),
  battlefields: content.battlefields.map((ref) => ({ ...ref })),
  sideboard: content.sideboard.map((line) => ({ ...line })),
  workbench: content.workbench.map((line) => ({ ...line })),
});

export function addCopy(content: DeckContentV2, zone: EditZone, ref: DeckRef): DeckContentV2 {
  const next = copy(content);
  if (zone === 'battlefields') {
    next.battlefields.push({ set: ref.set, id: ref.id });
    return next;
  }
  const line = next[zone].find((item) => same(item, ref));
  if (line) line.qty += 1;
  else next[zone].push({ set: ref.set, id: ref.id, qty: 1 });
  return next;
}

export function removeCopy(content: DeckContentV2, zone: EditZone, ref: DeckRef): DeckContentV2 {
  const next = copy(content);
  if (zone === 'battlefields') {
    const index = next.battlefields.findIndex((item) => same(item, ref));
    if (index >= 0) next.battlefields.splice(index, 1);
    return next;
  }
  const lines: DeckRefLine[] = next[zone];
  const index = lines.findIndex((item) => same(item, ref));
  if (index < 0) return next;
  lines[index].qty -= 1;
  if (lines[index].qty <= 0) lines.splice(index, 1);
  return next;
}

/** One copy from a zone to another (`canMove` said yes). */
export const moveCopy = (
  content: DeckContentV2,
  from: LineZone,
  to: LineZone,
  ref: DeckRef,
): DeckContentV2 => addCopy(removeCopy(content, from, ref), to, ref);

/**
 * `n` copies of printing `from` in `zone` become printing `to`, another printing of the same card
 * (the art switch). The copies of the name never change, so no rule is asked: in a zone of lines
 * the copies leave the `from` line (dropped at 0) for the `to` line, merged when the zone has one,
 * else a new line right after `from`; a battlefield, the legend or the champion is replaced in
 * place. The same printing, no copies or a `from` the zone lacks leave the content as it is.
 */
export function setPrinting(
  content: DeckContentV2,
  zone: EditZone | 'legend' | 'champion',
  from: DeckRef,
  to: DeckRef,
  n = 1,
): DeckContentV2 {
  if (same(from, to) || n < 1) return content;
  const target = { set: to.set, id: to.id };
  if (zone === 'legend' || zone === 'champion') {
    const slot = content[zone];
    return slot && same(slot, from) ? { ...copy(content), [zone]: target } : content;
  }
  const next = copy(content);
  if (zone === 'battlefields') {
    const index = next.battlefields.findIndex((ref) => same(ref, from));
    if (index < 0) return content;
    next.battlefields[index] = target;
    return next;
  }
  const lines: DeckRefLine[] = next[zone];
  const index = lines.findIndex((line) => same(line, from));
  if (index < 0) return content;
  const moved = Math.min(n, lines[index].qty);
  const existing = lines.find((line) => same(line, to));
  if (existing) existing.qty += moved;
  else lines.splice(index + 1, 0, { ...target, qty: moved });
  lines[index].qty -= moved;
  if (lines[index].qty <= 0) lines.splice(index, 1);
  return next;
}

const ZONES = [
  'legend',
  'champion',
  'main',
  'runes',
  'battlefields',
  'sideboard',
  'workbench',
] as const;

/** Copies of one printing in the deck (every zone but the workbench), for the browser tiles. */
export function copiesInDeck(content: DeckContentV2, ref: DeckRef): number {
  const slots = [content.legend, content.champion, ...content.battlefields];
  const lines = [...content.main, ...content.runes, ...content.sideboard];
  return (
    slots.filter((slot) => slot !== null && same(slot, ref)).length +
    lines.filter((line) => same(line, ref)).reduce((total, line) => total + line.qty, 0)
  );
}

/** Printings of the content the catalog does not have (`unknown_cards` shape, zone order). */
export function unknownRefs(content: DeckContentV2, book: CardBook): DeckUnknownCard[] {
  const out: DeckUnknownCard[] = [];
  for (const zone of ZONES) {
    const value = content[zone];
    const refs: DeckRef[] = value === null ? [] : Array.isArray(value) ? value : [value];
    for (const ref of refs) {
      if (!book[refKey(ref)]) out.push({ zone, set: ref.set, id: ref.id });
    }
  }
  return out;
}

/** The content without the printings the catalog lacks: what the rules can read. */
export function knownContent(content: DeckContentV2, book: CardBook): DeckContentV2 {
  const known = (ref: DeckRef) => Boolean(book[refKey(ref)]);
  return {
    ...content,
    legend: content.legend && known(content.legend) ? content.legend : null,
    champion: content.champion && known(content.champion) ? content.champion : null,
    main: content.main.filter(known),
    runes: content.runes.filter(known),
    battlefields: content.battlefields.filter(known),
    sideboard: content.sideboard.filter(known),
    workbench: content.workbench.filter(known),
  };
}

/** Takes the unknown printings out (the user asked for it: never silently). */
export const removeUnknown = knownContent;

/** Value rule of the server (EUR, cents): every zone but the workbench. */
export function contentValue(
  content: DeckContentV2,
  book: CardBook,
): { value: number; unpriced: number } {
  const lines: DeckRefLine[] = [
    ...(content.legend ? [{ ...content.legend, qty: 1 }] : []),
    ...(content.champion ? [{ ...content.champion, qty: 1 }] : []),
    ...content.main,
    ...content.runes,
    ...content.battlefields.map((ref) => ({ ...ref, qty: 1 })),
    ...content.sideboard,
  ];
  let value = 0;
  let unpriced = 0;
  for (const line of lines) {
    const market = book[refKey(line)]?.market ?? null;
    if (market === null) unpriced += line.qty;
    else value += market * line.qty;
  }
  return { value: Math.round(value * 100) / 100, unpriced };
}
