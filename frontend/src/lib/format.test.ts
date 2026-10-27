import { describe, expect, it } from 'vitest';
import { formatPct } from './format';

describe('formatPct', () => {
  it('formats a positive Spanish percentage with one decimal', () => {
    const expected = new Intl.NumberFormat('es-ES', {
      style: 'percent',
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
      signDisplay: 'exceptZero',
    }).format(0.1);
    expect(formatPct(10, 'es')).toBe(expected);
  });

  it('formats a negative English percentage with one decimal', () => {
    const expected = new Intl.NumberFormat('en-GB', {
      style: 'percent',
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
      signDisplay: 'exceptZero',
    }).format(-0.0314);
    expect(formatPct(-3.14, 'en')).toBe(expected);
  });

  it('adds a plus sign for positive values', () => {
    expect(formatPct(10, 'en')).toContain('+');
  });

  it('returns the signed zero for 0', () => {
    expect(formatPct(0, 'en')).toBe('0.0%');
  });
});
