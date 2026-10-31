import { createInstance, type i18n as I18n } from 'i18next';
import { initReactI18next } from 'react-i18next';
import { NAMESPACES, resources as bundled } from './resources';

export { translateDetail, translateError } from './translateError';
export { useDocumentTitle } from './useDocumentTitle';
export { useEnumLabel } from './enumLabel';

/**
 * A ready i18next instance. English is the only language (owner feedback S21): no detection, no
 * stored choice, and `<html lang>` is always `en`.
 */
export async function createI18n(resources: typeof bundled = bundled): Promise<I18n> {
  const instance = createInstance();
  await instance.use(initReactI18next).init({
    resources,
    lng: 'en',
    fallbackLng: 'en',
    supportedLngs: ['en'],
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
  document.documentElement.lang = 'en';
  return instance;
}
