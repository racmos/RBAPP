import type { resources } from './resources';

// English is the source of truth: a missing key is a compile error (I18N-5, D14).
declare module 'i18next' {
  interface CustomTypeOptions {
    defaultNS: 'common';
    resources: (typeof resources)['en'];
  }
}
