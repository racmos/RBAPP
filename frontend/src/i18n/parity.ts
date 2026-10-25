/** Catalog checks (I18N-1): used by the Vitest parity test, never shipped to the browser. */
type Catalog = { [key: string]: string | Catalog };
export type Catalogs = Record<string, Record<string, Catalog>>;

export type ParityIssue = {
  kind: 'missing-key' | 'placeholder-mismatch' | 'missing-plural';
  language: string;
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

/** The sorted `{{names}}` of an i18next string (format options after a comma are ignored). */
export function placeholders(text: string): string[] {
  const names = [...text.matchAll(/\{\{\s*([\w.]+)\s*(?:,[^}]*)?\}\}/g)].map((match) => match[1]);
  return [...new Set(names)].sort();
}

/** Plural categories the language needs (`Intl.PluralRules`), the same source as i18next. */
export function requiredPluralForms(language: string): string[] {
  return new Intl.PluralRules(language).resolvedOptions().pluralCategories;
}

const PLURAL_SUFFIX = /^(.*)_(zero|one|two|few|many|other)$/;

/** Plural groups of a flat catalog: base key -> forms present. */
function pluralGroups(flat: Record<string, string>): Map<string, Set<string>> {
  const groups = new Map<string, Set<string>>();
  for (const key of Object.keys(flat)) {
    const match = PLURAL_SUFFIX.exec(key);
    if (match) groups.set(match[1], (groups.get(match[1]) ?? new Set()).add(match[2]));
  }
  return groups;
}

/**
 * Compare every language with every other: missing keys (naming key and language), different
 * `{{placeholders}}`, and plural groups that lack a form the language requires.
 */
export function checkParity(catalogs: Catalogs): ParityIssue[] {
  const issues: ParityIssue[] = [];
  const languages = Object.keys(catalogs);
  const flat = Object.fromEntries(
    languages.map((lang) => [
      lang,
      Object.fromEntries(
        Object.entries(catalogs[lang]).map(([namespace, catalog]) => [namespace, flatten(catalog)]),
      ),
    ]),
  );
  const namespaces = [...new Set(languages.flatMap((lang) => Object.keys(flat[lang])))].sort();

  // Plural forms differ per language (es has `many`, en does not): presence and placeholders are
  // compared per base key, and the forms themselves are checked separately below.
  const byBase = (catalog: Record<string, string>): Record<string, string> => {
    const merged: Record<string, string> = {};
    for (const [key, text] of Object.entries(catalog)) {
      const base = key.replace(PLURAL_SUFFIX, '$1');
      merged[base] = base in merged ? `${merged[base]} ${text}` : text;
    }
    return merged;
  };

  for (const namespace of namespaces) {
    const bases = Object.fromEntries(
      languages.map((lang) => [lang, byBase(flat[lang][namespace] ?? {})]),
    );
    const keys = [...new Set(languages.flatMap((lang) => Object.keys(bases[lang])))].sort();
    for (const key of keys) {
      const present = languages.filter((lang) => key in bases[lang]);
      for (const language of languages.filter((lang) => !present.includes(lang))) {
        issues.push({
          kind: 'missing-key',
          language,
          namespace,
          key,
          detail: `present in ${present.join(', ')}`,
        });
      }
      const variants = new Set(present.map((lang) => placeholders(bases[lang][key]).join('|')));
      if (variants.size > 1) {
        const detail = present
          .map((lang) => `${lang}: {${placeholders(bases[lang][key]).join(', ')}}`)
          .join(' vs ');
        issues.push({ kind: 'placeholder-mismatch', language: present[0], namespace, key, detail });
      }
    }
    for (const language of languages) {
      const catalog = flat[language][namespace] ?? {};
      for (const [base, forms] of pluralGroups(catalog)) {
        for (const form of requiredPluralForms(language).filter((name) => !forms.has(name))) {
          issues.push({
            kind: 'missing-plural',
            language,
            namespace,
            key: `${base}_${form}`,
            detail: `${language} requires ${requiredPluralForms(language).join(', ')}`,
          });
        }
      }
    }
  }
  return issues;
}

/**
 * Keys no source string refers to (a warning list, I18N-1). A key counts as used when its path
 * (with or without the plural suffix and the namespace) appears in a quoted string, or when a
 * template literal starts with a prefix of it (`code.${x}`).
 */
export function findUnusedKeys(catalogs: Record<string, Catalog>, source: string): string[] {
  const literals = new Set([...source.matchAll(/(['"`])((?:(?!\1)[^\\\n])*)\1/g)].map((m) => m[2]));
  const prefixes = [...source.matchAll(/`([^`$]*)\$\{/g)].map((m) => m[1]).filter(Boolean);
  const unused: string[] = [];
  for (const [namespace, catalog] of Object.entries(catalogs)) {
    for (const key of Object.keys(flatten(catalog))) {
      const bare = key.replace(PLURAL_SUFFIX, '$1');
      const forms = [key, bare, `${namespace}:${key}`, `${namespace}:${bare}`];
      const used =
        forms.some((form) => literals.has(form)) ||
        forms.some((form) => prefixes.some((prefix) => form.startsWith(prefix)));
      if (!used) unused.push(`${namespace}:${key}`);
    }
  }
  return unused;
}
