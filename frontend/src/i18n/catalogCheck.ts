/** English catalog checks (I18N-1, owner feedback S21): used by the Vitest catalog test, never
    shipped to the browser. Missing keys are caught by `npm run typecheck`. */
type Catalog = { [key: string]: string | Catalog };
export type Catalogs = Record<string, Catalog>;

export type CatalogIssue = {
  kind: 'empty' | 'missing-plural' | 'extra-plural' | 'spanish';
  namespace: string;
  key: string;
  detail: string;
};

/** `{a: {b: 'x'}}` -> `{'a.b': 'x'}` */
export function flatten(catalog: Catalog, prefix = ''): Record<string, string> {
  const flat: Record<string, string> = {};
  for (const [name, value] of Object.entries(catalog)) {
    const path = prefix ? `${prefix}.${name}` : name;
    if (typeof value === 'string') flat[path] = value;
    else Object.assign(flat, flatten(value, path));
  }
  return flat;
}

const PLURAL_SUFFIX = /^(.*)_(zero|one|two|few|many|other)$/;
/** Characters that only Spanish text uses; English copy never needs them. */
const SPANISH = /[áéíóúñÁÉÍÓÚÑ¿¡]/;
/** Plural categories English needs (`Intl.PluralRules`), the same source as i18next. */
const ENGLISH_PLURALS: readonly string[] = new Intl.PluralRules('en').resolvedOptions()
  .pluralCategories;

/**
 * Empty strings, plural groups without a form English needs or with one it never uses (`_many`
 * is a Spanish leftover), and Spanish-only characters.
 */
export function checkCatalog(catalogs: Catalogs): CatalogIssue[] {
  const issues: CatalogIssue[] = [];
  for (const [namespace, catalog] of Object.entries(catalogs)) {
    const flat = flatten(catalog);
    const plurals = new Map<string, Set<string>>();
    for (const [key, text] of Object.entries(flat)) {
      if (text.trim() === '')
        issues.push({ kind: 'empty', namespace, key, detail: 'empty string' });
      if (SPANISH.test(text)) issues.push({ kind: 'spanish', namespace, key, detail: text });
      const match = PLURAL_SUFFIX.exec(key);
      if (match) plurals.set(match[1], (plurals.get(match[1]) ?? new Set()).add(match[2]));
    }
    for (const [base, forms] of plurals) {
      for (const form of ENGLISH_PLURALS.filter((name) => !forms.has(name))) {
        issues.push({
          kind: 'missing-plural',
          namespace,
          key: `${base}_${form}`,
          detail: `en requires ${ENGLISH_PLURALS.join(', ')}`,
        });
      }
      for (const form of [...forms].filter((name) => !ENGLISH_PLURALS.includes(name))) {
        issues.push({
          kind: 'extra-plural',
          namespace,
          key: `${base}_${form}`,
          detail: `en uses ${ENGLISH_PLURALS.join(', ')}`,
        });
      }
    }
  }
  return issues;
}
