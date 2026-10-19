// @vitest-environment node
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { checkParity, findUnusedKeys, flatten, placeholders, requiredPluralForms } from './parity';
import { resources } from './resources';

describe('flatten', () => {
  it('turns nested catalogs into dotted keys', () => {
    expect(flatten({ a: { b: 'x', c: { d: 'y' } }, e: 'z' })).toEqual({
      'a.b': 'x',
      'a.c.d': 'y',
      e: 'z',
    });
  });
});

describe('placeholders', () => {
  it('lists the {{names}} of a string, ignoring spacing and format options', () => {
    expect(placeholders('Hola {{ name }}, quedan {{count}} y {{when, datetime}}')).toEqual([
      'count',
      'name',
      'when',
    ]);
    expect(placeholders('sin variables')).toEqual([]);
  });
});

describe('requiredPluralForms', () => {
  it('follows Intl.PluralRules for each language', () => {
    expect(requiredPluralForms('en')).toEqual(['one', 'other']);
    expect(requiredPluralForms('es')).toEqual(expect.arrayContaining(['one', 'other']));
  });
});

describe('checkParity: failing fixtures (I18N-1)', () => {
  it('names the key and the language of a missing key', () => {
    const issues = checkParity({
      es: { auth: { login: { title: 'Entrar', extra: 'Solo ES' } } },
      en: { auth: { login: { title: 'Sign in' } } },
    });
    expect(issues).toEqual([
      expect.objectContaining({
        kind: 'missing-key',
        language: 'en',
        namespace: 'auth',
        key: 'login.extra',
      }),
    ]);
  });

  it('also catches a key that only the other language has', () => {
    const issues = checkParity({
      es: { auth: { a: 'a' } },
      en: { auth: { a: 'a', onlyEn: 'x' } },
    });
    expect(issues).toEqual([
      expect.objectContaining({ kind: 'missing-key', language: 'es', key: 'onlyEn' }),
    ]);
  });

  it('flags a namespace that one language lacks', () => {
    const issues = checkParity({
      es: { auth: { a: 'a' }, nav: { b: 'b' } },
      en: { auth: { a: 'a' } },
    });
    expect(issues).toEqual([
      expect.objectContaining({ kind: 'missing-key', language: 'en', namespace: 'nav', key: 'b' }),
    ]);
  });

  it('fails on mismatched placeholders ({{count}} vs {{n}})', () => {
    const issues = checkParity({
      es: { auth: { left: 'Quedan {{count}}' } },
      en: { auth: { left: 'Left {{n}}' } },
    });
    expect(issues).toHaveLength(1);
    expect(issues[0]).toMatchObject({ kind: 'placeholder-mismatch', key: 'left' });
    expect(issues[0].detail).toContain('count');
    expect(issues[0].detail).toContain('n');
  });

  it('fails on a missing plural form required by the language', () => {
    const en = { auth: { left_one: 'one second' } };
    const issues = checkParity({
      es: { auth: { left_one: 'un segundo', left_many: 'm', left_other: 'o' } },
      en,
    });
    expect(issues).toContainEqual(
      expect.objectContaining({ kind: 'missing-plural', language: 'en', key: 'left_other' }),
    );
  });

  it('accepts a complete plural group in each language', () => {
    const forms = (lang: 'es' | 'en') =>
      Object.fromEntries(
        requiredPluralForms(lang).map((form) => [`left_${form}`, `{{count}} ${form}`]),
      );
    expect(checkParity({ es: { auth: forms('es') }, en: { auth: forms('en') } })).toEqual([]);
  });

  it('passes when both languages match', () => {
    expect(
      checkParity({ es: { auth: { a: 'Hola {{x}}' } }, en: { auth: { a: 'Hi {{x}}' } } }),
    ).toEqual([]);
  });
});

describe('findUnusedKeys', () => {
  const catalogs = { auth: { login: { title: 'T', unused: 'U' }, code: { a: 'A' } } };

  it('reports keys whose path appears in no source string', () => {
    const source = "t('login.title'); t(`code.${c}`)";
    expect(findUnusedKeys(catalogs, source)).toEqual(['auth:login.unused']);
  });

  it('counts a key as used by its namespaced form or a dynamic template prefix', () => {
    expect(
      findUnusedKeys(catalogs, "t('auth:login.unused'); t('login.title'); t(`code.${x}`)"),
    ).toEqual([]);
  });

  it('strips plural suffixes before looking for the key', () => {
    expect(
      findUnusedKeys({ auth: { left_one: 'a', left_other: 'b' } }, "t('left', { count })"),
    ).toEqual([]);
  });
});

describe('the real catalogs (I18N-1)', () => {
  it('have parity between es and en', () => {
    expect(checkParity(resources)).toEqual([]);
  });

  it('ship the five required namespaces in both languages', () => {
    for (const lang of ['es', 'en'] as const) {
      expect(Object.keys(resources[lang]).sort()).toEqual([
        'auth',
        'common',
        'errors',
        'nav',
        'prefs',
      ]);
    }
  });

  it('has no empty strings', () => {
    for (const lang of ['es', 'en'] as const) {
      for (const [namespace, catalog] of Object.entries(resources[lang])) {
        const empty = Object.entries(flatten(catalog)).filter(([, text]) => text.trim() === '');
        expect(empty, `${lang}/${namespace}`).toEqual([]);
      }
    }
  });

  it('reports unused keys as a warning list (does not fail)', () => {
    const srcDir = fileURLToPath(new URL('../', import.meta.url));
    const files = (dir: string): string[] =>
      readdirSync(dir, { withFileTypes: true }).flatMap((entry) =>
        entry.isDirectory()
          ? files(join(dir, entry.name))
          : /\.(ts|tsx)$/.test(entry.name) && !/\.test\./.test(entry.name)
            ? [join(dir, entry.name)]
            : [],
      );
    const source = files(srcDir)
      .map((file) => readFileSync(file, 'utf8'))
      .join('\n');
    const unused = findUnusedKeys(resources.es, source);
    if (unused.length > 0) console.warn(`i18n: ${unused.length} unused keys\n${unused.join('\n')}`);
    expect(Array.isArray(unused)).toBe(true);
  });
});
