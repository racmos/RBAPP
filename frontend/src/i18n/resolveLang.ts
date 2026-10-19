import { readStorage, writeStorage } from '@/lib/storage';
import { LANGUAGES, type Lang } from './resources';

/** The device's language choice; the account preference overrides it when signed in (R4). */
export const LANG_STORAGE_KEY = 'rb_lang';

const isLang = (value: unknown): value is Lang => LANGUAGES.includes(value as Lang);

type Inputs = {
  accountLang?: string | null;
  storedLang?: string | null;
  browserLanguages?: readonly string[];
};

/** I18N-2: account pref, then rb_lang, then the first supported browser language, then es. */
export function resolveLang({ accountLang, storedLang, browserLanguages = [] }: Inputs): Lang {
  if (isLang(accountLang)) return accountLang;
  if (isLang(storedLang)) return storedLang;
  for (const tag of browserLanguages) {
    const primary = tag.toLowerCase().split('-')[0];
    if (isLang(primary)) return primary;
  }
  return 'es';
}

export function storedLang(): Lang | null {
  const value = readStorage(LANG_STORAGE_KEY);
  return isLang(value) ? value : null;
}

export const storeLang = (lang: Lang): void => writeStorage(LANG_STORAGE_KEY, lang);

/** Language before any session is known (main.tsx, anonymous screens). */
export function initialLang(browserLanguages: readonly string[] = navigator.languages): Lang {
  return resolveLang({ storedLang: storedLang(), browserLanguages });
}
