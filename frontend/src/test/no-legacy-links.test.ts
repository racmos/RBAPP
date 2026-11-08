import { readdirSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { describe, expect, it } from 'vitest';
import { SRC_DIR } from './css';

/**
 * The app never links back to the old Jinja web (PR 2/3 of the Jinja retirement). The app may
 * only name `/riftbound/api` (the JSON API), `/riftbound/app` (itself), `/riftbound/media` and
 * `/riftbound/static` (files); `safeNext.ts` keeps the bare `/riftbound/` prefix to validate
 * `next` values.
 */
const FORBIDDEN = [
  /\/riftbound\/set/,
  /\/riftbound\/card/,
  /\/riftbound\/collection/,
  /\/riftbound\/deck/,
  /\/riftbound\/profile/,
  /\/riftbound\/price/,
  /legacyHref/,
];
/** The old dashboard is the bare product root. */
const ROOT = /["'`]\/riftbound\/["'`]/;
const ROOT_ALLOWED = ['auth/safeNext.ts'];

/** Every non-test `.ts`, `.tsx` and `.json` file below `src/` (test helpers in `src/test/` out). */
function sourceFiles(): string[] {
  const walk = (dir: string): string[] =>
    readdirSync(dir, { withFileTypes: true }).flatMap((entry) =>
      entry.isDirectory()
        ? walk(join(dir, entry.name))
        : /\.(tsx?|json)$/.test(entry.name) && !entry.name.includes('.test.')
          ? [join(dir, entry.name)]
          : [],
    );
  return walk(SRC_DIR)
    .map((file) => relative(SRC_DIR, file).replaceAll('\\', '/'))
    .filter((file) => !file.startsWith('test/'))
    .sort();
}

describe('no links to the old web', () => {
  it('names no Jinja page anywhere in the app sources', () => {
    const offenders = sourceFiles().flatMap((file) => {
      const text = readFileSync(join(SRC_DIR, file), 'utf8');
      const hits = FORBIDDEN.filter((pattern) => pattern.test(text)).map(String);
      if (!ROOT_ALLOWED.includes(file) && ROOT.test(text)) hits.push(String(ROOT));
      return hits.map((hit) => `${file}: ${hit}`);
    });
    expect(offenders).toEqual([]);
  });
});
