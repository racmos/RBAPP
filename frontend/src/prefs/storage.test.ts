import { describe, expect, it } from 'vitest';
import { EMPTY_PREFS } from './domain';
import { MIRROR_KEY, readMirror, writeMirror } from './storage';

describe('rb_prefs_v1 mirror (PREF-7, R4)', () => {
  it('uses the key of the spec', () => {
    expect(MIRROR_KEY).toBe('rb_prefs_v1');
  });

  it('reads the empty prefs when nothing is stored', () => {
    expect(readMirror()).toEqual(EMPTY_PREFS);
  });

  it('round trips the five fields and keeps null (Auto)', () => {
    const prefs = {
      lang: null,
      density: 'comfy',
      accent: 'cyan',
      bg_intensity: 0,
      collection_view: null,
    } as const;
    writeMirror(prefs);
    expect(readMirror()).toEqual(prefs);
    expect(JSON.parse(localStorage.getItem(MIRROR_KEY)!)).toEqual(prefs);
  });

  it('stores only the five preference fields', () => {
    writeMirror({ ...EMPTY_PREFS, accent: 'orange', secret: 'x' } as never);
    expect(Object.keys(JSON.parse(localStorage.getItem(MIRROR_KEY)!)).sort()).toEqual([
      'accent',
      'bg_intensity',
      'collection_view',
      'density',
      'lang',
    ]);
  });

  it('ignores a corrupt mirror without throwing', () => {
    localStorage.setItem(MIRROR_KEY, '{not json');
    expect(readMirror()).toEqual(EMPTY_PREFS);
  });

  it('ignores a mirror that is JSON but not an object', () => {
    localStorage.setItem(MIRROR_KEY, '"text"');
    expect(readMirror()).toEqual(EMPTY_PREFS);
  });

  it('drops only the out-of-domain fields', () => {
    localStorage.setItem(MIRROR_KEY, JSON.stringify({ accent: 'cyan', density: 'huge' }));
    expect(readMirror()).toEqual({ ...EMPTY_PREFS, accent: 'cyan' });
  });
});
