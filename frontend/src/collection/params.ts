import type { CollectionParams, CollectionSort, ExportFormat } from '@/api/types';

export const DEFAULT_SORT: CollectionSort = 'number';
export const DEFAULT_DIR = 'asc' as const;
export const DEFAULT_PAGE = 1;
export const DEFAULT_PER_PAGE = 50;

const SORTS = new Set<CollectionSort>([
  'number',
  'name',
  'price',
  'qty',
  'value',
  'pl',
  'trend_7d',
  'updated',
  'rarity',
]);

const KEY_ORDER = [
  'q',
  'set',
  'domain',
  'type',
  'rarity',
  'condition',
  'language',
  'foil',
  'selling',
  'has_purchase',
  'sort',
  'dir',
  'page',
  'per_page',
] as const satisfies readonly (keyof CollectionParams)[];

const LIST_KEYS = ['set', 'domain', 'type', 'rarity', 'condition', 'language'] as const;
const TRISTATE_KEYS = ['selling', 'has_purchase'] as const;

function text(value: string | null): string | undefined {
  const trimmed = value?.trim();
  return trimmed ? trimmed : undefined;
}

function whole(value: string | null, min: number, max: number): number | undefined {
  if (value === null) return undefined;
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed >= min && parsed <= max ? parsed : undefined;
}

/** The URL search string as normalised `GET /collection` params; invalid values are dropped. */
export function parseCollectionSearch(search: URLSearchParams): CollectionParams {
  const params: CollectionParams = {};
  const q = text(search.get('q'));
  if (q !== undefined) params.q = q;
  for (const key of LIST_KEYS) {
    const values = search
      .getAll(key)
      .map((value) => value.trim())
      .filter((value) => value !== '');
    if (values.length > 0) params[key] = values;
  }
  const foil = search.get('foil');
  if (foil === 'foil' || foil === 'nonfoil') params.foil = foil;
  for (const key of TRISTATE_KEYS) {
    const value = search.get(key);
    if (value === 'yes' || value === 'no') params[key] = value;
  }
  const sort = search.get('sort');
  params.sort =
    sort !== null && SORTS.has(sort as CollectionSort) ? (sort as CollectionSort) : DEFAULT_SORT;
  params.dir = search.get('dir') === 'desc' ? 'desc' : DEFAULT_DIR;
  params.page = whole(search.get('page'), 1, 10_000) ?? DEFAULT_PAGE;
  params.per_page = whole(search.get('per_page'), 25, 200) ?? DEFAULT_PER_PAGE;
  return params;
}

/** A deterministic query string that leaves out every default (also the cache key). */
export function serializeCollectionParams(params: CollectionParams): string {
  const query = new URLSearchParams();
  for (const key of KEY_ORDER) {
    const value = params[key];
    if (value === undefined) continue;
    if (Array.isArray(value)) {
      for (const item of value) query.append(key, item);
    } else if (key === 'foil' || key === 'selling' || key === 'has_purchase') {
      if (value !== 'any') query.append(key, String(value));
    } else if (key === 'sort') {
      if (value !== DEFAULT_SORT) query.append(key, String(value));
    } else if (key === 'dir') {
      if (value !== DEFAULT_DIR) query.append(key, String(value));
    } else if (key === 'page') {
      if (value !== DEFAULT_PAGE) query.append(key, String(value));
    } else if (key === 'per_page') {
      if (value !== DEFAULT_PER_PAGE) query.append(key, String(value));
    } else {
      query.append(key, String(value));
    }
  }
  return query.toString();
}

/** Apply a change; anything but a page change goes back to the first page. */
export function withChange(
  params: CollectionParams,
  patch: Partial<CollectionParams>,
): CollectionParams {
  const next: CollectionParams = { ...params, ...patch };
  const keys = Object.keys(patch);
  if (!(keys.length === 1 && keys[0] === 'page')) delete next.page;
  return next;
}

/** How many filters (not search, sort or paging) are active. */
export function activeFilterCount(params: CollectionParams): number {
  let count = 0;
  for (const key of LIST_KEYS) count += params[key]?.length ?? 0;
  if (params.foil && params.foil !== 'any') count++;
  for (const key of TRISTATE_KEYS) if (params[key] && params[key] !== 'any') count++;
  return count;
}

export type ExportScope = 'all' | 'filtered' | 'selling';

/**
 * The query of `GET /collection/export` (F3-i S1): the current filters for `filtered` (paging and
 * sort leave nothing out of a file), then the format; Cardmarket is always what is on sale.
 */
export function exportQuery(
  params: CollectionParams,
  format: ExportFormat,
  scope: ExportScope,
): string {
  const effective = format === 'cardmarket' ? 'selling' : scope;
  const filters =
    effective === 'filtered'
      ? serializeCollectionParams({
          ...params,
          sort: undefined,
          dir: undefined,
          page: undefined,
          per_page: undefined,
        })
      : '';
  const query = new URLSearchParams(filters);
  query.append('format', format);
  if (effective === 'selling') query.append('only_selling', 'true');
  return query.toString();
}
