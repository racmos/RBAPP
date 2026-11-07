/** Pure helpers of the Cardmarket matching workbench (CM-b). */
import type { CardmarketFoil, CardmarketLink } from '@/api/endpoints';

export const TABS = ['link', 'linked', 'conflicts', 'ignored', 'auto'] as const;
export type MatchingTab = (typeof TABS)[number];

/** The page size of every list; all the matching endpoints accept 25, 50, 100 and 200. */
export const PER_PAGE = 50;

export const parseTab = (value: string | null): MatchingTab =>
  (TABS as readonly string[]).includes(value ?? '') ? (value as MatchingTab) : 'link';

/** The longest search the candidates endpoint takes. */
export const MAX_QUERY = 100;

/** The first search of a product: its name, as long as the candidates endpoint takes. */
export const firstQuery = (name: string): string => name.slice(0, MAX_QUERY);

/** "OGN-001": how cards are named in the workbench (the API `SET-ID`). */
export const cardRef = (setId: string, cardId: string): string => `${setId}-${cardId}`;

/** A similarity score of the suggestions, 0 to 1. */
export const scoreText = (score: number): string => score.toFixed(2);

/**
 * The foil slot a card is linked with by default, as the matcher builds its slots: runes and
 * every rarity above uncommon have one Cardmarket product (`null`); commons and uncommons have
 * a normal (`N`) and a foil (`S`) product, the first one still free.
 */
export function defaultFoil(
  card: { rarity: string | null; type: string | null },
  taken: CardmarketFoil[],
): CardmarketFoil {
  const rarity = (card.rarity ?? '').toLowerCase();
  const type = (card.type ?? '').toLowerCase();
  if (type.includes('rune') || (rarity !== 'common' && rarity !== 'uncommon')) return null;
  return taken.includes('N') && !taken.includes('S') ? 'S' : 'N';
}

/** "Ahri, Alluring (OGN-066)", "... [OGN 066a]" or "... #066": a trailing set and number. */
const NUMBER_NOISE = /\s*(?:[([]\s*[A-Z]{2,5}[-\s]?\d{1,4}[a-z]?\s*[)\]]|#\d{1,4}[a-z]?)$/;

/**
 * The card name a Cardmarket product suggests (CM-c): the name trimmed, without a trailing
 * set and number; anything less obvious (a variant such as "(V.2)") stays.
 */
export function cardNameFrom(name: string): string {
  const trimmed = name.trim();
  return trimmed.replace(NUMBER_NOISE, '').trim() || trimmed;
}

const CATEGORY_TYPES = [
  ['Rune', /\brunes?\b/i],
  ['Battlefield', /\bbattlefields?\b/i],
  ['Legend', /\blegends?\b/i],
] as const;

/**
 * The card type a Cardmarket category names, only when it names exactly one
 * ("Riftbound Single" names none).
 */
export function typeFromCategory(category: string | null): string {
  const found = CATEGORY_TYPES.filter(([, pattern]) => pattern.test(category ?? ''));
  return found.length === 1 ? found[0]![0] : '';
}

/** The slot a suggestion links to: its first free one; `undefined` when every slot is taken. */
export const suggestionFoil = (free: CardmarketFoil[]): CardmarketFoil | undefined =>
  free.length > 0 ? free[0] : undefined;

const ALLOWED: Record<'link' | 'linked' | 'conflicts' | 'review', Record<string, RegExp>> = {
  link: { q: /./, type: /^(single|nonsingle)$/, category: /./ },
  linked: { q: /./, set: /./, foil: /^(N|S|none)$/, match_type: /^(auto|manual)$/ },
  conflicts: {},
  review: { reason: /^(ignored_pair|no_candidates|conflict|ambiguous)$/ },
};

/** The query string of one list endpoint from the page URL: only the keys it takes. */
export function apiQuery(
  list: 'link' | 'linked' | 'conflicts' | 'review',
  params: URLSearchParams,
): string {
  const query = new URLSearchParams();
  if (list === 'conflicts') query.set('conflicts', 'true');
  for (const [key, pattern] of Object.entries(ALLOWED[list])) {
    const value = params.get(key)?.trim();
    if (value && pattern.test(value)) query.set(key, value);
  }
  const page = params.get('page');
  if (page && /^[1-9]\d*$/.test(page)) query.set('page', page);
  query.set('per_page', String(PER_PAGE));
  return query.toString();
}

export type ConflictGroup = {
  key: string;
  set_id: string;
  card_id: string;
  card_name: string | null;
  foil: CardmarketFoil;
  links: CardmarketLink[];
};

/** The conflict links grouped by card slot, groups in order of first appearance. */
export function groupConflicts(links: CardmarketLink[]): ConflictGroup[] {
  const groups = new Map<string, ConflictGroup>();
  for (const link of links) {
    const key = `${link.set_id}|${link.card_id}|${link.foil ?? ''}`;
    let group = groups.get(key);
    if (!group) {
      group = {
        key,
        set_id: link.set_id,
        card_id: link.card_id,
        card_name: link.card_name,
        foil: link.foil,
        links: [],
      };
      groups.set(key, group);
    }
    group.links.push(link);
  }
  return [...groups.values()];
}
