import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { SRC_DIR, declsFor, readCss } from '@/test/css';

const css = readCss(join(SRC_DIR, 'collection/CollectionTable.module.css'));
const value = (selector: string, prop: string) =>
  declsFor(css, selector).find((decl) => decl.prop === prop)?.value;
const px = (text: string | undefined) => Number(/^(\d+)px$/.exec(text ?? '')?.[1] ?? NaN);

describe('CollectionTable columns (owner feedback S18 i)', () => {
  it('gives the condition and language selects room for "Sin especificar" and "Near Mint"', () => {
    // `.table .select` outranks the Select primitive's own `.select { width: 100% }`
    expect(px(value('.table .select', 'min-width'))).toBeGreaterThanOrEqual(160);
    expect(value('.table .select', 'max-width')).toBeUndefined();
    expect(value('.table .select', 'width')).toBe(value('.table .select', 'min-width'));
    expect(declsFor(css, '.select')).toEqual([]);
  });

  it('never wraps or squeezes the numbers (market price, profit, trend)', () => {
    expect(value('.numeric', 'white-space')).toBe('nowrap');
    expect(value('.table th', 'white-space')).toBe('nowrap');
  });
});
