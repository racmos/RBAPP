import type { CardListParams, CardListSort } from '@/api/types';

export const DEFAULT_SORT: CardListSort = 'number';
export const DEFAULT_DIR: 'asc' | 'desc' = 'asc';
export const DEFAULT_PAGE = 1;
export const DEFAULT_PER_PAGE = 48 as const;

const VALID_SORTS = new Set<CardListSort>([
  'number',
  'name',
  'price',
  'trend_7d',
  'trend_30d',
  'rarity',
  'energy',
  'power',
  'might',
]);

const VALID_PER_PAGE = new Set<number>([48, 96, 192]);

const KEY_ORDER: (keyof CardListParams)[] = [
  'q',
  'text',
  'set',
  'domain',
  'type',
  'supertype',
  'exclude_supertype',
  'rarity',
  'tag',
  'domain_match',
  'energy_min',
  'energy_max',
  'power_min',
  'power_max',
  'might_min',
  'might_max',
  'price_min',
  'price_max',
  'owned',
  'banned_in',
  'base_only',
  'sort',
  'dir',
  'page',
  'per_page',
];

function readString(value: string | null): string | undefined {
  if (value === null) return undefined;
  const trimmed = value.trim();
  return trimmed === '' ? undefined : trimmed;
}

function readStrings(search: URLSearchParams, key: string): string[] | undefined {
  const values = search.getAll(key);
  const trimmed = values.map((v) => v.trim()).filter((v) => v !== '');
  return trimmed.length > 0 ? trimmed : undefined;
}

function readInt(value: string | null, min: number, max: number): number | undefined {
  if (value === null) return undefined;
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < min || parsed > max || !Number.isInteger(parsed)) {
    return undefined;
  }
  return parsed;
}

function readFloat(value: string | null, min: number, max: number): number | undefined {
  if (value === null) return undefined;
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < min || parsed > max) return undefined;
  return parsed;
}

function readSort(value: string | null): CardListSort {
  if (value !== null && VALID_SORTS.has(value as CardListSort)) return value as CardListSort;
  return DEFAULT_SORT;
}

function readPage(value: string | null): number {
  return readInt(value, 1, 10_000) ?? DEFAULT_PAGE;
}

function readPerPage(value: string | null): 48 | 96 | 192 {
  const parsed = readInt(value, 1, 192);
  if (parsed !== undefined && VALID_PER_PAGE.has(parsed)) return parsed as 48 | 96 | 192;
  return DEFAULT_PER_PAGE;
}

function readDomainMatch(value: string | null): 'any' | 'all' | 'subset' {
  if (value === 'any' || value === 'all' || value === 'subset') return value;
  return 'any';
}

function readOwned(value: string | null): 'any' | 'owned' | 'missing' {
  if (value === 'owned' || value === 'missing') return value;
  return 'any';
}

function readBannedIn(value: string | null): '1v1' | '2v2' | 'any' | undefined {
  if (value === '1v1' || value === '2v2' || value === 'any') return value;
  return undefined;
}

/** Read the current search string into a normalised `CardListParams` (F2-h S3). */
export function parseCatalogSearch(search: URLSearchParams): CardListParams {
  const params: CardListParams = {};

  const q = readString(search.get('q'));
  if (q !== undefined) params.q = q;

  const text = readString(search.get('text'));
  if (text !== undefined) params.text = text;

  const set = readStrings(search, 'set');
  if (set !== undefined) params.set = set;

  const domain = readStrings(search, 'domain');
  if (domain !== undefined) params.domain = domain;

  const type = readStrings(search, 'type');
  if (type !== undefined) params.type = type;

  const supertype = readStrings(search, 'supertype');
  if (supertype !== undefined) params.supertype = supertype;

  const excludeSupertype = readStrings(search, 'exclude_supertype');
  if (excludeSupertype !== undefined) params.exclude_supertype = excludeSupertype;

  const rarity = readStrings(search, 'rarity');
  if (rarity !== undefined) params.rarity = rarity;

  const tag = readStrings(search, 'tag');
  if (tag !== undefined) params.tag = tag;

  params.domain_match = readDomainMatch(search.get('domain_match'));
  if (params.domain_match === 'any') delete params.domain_match;

  const energyMin = readInt(search.get('energy_min'), 0, 99);
  if (energyMin !== undefined) params.energy_min = energyMin;

  const energyMax = readInt(search.get('energy_max'), 0, 99);
  if (energyMax !== undefined) params.energy_max = energyMax;

  const powerMin = readInt(search.get('power_min'), 0, 99);
  if (powerMin !== undefined) params.power_min = powerMin;

  const powerMax = readInt(search.get('power_max'), 0, 99);
  if (powerMax !== undefined) params.power_max = powerMax;

  const mightMin = readInt(search.get('might_min'), 0, 99);
  if (mightMin !== undefined) params.might_min = mightMin;

  const mightMax = readInt(search.get('might_max'), 0, 99);
  if (mightMax !== undefined) params.might_max = mightMax;

  const priceMin = readFloat(search.get('price_min'), 0, 100_000);
  if (priceMin !== undefined) params.price_min = priceMin;

  const priceMax = readFloat(search.get('price_max'), 0, 100_000);
  if (priceMax !== undefined) params.price_max = priceMax;

  params.owned = readOwned(search.get('owned'));
  if (params.owned === 'any') delete params.owned;

  const bannedIn = readBannedIn(search.get('banned_in'));
  if (bannedIn !== undefined) params.banned_in = bannedIn;

  if (search.get('base_only') === 'true') params.base_only = true;

  params.sort = readSort(search.get('sort'));
  params.dir = search.get('dir') === 'desc' ? 'desc' : DEFAULT_DIR;
  params.page = readPage(search.get('page'));
  params.per_page = readPerPage(search.get('per_page'));

  return params;
}

function appendParam(query: URLSearchParams, key: string, value: string | number): void {
  query.append(key, String(value));
}

function appendArray(query: URLSearchParams, key: string, values: string[] | undefined): void {
  if (!values || values.length === 0) return;
  for (const value of values) appendParam(query, key, value);
}

/** Serialise params into a deterministic query string that omits defaults (F2-h S3). */
export function serializeCatalogParams(params: CardListParams): string {
  const query = new URLSearchParams();

  for (const key of KEY_ORDER) {
    const value = params[key];
    if (value === undefined || value === null) continue;

    switch (key) {
      case 'q':
      case 'text':
        appendParam(query, key, value as string);
        break;
      case 'set':
      case 'domain':
      case 'type':
      case 'supertype':
      case 'exclude_supertype':
      case 'rarity':
      case 'tag':
        appendArray(query, key, value as string[]);
        break;
      case 'domain_match':
        if (value !== 'any') appendParam(query, key, value as string);
        break;
      case 'energy_min':
      case 'energy_max':
      case 'power_min':
      case 'power_max':
      case 'might_min':
      case 'might_max':
        appendParam(query, key, value as number);
        break;
      case 'price_min':
      case 'price_max':
        appendParam(query, key, value as number);
        break;
      case 'owned':
        if (value !== 'any') appendParam(query, key, value as string);
        break;
      case 'banned_in':
        appendParam(query, key, value as string);
        break;
      case 'base_only':
        if (value === true) appendParam(query, key, 'true');
        break;
      case 'sort':
        if (value !== DEFAULT_SORT) appendParam(query, key, value as string);
        break;
      case 'dir':
        if (value !== DEFAULT_DIR) appendParam(query, key, value as string);
        break;
      case 'page':
        if (value !== DEFAULT_PAGE) appendParam(query, key, value as number);
        break;
      case 'per_page':
        if (value !== DEFAULT_PER_PAGE) appendParam(query, key, value as number);
        break;
      default:
        break;
    }
  }

  return query.toString();
}

/** Apply a patch; any change other than `page` resets `page` to 1 (F2-h S3). */
export function withChange(params: CardListParams, patch: Partial<CardListParams>): CardListParams {
  const next = { ...params, ...patch };
  const keys = Object.keys(patch);
  if (keys.length === 0) return next;
  if (keys.length === 1 && keys[0] === 'page') return next;
  next.page = DEFAULT_PAGE;
  if (next.page === DEFAULT_PAGE) delete next.page;
  return next;
}
