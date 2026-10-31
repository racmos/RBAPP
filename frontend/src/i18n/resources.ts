import enAdmin from './locales/en/admin.json';
import enAuth from './locales/en/auth.json';
import enCards from './locales/en/cards.json';
import enCollection from './locales/en/collection.json';
import enCommon from './locales/en/common.json';
import enEnums from './locales/en/enums.json';
import enErrors from './locales/en/errors.json';
import enNav from './locales/en/nav.json';
import enPrefs from './locales/en/prefs.json';
import enProducts from './locales/en/products.json';

/**
 * Catalogs are bundled and precached: no translation requests at run time (I18N-1). English is
 * the only language (owner feedback S21): there is no Spanish catalog and no language choice.
 */
export const resources = {
  en: {
    common: enCommon,
    nav: enNav,
    auth: enAuth,
    errors: enErrors,
    prefs: enPrefs,
    admin: enAdmin,
    enums: enEnums,
    cards: enCards,
    collection: enCollection,
    products: enProducts,
  },
};

export const NAMESPACES = [
  'common',
  'nav',
  'auth',
  'errors',
  'prefs',
  'admin',
  'enums',
  'cards',
  'collection',
  'products',
] as const;
export type Namespace = (typeof NAMESPACES)[number];
