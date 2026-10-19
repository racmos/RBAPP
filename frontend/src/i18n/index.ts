import { createInstance, type i18n as I18n } from 'i18next';
import { initReactI18next } from 'react-i18next';
import { NAMESPACES, resources as bundled, type Lang } from './resources';

export { LANGUAGES, type Lang } from './resources';
export { initialLang, resolveLang, storeLang, storedLang } from './resolveLang';
export { translateDetail, translateError } from './translateError';
export { useDocumentTitle } from './useDocumentTitle';
export { LanguageToggle } from './LanguageToggle';

/**
 * A ready i18next instance. ES is the fallback (I18N-5); a key missing everywhere renders
 * nothing in production instead of the raw key. `<html lang>` follows the active language.
 */
export async function createI18n(lang: Lang, resources: typeof bundled = bundled): Promise<I18n> {
  const instance = createInstance();
  instance.on('languageChanged', (language) => {
    document.documentElement.lang = language;
  });
  await instance.use(initReactI18next).init({
    resources,
    lng: lang,
    fallbackLng: 'es',
    supportedLngs: ['es', 'en'],
    ns: [...NAMESPACES],
    defaultNS: 'common',
    interpolation: { escapeValue: false },
    // Never show a raw key: typed resources catch it at build time, this covers the rest.
    parseMissingKeyHandler: () => '',
    saveMissing: import.meta.env.DEV,
    missingKeyHandler: (_languages, namespace, key) =>
      console.warn(`i18n: missing ${namespace}:${key}`),
    initAsync: false,
  });
  document.documentElement.lang = instance.language;
  return instance;
}
