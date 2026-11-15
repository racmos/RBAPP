import { describe, expect, it } from 'vitest';
import {
  formatDate,
  formatDateTime,
  formatMoney,
  formatNumber,
  formatPct,
  formatRelative,
} from './format';

/** English formats only (owner feedback S21): "1,061.52 €", "5 Oct 2026", "+10.0%". */
describe('formatMoney', () => {
  it('uses English separators with the euro after the value', () => {
    expect(formatMoney(1061.52)).toBe('1,061.52 €');
  });

  it('always shows two decimals', () => {
    expect(formatMoney(2.5)).toBe('2.50 €');
    expect(formatMoney(0)).toBe('0.00 €');
  });
});

describe('formatNumber', () => {
  it('groups thousands with a comma', () => {
    expect(formatNumber(1234567)).toBe('1,234,567');
  });
});

describe('formatDate', () => {
  it('writes a medium English date in UTC', () => {
    expect(formatDate('2026-10-05')).toBe('5 Oct 2026');
  });
});

describe('formatDateTime', () => {
  it('writes an English date and time', () => {
    expect(formatDateTime('2026-10-05T08:00:00')).toBe('5 Oct 2026, 08:00');
  });
});

describe('formatPct', () => {
  it('formats a positive percentage with one decimal and a plus sign', () => {
    expect(formatPct(10)).toBe('+10.0%');
  });

  it('formats a negative percentage with one decimal', () => {
    expect(formatPct(-3.14)).toBe('-3.1%');
  });

  it('returns the unsigned zero for 0', () => {
    expect(formatPct(0)).toBe('0.0%');
  });
});

describe('formatRelative (F9-j S9)', () => {
  const NOW = new Date('2026-11-15T12:00:00Z');

  it('is relative under 7 days', () => {
    expect(formatRelative('2026-11-15T12:00:00Z', NOW)).toBe('now');
    expect(formatRelative('2026-11-15T11:59:20Z', NOW)).toBe('40 seconds ago');
    expect(formatRelative('2026-11-15T11:55:00Z', NOW)).toBe('5 minutes ago');
    expect(formatRelative('2026-11-15T09:00:00Z', NOW)).toBe('3 hours ago');
    expect(formatRelative('2026-11-14T10:00:00Z', NOW)).toBe('yesterday');
    expect(formatRelative('2026-11-09T11:00:00Z', NOW)).toBe('6 days ago');
  });

  it('is the date from 7 days, and "now" for a time in the future', () => {
    expect(formatRelative('2026-11-08T12:00:00Z', NOW)).toBe('8 Nov 2026');
    expect(formatRelative('2026-11-15T12:05:00Z', NOW)).toBe('now');
  });
});
