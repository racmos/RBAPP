import { afterEach, describe, expect, it, vi } from 'vitest';
import { formatDate, formatMoney, formatNumber, localeFor } from './format';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('localeFor', () => {
  it('maps the two app languages to es-ES and en-GB', () => {
    expect(localeFor('es')).toBe('es-ES');
    expect(localeFor('en')).toBe('en-GB');
  });
});

describe('formatMoney', () => {
  it('formats EUR with a decimal comma and a trailing symbol in Spanish', () => {
    expect(formatMoney(1234.5, 'es')).toBe('1234,50 €');
    expect(formatMoney(12345.6, 'es')).toBe('12.345,60 €');
  });

  it('formats EUR with a decimal point and a leading symbol in English (en-GB)', () => {
    expect(formatMoney(1234.5, 'en')).toBe('€1,234.50');
    expect(formatMoney(12345.6, 'en')).toBe('€12,345.60');
  });
});

describe('formatNumber', () => {
  it('groups with the language separators', () => {
    expect(formatNumber(1234567.891, 'es')).toBe('1.234.567,891');
    expect(formatNumber(1234567.891, 'en')).toBe('1,234,567.891');
  });
});

describe('formatDate', () => {
  const date = new Date(Date.UTC(2026, 9, 5, 12));

  it('formats the medium date of the app locale, in UTC', () => {
    expect(formatDate(date, 'es')).toBe('5 oct 2026');
    expect(formatDate(date, 'en')).toBe('5 Oct 2026');
  });

  it('accepts an ISO string', () => {
    expect(formatDate('2026-10-05T12:00:00Z', 'es')).toBe('5 oct 2026');
  });
});

describe('browser locale independence', () => {
  it('ignores navigator.language', () => {
    vi.spyOn(navigator, 'language', 'get').mockReturnValue('de-DE');
    vi.spyOn(navigator, 'languages', 'get').mockReturnValue(['de-DE']);
    expect(formatMoney(1234.5, 'en')).toBe('€1,234.50');
    expect(formatNumber(1234567.891, 'es')).toBe('1.234.567,891');
  });
});
