import { describe, expect, it } from 'vitest';
import { EMPTY_PREFS, isPrefValue, PREF_KEYS, sanitizePrefs } from './domain';

describe('playset_size preference (F3-c S8)', () => {
  it('is one of the stored keys, Auto by default', () => {
    expect(PREF_KEYS).toContain('playset_size');
    expect(EMPTY_PREFS.playset_size).toBeNull();
  });

  it.each([1, 3, 9])('accepts the integer %i', (value) => {
    expect(isPrefValue('playset_size', value)).toBe(true);
    expect(sanitizePrefs({ playset_size: value }).playset_size).toBe(value);
  });

  it.each([0, 10, 2.5, '3', true, null])('turns %j into Auto', (value) => {
    expect(isPrefValue('playset_size', value)).toBe(false);
    expect(sanitizePrefs({ playset_size: value }).playset_size).toBeNull();
  });
});
