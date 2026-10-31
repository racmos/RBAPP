import { describe, expect, it } from 'vitest';
import { formatDate, formatDateTime, formatMoney, formatNumber, formatPct } from './format';

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
