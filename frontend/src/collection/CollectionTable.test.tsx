import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { SRC_DIR, declsFor, readCss, rules } from '@/test/css';

const css = readCss(join(SRC_DIR, 'collection/CollectionTable.module.css'));
const value = (selector: string, prop: string) =>
  declsFor(css, selector).find((decl) => decl.prop === prop)?.value;
const px = (text: string | undefined) => Number(/^(\d+)px$/.exec(text ?? '')?.[1] ?? NaN);

describe('CollectionTable columns (owner feedback S18 i, S24 q)', () => {
  it('gives the condition and language selects a fixed width for their codes', () => {
    // `.table .code` outranks the Select primitive's own `.select { width: 100% }`; a select at
    // 100 % of an auto column was squeezed to "Si…" (S18 i). The selects show the code ("NM",
    // "FR") and "—" for no value (S24 q), so "Not set" no longer sets the width.
    expect(px(value('.table .code', 'width'))).toBeGreaterThanOrEqual(60);
    expect(px(value('.table .code', 'width'))).toBeLessThanOrEqual(72);
    expect(value('.table .code', 'min-width')).toBe(value('.table .code', 'width'));
    expect(value('.table .code', 'max-width')).toBeUndefined();
    expect(declsFor(css, '.select')).toEqual([]);
  });

  it('never wraps or squeezes the numbers (market price, profit, trend)', () => {
    expect(value('.numeric', 'white-space')).toBe('nowrap');
    expect(value('.table th', 'white-space')).toBe('nowrap');
  });

  it('fits the content column: no fixed minimum, compact cells and inputs (S24 q)', () => {
    expect(value('.table', 'min-width')).toBeUndefined();
    expect(value('.table td', 'padding')).toBe('4px');
    expect(value('.table th', 'padding')).toBe('8px 4px');
    expect(px(value('.number', 'width'))).toBeLessThanOrEqual(48);
    expect(px(value('.money', 'width'))).toBeLessThanOrEqual(64);
    expect(px(value('.thumb', 'width'))).toBeLessThanOrEqual(32);
  });

  it('the page takes the wide width from 1240 px (S24 q)', () => {
    const page = readCss(join(SRC_DIR, 'collection/CollectionDesktop.module.css'));
    const wide = rules(page).find(
      (rule) =>
        rule.selectors.includes('.page') && rule.atRules.includes('media (min-width: 1240px)'),
    );
    expect(wide?.decls).toContainEqual({ prop: 'max-width', value: 'var(--maxw-wide)' });
  });
});
