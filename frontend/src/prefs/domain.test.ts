import { describe, expect, it } from 'vitest';
import { EMPTY_PREFS, PREF_KEYS, isPrefValue, sanitizePrefs } from './domain';

describe('preference domains (PREF-2)', () => {
  it('has exactly the five fields of the API', () => {
    expect(PREF_KEYS).toEqual(['lang', 'density', 'accent', 'bg_intensity', 'collection_view']);
    expect(EMPTY_PREFS).toEqual({
      lang: null,
      density: null,
      accent: null,
      bg_intensity: null,
      collection_view: null,
    });
  });

  it.each([
    ['lang', 'es'],
    ['lang', 'en'],
    ['density', 'compact'],
    ['density', 'regular'],
    ['density', 'comfy'],
    ['accent', 'cyan'],
    ['accent', 'orange'],
    ['bg_intensity', 0],
    ['bg_intensity', 100],
    ['bg_intensity', 37],
    ['collection_view', 'table'],
    ['collection_view', 'grid'],
  ] as const)('accepts %s = %s', (key, value) => {
    expect(isPrefValue(key, value)).toBe(true);
  });

  it.each([
    ['lang', 'fr'],
    ['density', 'huge'],
    ['accent', 'purple'],
    ['bg_intensity', 101],
    ['bg_intensity', -1],
    ['bg_intensity', 50.5],
    ['bg_intensity', '50'],
    ['bg_intensity', true],
    ['collection_view', 'list'],
    ['accent', null],
    ['density', undefined],
  ] as const)('rejects %s = %s', (key, value) => {
    expect(isPrefValue(key, value)).toBe(false);
  });

  describe('sanitizePrefs', () => {
    it('keeps valid values, nulls and nothing else', () => {
      expect(
        sanitizePrefs({ accent: 'cyan', density: null, bg_intensity: 40, extra: 'x', lang: 'en' }),
      ).toEqual({
        lang: 'en',
        density: null,
        accent: 'cyan',
        bg_intensity: 40,
        collection_view: null,
      });
    });

    it('turns out-of-domain values into Auto without throwing', () => {
      expect(sanitizePrefs({ accent: 'purple', bg_intensity: 900, density: 7 })).toEqual(
        EMPTY_PREFS,
      );
    });

    it.each([null, undefined, 'text', 42, [], true])('returns the empty prefs for %s', (raw) => {
      expect(sanitizePrefs(raw)).toEqual(EMPTY_PREFS);
    });
  });
});
