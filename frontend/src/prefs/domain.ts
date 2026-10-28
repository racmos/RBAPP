import type { PrefKey, Prefs } from './types';

/** The stored fields, in the order of the API (PREF-2). */
export const PREF_KEYS = [
  'lang',
  'density',
  'accent',
  'bg_intensity',
  'collection_view',
  'playset_size',
] as const satisfies readonly PrefKey[];

/** Allowed values of the enumerated fields; `bg_intensity` is an integer 0..100 and
    `playset_size` an integer 1..9. */
export const DOMAINS = {
  lang: ['es', 'en'],
  density: ['compact', 'regular', 'comfy'],
  accent: ['cyan', 'orange'],
  collection_view: ['table', 'grid'],
} as const;

export const BG_MIN = 0;
export const BG_MAX = 100;
export const PLAYSET_MIN = 1;
export const PLAYSET_MAX = 9;

export const EMPTY_PREFS: Prefs = {
  lang: null,
  density: null,
  accent: null,
  bg_intensity: null,
  collection_view: null,
  playset_size: null,
};

/** Whether `value` is a stored (non-Auto) value of `key`. `null` is Auto, not a value. */
export function isPrefValue<K extends PrefKey>(
  key: K,
  value: unknown,
): value is NonNullable<Prefs[K]> {
  if (key === 'bg_intensity') {
    return (
      typeof value === 'number' && Number.isInteger(value) && value >= BG_MIN && value <= BG_MAX
    );
  }
  if (key === 'playset_size') {
    return (
      typeof value === 'number' &&
      Number.isInteger(value) &&
      value >= PLAYSET_MIN &&
      value <= PLAYSET_MAX
    );
  }
  return (DOMAINS[key as keyof typeof DOMAINS] as readonly unknown[]).includes(value);
}

/**
 * Anything (a parsed mirror, a server payload) to the stored fields: valid values stay, everything
 * else, including unknown keys and out-of-domain values, becomes Auto. Never throws.
 */
export function sanitizePrefs(raw: unknown): Prefs {
  const source = typeof raw === 'object' && raw !== null ? (raw as Record<string, unknown>) : {};
  const clean: Record<string, unknown> = {};
  for (const key of PREF_KEYS) clean[key] = isPrefValue(key, source[key]) ? source[key] : null;
  return clean as Prefs;
}
