import { applyBackground } from '@/lib/background';
import type { EffectivePrefs } from './types';

/**
 * Write the effective values to `<html>` (D18): `data-accent`, `data-density` (absent for
 * regular), and the background state through `applyBackground`. The app is English-only, so
 * `<html lang>` stays at `en`.
 */
export function applyPrefs(root: HTMLElement, prefs: EffectivePrefs): void {
  root.dataset.accent = prefs.accent;
  if (prefs.density === 'regular') root.removeAttribute('data-density');
  else root.dataset.density = prefs.density;
  root.lang = 'en';
  applyBackground(root, prefs.bgIntensity);
}
