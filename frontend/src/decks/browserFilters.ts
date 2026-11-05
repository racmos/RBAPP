import type { CardListParams } from '@/api/types';

/** The cost groups of the filter panel; the top value means "and more" (`7+`). */
export const RANGES = { energy: 7, power: 3, might: 7 } as const;
export type RangeKey = keyof typeof RANGES;
export const RANGE_KEYS = Object.keys(RANGES) as RangeKey[];

/** What the user chose in the browser's filter panel (F5-i step 3). */
export type BrowserFilters = {
  domain: string[];
  type: string[];
  rarity: string[];
  set: string[];
  tag: string[];
  /** One value per cost group, or null. */
  energy: number | null;
  power: number | null;
  might: number | null;
  owned: boolean;
};

export const NO_FILTERS: BrowserFilters = {
  domain: [],
  type: [],
  rarity: [],
  set: [],
  tag: [],
  energy: null,
  power: null,
  might: null,
  owned: false,
};

/**
 * What a zone lets the user choose: `null` = any value, a list = only those values (an empty
 * list hides the group). `costs` is false for the zones whose cards have no costs (legend,
 * battlefields, runes); tags apply only where costs do.
 */
export type FilterScope = {
  types: string[] | null;
  domains: string[] | null;
  tags: string[] | null;
  costs: boolean;
};

const listed = (values: string[] | undefined) => (values && values.length > 0 ? values : null);

/** The scope of a zone from its own filters (`pickFilters`): a zone of one type offers none. */
export function scopeOf(base: Partial<CardListParams>, costs: boolean): FilterScope {
  const types = listed(base.type);
  return {
    types: types === null ? null : types.length > 1 ? types : [],
    domains: listed(base.domain),
    tags: costs ? listed(base.tag) : [],
    costs,
  };
}

const within = (values: string[], allowed: string[] | null) =>
  allowed === null ? values : values.filter((value) => allowed.includes(value));

/** The filters that apply to a zone: values it does not allow and costs it lacks are dropped. */
export function pruneFilters(filters: BrowserFilters, scope: FilterScope): BrowserFilters {
  return {
    ...filters,
    domain: within(filters.domain, scope.domains),
    type: within(filters.type, scope.types),
    tag: within(filters.tag, scope.tags),
    energy: scope.costs ? filters.energy : null,
    power: scope.costs ? filters.power : null,
    might: scope.costs ? filters.might : null,
  };
}

/** The user's values inside the zone's list; the zone's list when none of them fits. */
const narrow = (base: string[] | undefined, chosen: string[]) => {
  if (chosen.length === 0) return base;
  if (!base || base.length === 0) return chosen;
  const kept = chosen.filter((value) => base.includes(value));
  return kept.length > 0 ? kept : base;
};

/**
 * The `GET /cards` filters of a zone with the user's filters on top. The zone and legend
 * filters always apply: a user list only narrows the zone's list (never widens it) and the
 * zone's `domain_match` stays.
 */
export function mergeFilters(
  base: Partial<CardListParams>,
  filters: BrowserFilters,
): Partial<CardListParams> {
  const params: Partial<CardListParams> = { ...base };
  for (const key of ['domain', 'type', 'tag', 'rarity', 'set'] as const) {
    const value = narrow(base[key], filters[key]);
    if (value) params[key] = value;
  }
  for (const key of RANGE_KEYS) {
    const value = filters[key];
    if (value === null) continue;
    params[`${key}_min`] = value;
    if (value < RANGES[key]) params[`${key}_max`] = value;
  }
  if (filters.owned) params.owned = 'owned';
  return params;
}

/** The number of active filters: each value, each cost and owned only. */
export function countFilters(filters: BrowserFilters): number {
  return (
    filters.domain.length +
    filters.type.length +
    filters.rarity.length +
    filters.set.length +
    filters.tag.length +
    RANGE_KEYS.filter((key) => filters[key] !== null).length +
    (filters.owned ? 1 : 0)
  );
}
