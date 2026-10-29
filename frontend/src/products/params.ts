import {
  PRODUCT_KINDS,
  type ProductKind,
  type ProductListParams,
  type ProductListSort,
} from '@/api/types';

export type ProductsTab = 'mine' | 'catalog';

export const DEFAULT_SORT: ProductListSort = 'name';
export const DEFAULT_DIR = 'asc' as const;
export const DEFAULT_PAGE = 1;
export const DEFAULT_PER_PAGE = 48;

const SORTS = new Set<ProductListSort>(['name', 'price', 'change_7d', 'change_30d']);
const KINDS = new Set<string>(PRODUCT_KINDS);

function whole(value: string | null, min: number, max: number): number | undefined {
  if (value === null) return undefined;
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed >= min && parsed <= max ? parsed : undefined;
}

/** The URL search string as normalised `GET /products` params; invalid values are dropped. */
export function parseProductSearch(search: URLSearchParams): ProductListParams {
  const params: ProductListParams = {};
  const q = search.get('q')?.trim();
  if (q) params.q = q;
  const kind = search.getAll('kind').filter((value): value is ProductKind => KINDS.has(value));
  if (kind.length > 0) params.kind = kind;
  const set = search
    .getAll('set')
    .map((value) => value.trim())
    .filter((value) => value !== '');
  if (set.length > 0) params.set = set;
  const sort = search.get('sort');
  params.sort =
    sort !== null && SORTS.has(sort as ProductListSort) ? (sort as ProductListSort) : DEFAULT_SORT;
  params.dir = search.get('dir') === 'desc' ? 'desc' : DEFAULT_DIR;
  params.page = whole(search.get('page'), 1, 10_000) ?? DEFAULT_PAGE;
  params.per_page = whole(search.get('per_page'), 24, 96) ?? DEFAULT_PER_PAGE;
  return params;
}

/** A deterministic query string that leaves out every default (also the cache key). */
export function serializeProductParams(params: ProductListParams): string {
  const query = new URLSearchParams();
  if (params.q) query.append('q', params.q);
  for (const kind of params.kind ?? []) query.append('kind', kind);
  for (const set of params.set ?? []) query.append('set', set);
  if (params.sort && params.sort !== DEFAULT_SORT) query.append('sort', params.sort);
  if (params.dir && params.dir !== DEFAULT_DIR) query.append('dir', params.dir);
  if (params.page && params.page !== DEFAULT_PAGE) query.append('page', String(params.page));
  if (params.per_page && params.per_page !== DEFAULT_PER_PAGE) {
    query.append('per_page', String(params.per_page));
  }
  return query.toString();
}

/** Apply a change; anything but a page change goes back to the first page. */
export function withChange(
  params: ProductListParams,
  patch: Partial<ProductListParams>,
): ProductListParams {
  const next: ProductListParams = { ...params, ...patch };
  const keys = Object.keys(patch);
  if (!(keys.length === 1 && keys[0] === 'page')) delete next.page;
  return next;
}

/** How many filters (kinds and sets, not the search) are active. */
export const activeFilterCount = (params: ProductListParams): number =>
  (params.kind?.length ?? 0) + (params.set?.length ?? 0);

/** The tab the URL asks for, or `null` (then the default rule decides). */
export function parseTab(search: URLSearchParams): ProductsTab | null {
  const tab = search.get('tab');
  return tab === 'mine' || tab === 'catalog' ? tab : null;
}

/** The page's search string: the tab first, then the catalog params. */
export function productsSearch(tab: ProductsTab, params: ProductListParams): string {
  const rest = serializeProductParams(params);
  return rest ? `tab=${tab}&${rest}` : `tab=${tab}`;
}
