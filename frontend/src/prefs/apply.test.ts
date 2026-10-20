import { afterEach, describe, expect, it } from 'vitest';
import { applyPrefs } from './apply';

const root = document.documentElement;
const base = {
  density: 'regular',
  accent: 'orange',
  bgIntensity: 100,
  collectionView: 'table',
  lang: 'es',
} as const;

afterEach(() => {
  root.removeAttribute('data-density');
  root.removeAttribute('data-accent');
  root.removeAttribute('data-bg');
  root.removeAttribute('style');
  root.lang = '';
});

describe('applyPrefs (D18)', () => {
  it('sets the accent and the language on <html>', () => {
    applyPrefs(root, { ...base, accent: 'cyan', lang: 'en' });
    expect(root.dataset.accent).toBe('cyan');
    expect(root.lang).toBe('en');
  });

  it('removes data-density for regular and sets it for the others', () => {
    applyPrefs(root, { ...base, density: 'compact' });
    expect(root.dataset.density).toBe('compact');
    applyPrefs(root, { ...base, density: 'comfy' });
    expect(root.dataset.density).toBe('comfy');
    applyPrefs(root, { ...base, density: 'regular' });
    expect(root.hasAttribute('data-density')).toBe(false);
  });

  it('applies the background variables and data-bg', () => {
    applyPrefs(root, { ...base, bgIntensity: 40 });
    expect(root.dataset.bg).toBe('on');
    expect(root.style.getPropertyValue('--bg-image-opacity')).toBe('0.4');
    expect(root.style.getPropertyValue('--bg-image-filter')).toContain('blur(3px)');
  });

  it('turns the image layer off at 0', () => {
    applyPrefs(root, { ...base, bgIntensity: 0 });
    expect(root.dataset.bg).toBe('off');
    expect(root.style.getPropertyValue('--bg-image-opacity')).toBe('0');
  });
});
