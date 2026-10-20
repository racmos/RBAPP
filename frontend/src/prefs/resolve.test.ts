import { afterEach, describe, expect, it } from 'vitest';
import { setViewport } from '@/test/viewport';
import { EMPTY_PREFS } from './domain';
import { isPhone, resolvePrefs } from './resolve';

describe('Auto resolution (PREF-6, R1)', () => {
  afterEach(() => setViewport(1280));

  it('tells a phone from a desktop at the 860 px edge', () => {
    setViewport(859);
    expect(isPhone()).toBe(true);
    setViewport(860);
    expect(isPhone()).toBe(false);
  });

  it('Auto density is compact on a phone and regular on a desktop', () => {
    expect(resolvePrefs(EMPTY_PREFS, { phone: true }).density).toBe('compact');
    expect(resolvePrefs(EMPTY_PREFS, { phone: false }).density).toBe('regular');
  });

  it('Auto collection view is grid on a phone and table on a desktop', () => {
    expect(resolvePrefs(EMPTY_PREFS, { phone: true }).collectionView).toBe('grid');
    expect(resolvePrefs(EMPTY_PREFS, { phone: false }).collectionView).toBe('table');
  });

  it('Auto accent is orange and Auto background is 100', () => {
    const effective = resolvePrefs(EMPTY_PREFS, { phone: false });
    expect(effective.accent).toBe('orange');
    expect(effective.bgIntensity).toBe(100);
  });

  it('an explicit value wins over Auto at any width', () => {
    const raw = {
      ...EMPTY_PREFS,
      density: 'comfy',
      accent: 'cyan',
      bg_intensity: 0,
      collection_view: 'table',
    } as const;
    expect(resolvePrefs(raw, { phone: true })).toEqual({
      density: 'comfy',
      accent: 'cyan',
      bgIntensity: 0,
      collectionView: 'table',
    });
  });

  it('keeps an explicit regular density on a phone', () => {
    expect(resolvePrefs({ ...EMPTY_PREFS, density: 'regular' }, { phone: true }).density).toBe(
      'regular',
    );
  });
});
