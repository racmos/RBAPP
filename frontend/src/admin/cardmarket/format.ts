/** Pure helpers of the Cardmarket load log screen (CM-a). */

/** The API sends naive UTC timestamps: mark them as UTC so the browser converts them. */
export function asUtc(value: string): string {
  return /(Z|[+-]\d\d:?\d\d)$/i.test(value) ? value : `${value}Z`;
}

export type DurationLabel =
  | { key: 'cardmarket.duration.seconds'; values: { s: number } }
  | { key: 'cardmarket.duration.minutes'; values: { m: number; s: number } }
  | { key: 'cardmarket.duration.hours'; values: { h: number; m: number } };

/** "10 s", "2 min 5 s", "1 h 2 min": the catalog key and its values; null without a duration. */
export function durationLabel(seconds: number | null | undefined): DurationLabel | null {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds) || seconds < 0) {
    return null;
  }
  const total = Math.round(seconds);
  if (total < 60) return { key: 'cardmarket.duration.seconds', values: { s: total } };
  if (total < 3600) {
    return {
      key: 'cardmarket.duration.minutes',
      values: { m: Math.floor(total / 60), s: total % 60 },
    };
  }
  return {
    key: 'cardmarket.duration.hours',
    values: { h: Math.floor(total / 3600), m: Math.floor((total % 3600) / 60) },
  };
}

/** Whole seconds from `start` to `end` (naive UTC), or null when one is missing or unreadable. */
export function secondsBetween(start: string | null, end: string | null): number | null {
  if (!start || !end) return null;
  const diff = Date.parse(asUtc(end)) - Date.parse(asUtc(start));
  return Number.isFinite(diff) ? Math.round(diff / 1000) : null;
}

export const isActiveJob = (status: string | null | undefined): boolean =>
  status === 'queued' || status === 'running';

export type ResultKey =
  | 'cardmarket.result.priceRows'
  | 'cardmarket.result.productsToday'
  | 'cardmarket.result.newProducts'
  | 'cardmarket.result.linked'
  | 'cardmarket.result.proposed'
  | 'cardmarket.result.review'
  | 'cardmarket.result.queued';
export type ResultRow = { key: ResultKey; value: number | string };

const record = (value: unknown): Record<string, unknown> | null =>
  typeof value === 'object' && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
const count = (value: unknown): number | null =>
  typeof value === 'number' && Number.isFinite(value) ? value : null;

/**
 * The known numbers of a `daily_prices` job result (validation, auto-match, follow-ups) as
 * label/value rows. Nothing about the shape is assumed: a missing or odd value is left out.
 */
export function resultRows(result: unknown): ResultRow[] {
  const root = record(result);
  if (!root) return [];
  const validation = record(root.validation);
  const autoMatch = record(root.auto_match);
  const candidates: [ResultKey, number | string | null][] = [
    ['cardmarket.result.priceRows', count(validation?.price_rows)],
    ['cardmarket.result.productsToday', count(validation?.products_today)],
    ['cardmarket.result.newProducts', count(validation?.new_products)],
    ['cardmarket.result.linked', count(autoMatch?.linked)],
    ['cardmarket.result.proposed', count(autoMatch?.proposed)],
    ['cardmarket.result.review', count(root.review_total) ?? count(autoMatch?.review)],
    [
      'cardmarket.result.queued',
      Array.isArray(root.queued) && root.queued.every((kind) => typeof kind === 'string')
        ? root.queued.join(', ') || null
        : null,
    ],
  ];
  return candidates.flatMap(([key, value]) => (value === null ? [] : [{ key, value }]));
}
