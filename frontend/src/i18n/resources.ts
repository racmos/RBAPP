import enAdmin from './locales/en/admin.json';
import enAuth from './locales/en/auth.json';
import enCards from './locales/en/cards.json';
import enCommon from './locales/en/common.json';
import enEnums from './locales/en/enums.json';
import enErrors from './locales/en/errors.json';
import enNav from './locales/en/nav.json';
import enPrefs from './locales/en/prefs.json';
import esAdmin from './locales/es/admin.json';
import esAuth from './locales/es/auth.json';
import esCards from './locales/es/cards.json';
import esCommon from './locales/es/common.json';
import esEnums from './locales/es/enums.json';
import esErrors from './locales/es/errors.json';
import esNav from './locales/es/nav.json';
import esPrefs from './locales/es/prefs.json';

export const LANGUAGES = ['es', 'en'] as const;
export type Lang = (typeof LANGUAGES)[number];

/** Catalogs are bundled and precached: no runtime fetch of translations (I18N-1). */
export const resources = {
  es: {
    common: esCommon,
    nav: esNav,
    auth: esAuth,
    errors: esErrors,
    prefs: esPrefs,
    admin: esAdmin,
    enums: esEnums,
    cards: esCards,
  },
  en: {
    common: enCommon,
    nav: enNav,
    auth: enAuth,
    errors: enErrors,
    prefs: enPrefs,
    admin: enAdmin,
    enums: enEnums,
    cards: enCards,
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
] as const;
export type Namespace = (typeof NAMESPACES)[number];
