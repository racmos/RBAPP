import { applyBackground } from '@/lib/background';
import type { Lang } from '@/i18n';
import type { EffectivePrefs } from './types';

/**
 * Write the effective values to `<html>` (D18): `data-accent`, `data-density` (absent for
 * regular), `lang`, and the background state through `applyBackground`.
 */
export function applyPrefs(root: HTMLElement, prefs: EffectivePrefs & { lang: Lang }): void {
  root.dataset.accent = prefs.accent;
  if (prefs.density === 'regular') root.removeAttribute('data-density');
  else root.dataset.density = prefs.density;
  root.lang = prefs.lang;
  applyBackground(root, prefs.bgIntensity);
}
