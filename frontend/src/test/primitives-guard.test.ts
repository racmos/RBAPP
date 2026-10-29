import { readdirSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { describe, expect, it } from 'vitest';
import { SRC_DIR, cssFiles, readCss, rules } from './css';

/** Every non-test `.tsx` file below `src/`, as a path relative to `src/`. */
function tsxFiles(): string[] {
  const walk = (dir: string): string[] =>
    readdirSync(dir, { withFileTypes: true }).flatMap((entry) =>
      entry.isDirectory()
        ? walk(join(dir, entry.name))
        : entry.name.endsWith('.tsx') && !entry.name.includes('.test.')
          ? [join(dir, entry.name)]
          : [],
    );
  return walk(SRC_DIR)
    .map((file) => relative(SRC_DIR, file).replaceAll('\\', '/'))
    .sort();
}

const source = (file: string) => readFileSync(join(SRC_DIR, file), 'utf8');

describe('shared primitives guard (owner feedback 2026-10-29)', () => {
  it('renders every dropdown through components/ui/Select (S2)', () => {
    const raw = tsxFiles().filter(
      (file) => file !== 'components/ui/Select.tsx' && /<select[\s>]/.test(source(file)),
    );
    expect(raw).toEqual([]);
  });

  it('renders every checkbox through components/ui/Checkbox (S3)', () => {
    const raw = tsxFiles().filter(
      (file) => file !== 'components/ui/Checkbox.tsx' && /type="checkbox"/.test(source(file)),
    );
    expect(raw).toEqual([]);
  });

  it('wraps every data table in TableScroll (S1)', () => {
    // The import preview scrolls inside its own box and the chart table is a small fallback.
    const exempt = ['collection/ImportWizard.tsx', 'components/charts/PriceChart.tsx'];
    const missing = tsxFiles().filter(
      (file) =>
        !exempt.includes(file) &&
        /<table[\s>]/.test(source(file)) &&
        !/<TableScroll/.test(source(file)),
    );
    expect(missing).toEqual([]);
  });

  it('never offsets a sticky table header from its scroll box (S1)', () => {
    const offenders = cssFiles().flatMap((file) =>
      rules(readCss(file))
        .filter(
          (rule) =>
            rule.selectors.some((selector) => /(^|[\s>])th\b|\.th\b/.test(selector)) &&
            rule.decls.some((decl) => decl.prop === 'position' && decl.value === 'sticky') &&
            rule.decls.some((decl) => decl.prop === 'top' && decl.value !== '0'),
        )
        .map((rule) => `${relative(SRC_DIR, file)} ${rule.selectors.join(', ')}`),
    );
    expect(offenders).toEqual([]);
  });
});
