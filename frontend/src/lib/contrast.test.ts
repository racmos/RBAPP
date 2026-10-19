// @vitest-environment node
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { SRC_DIR, declsFor, readCss } from '@/test/css';
import { composite, contrast, parseColor, relativeLuminance } from './contrast';

describe('parseColor', () => {
  it('reads 3, 6 and 8 digit hex', () => {
    expect(parseColor('#fff')).toEqual({ r: 255, g: 255, b: 255, a: 1 });
    expect(parseColor('#06222c')).toEqual({ r: 6, g: 34, b: 44, a: 1 });
    expect(parseColor('#06222c80')).toMatchObject({ r: 6, g: 34, b: 44 });
    expect(parseColor('#06222c80').a).toBeCloseTo(128 / 255, 5);
  });

  it('reads rgb() and rgba() with and without spaces', () => {
    expect(parseColor('rgb(1, 2, 3)')).toEqual({ r: 1, g: 2, b: 3, a: 1 });
    expect(parseColor('rgba(13,58,73,0.66)')).toEqual({ r: 13, g: 58, b: 73, a: 0.66 });
    expect(parseColor('rgba(120, 205, 228, .1)').a).toBe(0.1);
  });

  it('rejects what it cannot read', () => {
    expect(() => parseColor('var(--x)')).toThrow(/var\(--x\)/);
  });
});

describe('composite', () => {
  it('blends a translucent colour over an opaque base', () => {
    expect(composite(parseColor('rgba(255,255,255,0.5)'), parseColor('#000'))).toEqual({
      r: 127.5,
      g: 127.5,
      b: 127.5,
      a: 1,
    });
  });

  it('keeps an opaque colour as it is', () => {
    expect(composite(parseColor('#336699'), parseColor('#fff'))).toEqual(parseColor('#336699'));
  });
});

describe('contrast (WCAG 2.2)', () => {
  it('is 21 for white on black and 1 for equal colours', () => {
    expect(contrast('#fff', '#000')).toBe(21);
    expect(contrast('#123456', '#123456')).toBe(1);
  });

  it('is symmetric in luminance order', () => {
    expect(contrast('#000', '#fff')).toBe(21);
  });

  it('composes translucent text and background over the base', () => {
    // 50 % white over black is rgb(127.5): about 5.3:1 against black
    expect(contrast('rgba(255,255,255,0.5)', '#000')).toBeCloseTo(5.3, 1);
    // a translucent panel is composited over the base first
    expect(contrast('#fff', 'rgba(0,0,0,0.5)', '#fff')).toBeCloseTo(contrast('#fff', '#808080'), 1);
  });

  it('matches known relative luminances', () => {
    expect(relativeLuminance(parseColor('#000'))).toBe(0);
    expect(relativeLuminance(parseColor('#fff'))).toBe(1);
    expect(relativeLuminance(parseColor('#7f7f7f'))).toBeCloseTo(0.2122, 3);
  });
});

// DS-7: token pairs used by F1, read from tokens.css so a regression in a value fails here.
const tokens = readCss(join(SRC_DIR, 'styles', 'tokens.css'));
const asMap = (selector: string) =>
  Object.fromEntries(declsFor(tokens, selector).map(({ prop, value }) => [prop, value]));
const root = asMap(':root');

function resolve(value: string, scope: Record<string, string> = root): string {
  const reference = /^var\((--[\w-]+)\)$/.exec(value);
  return reference ? resolve(scope[reference[1]] ?? root[reference[1]], scope) : value;
}
const token = (name: string, scope = root) => resolve(scope[name] ?? root[name], scope);

const BG = token('--bg-0');
const PAIRS: [string, string, string][] = [
  ['--text', '--bg-0', 'page text'],
  ['--text', '--panel', 'panel text'],
  ['--text', '--panel-2', 'solid panel text'],
  ['--text', '--header', 'topbar text'],
  ['--muted', '--bg-0', 'secondary text on the page'],
  ['--muted', '--panel', 'secondary text on a panel'],
  ['--muted-2', '--panel', 'tertiary text on a panel (DS-7 fix)'],
  ['--on-red', '--red-strong', 'white on destructive fill (DS-7 fix)'],
  ['--red-text', '--panel', 'red text on a panel (DS-7 fix)'],
  ['--red-text', '--bg-0', 'red text on the page'],
  ['--green', '--panel', 'success text'],
];

describe('token contrast (DS-7)', () => {
  it.each(PAIRS)('%s on %s is at least 4.5:1 (%s)', (fg, bg) => {
    expect(contrast(token(fg), token(bg), BG)).toBeGreaterThanOrEqual(4.5);
  });

  it.each(['orange', 'cyan'])('accent-ink on the %s accent is at least 4.5:1', (name) => {
    const scope = { ...root, ...asMap(`[data-accent='${name}']`) };
    expect(
      contrast(token('--accent-ink', scope), token('--accent', scope), BG),
    ).toBeGreaterThanOrEqual(4.5);
    // the accent as text on a panel (links, eyebrow) must read too
    expect(contrast(token('--accent', scope), token('--panel', scope), BG)).toBeGreaterThanOrEqual(
      4.5,
    );
  });

  it('proves the fixes were needed: the handoff values fail', () => {
    expect(contrast('#6f96a3', token('--panel'), BG)).toBeLessThan(4.5);
    expect(contrast('#ffffff', '#dc4a31', BG)).toBeLessThan(4.5);
    expect(contrast('#dc4a31', token('--panel'), BG)).toBeLessThan(4.5);
  });
});
