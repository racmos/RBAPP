import { hasSignedInHint } from '@/auth';
import { EMPTY_PREFS } from './domain';
import { applyPrefs } from './apply';
import { isPhone, resolvePrefs } from './resolve';
import { readMirror } from './storage';
import type { Prefs } from './types';

/**
 * Before React renders (D18, PREF-7): read the mirror, resolve Auto against this viewport and
 * write the result to `<html>`, so there is no theme flash. The app is English-only, so the
 * language is always `en`.
 */
export function bootstrapPrefs(): { prefs: Prefs } {
  const prefs = hasSignedInHint() ? readMirror() : { ...EMPTY_PREFS };
  applyPrefs(document.documentElement, resolvePrefs(prefs, { phone: isPhone() }));
  return { prefs };
}
