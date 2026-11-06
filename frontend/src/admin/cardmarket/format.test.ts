import { describe, expect, it } from 'vitest';
import { asUtc, durationLabel, isActiveJob, resultRows, secondsBetween } from './format';

describe('asUtc', () => {
  it('marks a naive timestamp as UTC', () => {
    expect(asUtc('2026-11-06T06:30:00')).toBe('2026-11-06T06:30:00Z');
  });

  it('keeps a timestamp that already carries its offset', () => {
    expect(asUtc('2026-11-06T06:30:00Z')).toBe('2026-11-06T06:30:00Z');
    expect(asUtc('2026-11-06T06:30:00+01:00')).toBe('2026-11-06T06:30:00+01:00');
  });
});

describe('durationLabel', () => {
  it('uses seconds below a minute', () => {
    expect(durationLabel(10)).toEqual({ key: 'cardmarket.duration.seconds', values: { s: 10 } });
  });

  it('uses minutes and seconds below an hour', () => {
    expect(durationLabel(125)).toEqual({
      key: 'cardmarket.duration.minutes',
      values: { m: 2, s: 5 },
    });
  });

  it('uses hours and minutes from an hour', () => {
    expect(durationLabel(3720)).toEqual({
      key: 'cardmarket.duration.hours',
      values: { h: 1, m: 2 },
    });
  });

  it('is null when there is no duration', () => {
    expect(durationLabel(null)).toBeNull();
    expect(durationLabel(-1)).toBeNull();
  });
});

describe('secondsBetween', () => {
  it('rounds the difference of two naive UTC timestamps', () => {
    expect(secondsBetween('2026-11-06T06:30:00', '2026-11-06T06:30:42.6')).toBe(43);
  });

  it('is null when a timestamp is missing or unreadable', () => {
    expect(secondsBetween(null, '2026-11-06T06:30:00')).toBeNull();
    expect(secondsBetween('2026-11-06T06:30:00', 'soon')).toBeNull();
  });
});

describe('isActiveJob', () => {
  it('is true only for queued and running', () => {
    expect(isActiveJob('queued')).toBe(true);
    expect(isActiveJob('running')).toBe(true);
    expect(isActiveJob('success')).toBe(false);
    expect(isActiveJob(undefined)).toBe(false);
  });
});

describe('resultRows', () => {
  it('reads the known numbers of a daily_prices result', () => {
    expect(
      resultRows({
        validation: { date: '20261106', price_rows: 900, products_today: 1200, new_products: 3 },
        auto_match: { linked: 4, proposed: 6, review: 2 },
        review: [{ product_id: 1 }],
        review_total: 2,
        queued: ['value_snapshot', 'products_refresh'],
      }),
    ).toEqual([
      { key: 'cardmarket.result.priceRows', value: 900 },
      { key: 'cardmarket.result.productsToday', value: 1200 },
      { key: 'cardmarket.result.newProducts', value: 3 },
      { key: 'cardmarket.result.linked', value: 4 },
      { key: 'cardmarket.result.proposed', value: 6 },
      { key: 'cardmarket.result.review', value: 2 },
      { key: 'cardmarket.result.queued', value: 'value_snapshot, products_refresh' },
    ]);
  });

  it('skips what is missing or of another shape', () => {
    expect(resultRows(null)).toEqual([]);
    expect(resultRows('oops')).toEqual([]);
    expect(resultRows([1, 2])).toEqual([]);
    expect(
      resultRows({ validation: 'x', auto_match: { linked: '4', proposed: 1 }, queued: 'no' }),
    ).toEqual([{ key: 'cardmarket.result.proposed', value: 1 }]);
  });

  it('falls back to the review count of auto_match without review_total', () => {
    expect(resultRows({ auto_match: { review: 5 } })).toEqual([
      { key: 'cardmarket.result.review', value: 5 },
    ]);
  });
});
