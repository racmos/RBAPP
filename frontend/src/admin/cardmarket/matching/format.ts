/** Pure helpers of the Cardmarket matching workbench (CM-b). */
import type { CardmarketFoil, CardmarketLink } from '@/api/endpoints';

export const TABS = ['link', 'linked', 'conflicts', 'ignored', 'auto'] as const;
export type MatchingTab = (typeof TABS)[number];

/** The page size of every list; all the matching endpoints accept 25, 50, 100 and 200. */
export const PER_PAGE = 50;

export const parseTab = (value: string | null): MatchingTab =>
  (TABS as readonly string[]).includes(value ?? '') ? (value as MatchingTab) : 'link';

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
