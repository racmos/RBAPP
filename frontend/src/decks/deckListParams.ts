import type { DeckListItem, GameMode } from '@/api/types';

/** The `/decks` toolbar in the URL (`q`, `mode`, `legal`, `sort`); defaults are left out. */
export type DeckListSort = 'updated' | 'updated_asc' | 'name' | 'value';
export type DeckListParams = {
  /** As typed (the search input owns it); filtering trims it. */
  q: string;
  mode: GameMode | 'all';
  /** `yes`: legal in the deck's own mode; `no`: not legal in it. */
  legal: 'all' | 'yes' | 'no';
  sort: DeckListSort;
};

export const DECK_LIST_SORTS: readonly DeckListSort[] = ['updated', 'updated_asc', 'name', 'value'];
const MODES: readonly GameMode[] = ['1v1', '2v2'];
const LEGAL = ['yes', 'no'] as const;

export const DEFAULT_DECK_LIST_PARAMS: DeckListParams = {
  q: '',
  mode: 'all',
  legal: 'all',
  sort: 'updated',
};

const pick = <T extends string>(value: string | null, allowed: readonly T[], fallback: T): T =>
  allowed.includes(value as T) ? (value as T) : fallback;

export function parseDeckListParams(search: URLSearchParams): DeckListParams {
  return {
    q: search.get('q') ?? '',
    mode: pick<DeckListParams['mode']>(search.get('mode'), MODES, 'all'),
    legal: pick<DeckListParams['legal']>(search.get('legal'), LEGAL, 'all'),
    sort: pick(search.get('sort'), DECK_LIST_SORTS, 'updated'),
  };
}

/** `params` over `base` (other params stay), without the leading `?`. */
export function serializeDeckListParams(
  params: DeckListParams,
  base: URLSearchParams = new URLSearchParams(),
): string {
  const next = new URLSearchParams(base);
  if (params.q.trim() === '') next.delete('q');
  else next.set('q', params.q);
  for (const key of ['mode', 'legal', 'sort'] as const) {
    if (params[key] === DEFAULT_DECK_LIST_PARAMS[key]) next.delete(key);
    else next.set(key, params[key]);
  }
  return next.toString();
}

/** A search or a filter is on (the sort only orders). */
export const hasDeckFilters = (params: DeckListParams) =>
  params.q.trim() !== '' || params.mode !== 'all' || params.legal !== 'all';

const fold = (text: string) => text.normalize('NFD').replace(/\p{M}/gu, '').toLocaleLowerCase('en');

const byName = (a: DeckListItem, b: DeckListItem) =>
  a.name.localeCompare(b.name, 'en', { sensitivity: 'base', numeric: true });

const COMPARE: Record<DeckListSort, (a: DeckListItem, b: DeckListItem) => number> = {
  updated: (a, b) => b.updated_at.localeCompare(a.updated_at) || byName(a, b),
  updated_asc: (a, b) => a.updated_at.localeCompare(b.updated_at) || byName(a, b),
  name: byName,
  value: (a, b) => b.value - a.value || byName(a, b),
};

/** The decks the toolbar shows, in its order; a new array, `items` is left as it is. */
export function selectDecks(items: readonly DeckListItem[], params: DeckListParams) {
  const q = fold(params.q.trim());
  return items
    .filter(
      (deck) =>
        (q === '' || fold(deck.name).includes(q)) &&
        (params.mode === 'all' || deck.mode === params.mode) &&
        (params.legal === 'all' || deck.legal[deck.mode] === (params.legal === 'yes')),
    )
    .sort(COMPARE[params.sort]);
}
