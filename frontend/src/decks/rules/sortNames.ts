// Names (F5-a S3, D-F5-7): printings of one `nameKey` are one card, and names sort by
// `(nameKey, name)` in code-point order, never with a locale collation.

// The characters Python's `str.split()` splits on (`str.isspace`); JS `\s` differs.
const WHITESPACE =
  // eslint-disable-next-line no-control-regex -- \x1c-\x1f are whitespace for Python.
  /[\t\n\v\f\r\x1c-\x1f \x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+/;

/** Python `s.split()`: words between runs of whitespace, no empty words. */
export function splitWords(text: string): string[] {
  return text.split(WHITESPACE).filter((word) => word !== '');
}

/** `name_key` of `app/services/bans.py`: typographic apostrophes become `'`, case is folded
 * (`toLocaleLowerCase('en')` for Python `casefold()`) and whitespace runs become one space. */
export function nameKey(name: string): string {
  return splitWords(name.replace(/’/g, "'").replace(/‘/g, "'").toLocaleLowerCase('en')).join(' ');
}

/** Python string order: by code point (JS `<` compares UTF-16 units, which differs for
 * characters outside the BMP). */
export function compareCodePoints(a: string, b: string): number {
  let i = 0;
  while (i < a.length && i < b.length) {
    const x = a.codePointAt(i)!;
    const y = b.codePointAt(i)!;
    if (x !== y) return x < y ? -1 : 1;
    i += x > 0xffff ? 2 : 1;
  }
  return a.length === b.length ? 0 : a.length < b.length ? -1 : 1;
}

/** `name_sort_key` order: `nameKey`, ties by the raw name. */
export function compareNames(a: string, b: string): number {
  return compareCodePoints(nameKey(a), nameKey(b)) || compareCodePoints(a, b);
}

/** A sorted copy of `names` (`sort_names`). */
export function sortNames(names: readonly string[]): string[] {
  return [...names].sort(compareNames);
}
