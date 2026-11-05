import type {
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

const ZONES = [
  'legend',
  'champion',
  'main',
  'runes',
  'battlefields',
  'sideboard',
  'workbench',
] as const;

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
