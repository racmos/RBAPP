/** Pure helpers of the Cardmarket matching workbench (CM-b). */
import type { CardmarketFoil, CardmarketLink } from '@/api/endpoints';

/** The four tabs in the order of the work after a reset or a new set (CM-l S1). */
export const TABS = ['prepare', 'auto', 'link', 'linked'] as const;
export type MatchingTab = (typeof TABS)[number];

/**
 * The views of the merged tabs (CM-l S2-S4), the default first: Prepare holds Expansions and
 * Missing cards, To link the Ignored list, Linked the Conflicts.
 */
export const VIEWS = {
  prepare: ['expansions', 'missing'],
  link: ['link', 'ignored'],
  linked: ['all', 'conflicts'],
} as const;
export type ViewTab = keyof typeof VIEWS;
export type MatchingView<T extends ViewTab = ViewTab> = (typeof VIEWS)[T][number];

export const hasViews = (tab: MatchingTab): tab is ViewTab => tab in VIEWS;

/** The page size of every list; all the matching endpoints accept 25, 50, 100 and 200. */
export const PER_PAGE = 50;

const BASE_URL = '/admin/cardmarket/matching';

/** The filters a view change keeps (CM-l S6); the page and every other filter go. */
const VIEW_KEPT = ['q', 'set', 'category'];

/**
 * The old tabs of CM-b..CM-h and where they live now (CM-l S5): their URLs are rewritten with
 * a replace, keeping the filters.
 */
const OLD_TABS: Record<string, { tab: MatchingTab; view: MatchingView }> = {
  conflicts: { tab: 'linked', view: 'conflicts' },
  ignored: { tab: 'link', view: 'ignored' },
  expansions: { tab: 'prepare', view: 'expansions' },
  missing: { tab: 'prepare', view: 'missing' },
};

/**
 * `view` as the URL holds it: the default views of To link and Linked are never written; both
 * views of Prepare are (`?tab=prepare&view=expansions|missing`).
 */
function viewParam(tab: MatchingTab, view: string | undefined): string | null {
  if (!view || !hasViews(tab)) return null;
  if (tab !== 'prepare' && view === VIEWS[tab][0]) return null;
  return view;
}

/** The search of one tab: `tab` (none for To link, the default), then `view`, then the rest. */
export function matchingSearch(
  tab: MatchingTab,
  params: Iterable<[string, string]>,
): URLSearchParams {
  const rest = [...params];
  const view = viewParam(tab, rest.find(([key]) => key === 'view')?.[1]);
  const search = new URLSearchParams(tab === 'link' ? {} : { tab });
  if (view) search.set('view', view);
  for (const [key, value] of rest) if (key !== 'tab' && key !== 'view') search.append(key, value);
  return search;
}

/**
 * The URL of one workbench tab with its view and filters, for links from other screens and
 * panels (CM-m, CM-l). The one place that knows how a tab and its view are in the URL; `link`
 * is the default tab. `params.view` picks a view of a merged tab.
 */
export function matchingTabUrl(tab: MatchingTab, params: Record<string, string> = {}): string {
  const query = matchingSearch(tab, Object.entries(params)).toString();
  return query ? `${BASE_URL}?${query}` : BASE_URL;
}

export const parseTab = (value: string | null): MatchingTab =>
  (TABS as readonly string[]).includes(value ?? '') ? (value as MatchingTab) : 'link';

/** The view of a merged tab from the URL; its first view when absent or unknown. */
export const parseView = <T extends ViewTab>(tab: T, value: string | null): MatchingView<T> => {
  const views: readonly string[] = VIEWS[tab];
  return (views.includes(value ?? '') ? value : views[0]) as MatchingView<T>;
};

/**
 * The search an old or unknown `?tab=` stands for (CM-l S5), with every other parameter kept;
 * null when the search is already in the current form.
 */
export function canonicalSearch(params: URLSearchParams): URLSearchParams | null {
  const value = params.get('tab');
  if (value === null || (TABS as readonly string[]).includes(value)) return null;
  const old = OLD_TABS[value];
  const rest = [...params].filter(([key]) => key !== 'tab' && (!old || key !== 'view'));
  return old
    ? matchingSearch(old.tab, [['view', old.view], ...rest])
    : matchingSearch('link', rest);
}

/** The search after choosing another view of the same tab: q, set and category stay (S6). */
export function viewSearch<T extends ViewTab>(
  tab: T,
  view: MatchingView<T>,
  params: URLSearchParams,
): URLSearchParams {
  const kept = [...params].filter(([key]) => VIEW_KEPT.includes(key));
  return matchingSearch(tab, [['view', view], ...kept]);
}

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
