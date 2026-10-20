import { hasSignedInHint } from '@/auth';
import { resolveLang, storedLang, type Lang } from '@/i18n';
import { applyPrefs } from './apply';
import { isPhone, resolvePrefs } from './resolve';
import { readMirror } from './storage';
import type { Prefs } from './types';

/**
 * Before React renders (D18, PREF-7): read the mirror, resolve Auto against this viewport and
 * write the result to `<html>`, so there is no theme flash. The mirror language counts only for
 * a browser that was signed in; an anonymous one follows `rb_lang` and the browser (I18N-2).
 */
export function bootstrapPrefs(): { prefs: Prefs; lang: Lang } {
  const prefs = readMirror();
  const lang = resolveLang({
    accountLang: hasSignedInHint() ? prefs.lang : null,
    storedLang: storedLang(),
    browserLanguages: navigator.languages,
  });
  applyPrefs(document.documentElement, { ...resolvePrefs(prefs, { phone: isPhone() }), lang });
  return { prefs, lang };
}
