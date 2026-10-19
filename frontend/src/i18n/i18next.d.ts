import type { resources } from './resources';

// ES is the source of truth: a key missing from it is a compile error (I18N-5, D14).
declare module 'i18next' {
  interface CustomTypeOptions {
    defaultNS: 'common';
    resources: (typeof resources)['es'];
  }
}
