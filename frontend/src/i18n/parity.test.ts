/** Catalog parity (G5, re-created by F13-a): ES and EN must agree. */
import { describe, expect, it } from 'vitest';
import { checkParity, type Catalogs } from './parity';
import { LANGUAGES, NAMESPACES, resources } from './resources';

describe('i18n catalogs', () => {
  it('every language bundles every namespace', () => {
    for (const lang of LANGUAGES) {
      for (const namespace of NAMESPACES) {
        expect(resources[lang][namespace], `${lang}:${namespace}`).toBeDefined();
      }
    }
  });

  it('agree on keys, placeholders and plural forms', () => {
    expect(checkParity(resources as unknown as Catalogs)).toEqual([]);
  });
});
