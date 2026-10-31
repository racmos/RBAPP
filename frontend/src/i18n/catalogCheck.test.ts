/** English catalog completeness (owner feedback S21): English is the only catalog. */
import { describe, expect, it } from 'vitest';
import { checkCatalog, type Catalogs } from './catalogCheck';
import { NAMESPACES, resources } from './resources';

describe('i18n catalog', () => {
  it('bundles English only, with every namespace', () => {
    expect(Object.keys(resources)).toEqual(['en']);
    for (const namespace of NAMESPACES) {
      expect(resources.en[namespace], `en:${namespace}`).toBeDefined();
    }
  });

  it('has no empty strings, complete English plurals and no Spanish characters', () => {
    expect(checkCatalog(resources.en as unknown as Catalogs)).toEqual([]);
  });
});

describe('checkCatalog', () => {
  it('reports an empty string, naming namespace and key', () => {
    expect(checkCatalog({ common: { a: { b: '' } } })).toEqual([
      { kind: 'empty', namespace: 'common', key: 'a.b', detail: 'empty string' },
    ]);
  });

  it('reports a plural group without a form English needs', () => {
    expect(checkCatalog({ nav: { items_one: '{{count}} item' } })).toEqual([
      {
        kind: 'missing-plural',
        namespace: 'nav',
        key: 'items_other',
        detail: 'en requires one, other',
      },
    ]);
  });

  it('reports a plural form English never uses (a Spanish leftover)', () => {
    expect(
      checkCatalog({
        nav: {
          items_one: '{{count}} item',
          items_many: '{{count}} items',
          items_other: '{{count}} items',
        },
      }),
    ).toEqual([
      { kind: 'extra-plural', namespace: 'nav', key: 'items_many', detail: 'en uses one, other' },
    ]);
  });

  it('reports Spanish-only characters', () => {
    expect(checkCatalog({ cards: { add: 'Añadir', ask: '¿Seguro?' } })).toEqual([
      { kind: 'spanish', namespace: 'cards', key: 'add', detail: 'Añadir' },
      { kind: 'spanish', namespace: 'cards', key: 'ask', detail: '¿Seguro?' },
    ]);
  });

  it('accepts a complete catalog', () => {
    expect(
      checkCatalog({ common: { items_one: '{{count}} item', items_other: '{{count}} items' } }),
    ).toEqual([]);
  });
});
