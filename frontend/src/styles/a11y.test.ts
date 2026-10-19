// @vitest-environment node
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { SRC_DIR, cssFiles, declsFor, readCss, rules } from '@/test/css';

const base = readCss(join(SRC_DIR, 'styles', 'base.css'));
const toMap = (decls: { prop: string; value: string }[]) =>
  Object.fromEntries(decls.map(({ prop, value }) => [prop, value]));

/** Rules that drop the outline without putting another focus indicator on the same selector. */
function bareOutlineRemoval(css: string) {
  return rules(css)
    .filter(
      (rule) => !rule.selectors.every((selector) => selector.includes(':not(:focus-visible)')),
    )
    .filter((rule) =>
      rule.decls.some(
        ({ prop, value }) =>
          (prop === 'outline' && /^(none|0)\b/.test(value)) ||
          (prop === 'outline-style' && value === 'none'),
      ),
    )
    .filter((rule) => !rule.decls.some(({ prop }) => ['box-shadow', 'border-color'].includes(prop)))
    .map((rule) => rule.selectors.join(', '));
}

/** font-size declarations below 11 px (px, or rem/em at 16 px). */
function tinyText(css: string) {
  return rules(css).flatMap((rule) =>
    rule.decls
      .filter(({ prop }) => prop === 'font-size' || prop === 'font')
      .flatMap(({ value }) => [...value.matchAll(/(?<![\w.-])(\d*\.?\d+)(px|rem|em)\b/g)])
      .map(([text, amount, unit]) => ({ text, px: Number(amount) * (unit === 'px' ? 1 : 16) }))
      .filter(({ px }) => px < 11)
      .map(({ text }) => `${rule.selectors.join(', ')} { font-size: ${text} }`),
  );
}

/** backdrop-filter rules without a solid background in the same rule. */
function backdropWithoutFallback(css: string) {
  return rules(css)
    .filter((rule) =>
      rule.decls.some(
        ({ prop }) => prop === 'backdrop-filter' || prop === '-webkit-backdrop-filter',
      ),
    )
    .filter(
      (rule) =>
        !rule.decls.some(({ prop }) => prop === 'background' || prop === 'background-color'),
    )
    .map((rule) => rule.selectors.join(', '));
}

describe('focus (DS-7)', () => {
  it('has a global :focus-visible ring that uses the accent', () => {
    expect(toMap(declsFor(base, ':focus-visible'))).toMatchObject({
      outline: '2px solid var(--accent)',
      'outline-offset': '2px',
    });
  });

  it('flags outline removal without a replacement, and accepts a replacement', () => {
    expect(bareOutlineRemoval('.input { outline: none; }')).toEqual(['.input']);
    expect(bareOutlineRemoval('.x { outline: 0 } .y { outline-style: none }')).toEqual([
      '.x',
      '.y',
    ]);
    expect(
      bareOutlineRemoval('.input { outline: none; } .input:focus { box-shadow: 0 0 0 2px red; }'),
    ).toEqual(['.input']);
    expect(bareOutlineRemoval('.input { outline: none; box-shadow: 0 0 0 2px red; }')).toEqual([]);
    expect(bareOutlineRemoval('.b:focus:not(:focus-visible) { outline: none; }')).toEqual([]);
  });

  it('removes no outline bare in any stylesheet', () => {
    const files = cssFiles();
    expect(files.length).toBeGreaterThan(4);
    expect(files.flatMap((file) => bareOutlineRemoval(readCss(file)))).toEqual([]);
  });
});

describe('reduced motion (DS-7)', () => {
  it('stops animation and transition inside prefers-reduced-motion: reduce', () => {
    const reduced = rules(base).filter((rule) =>
      rule.atRules.includes('media (prefers-reduced-motion: reduce)'),
    );
    expect(reduced.length).toBeGreaterThan(0);
    const decls = toMap(reduced.flatMap((rule) => rule.decls));
    expect(decls).toMatchObject({
      'animation-duration': '0.01ms',
      'animation-iteration-count': '1',
      'transition-duration': '0.01ms',
      'scroll-behavior': 'auto',
    });
    // postcss keeps !important out of the value; it must win over component rules
    expect(base).toMatch(/animation-duration:\s*0\.01ms\s*!important/);
    expect(base).toMatch(/transition-duration:\s*0\.01ms\s*!important/);
    expect(reduced[0].selectors).toEqual(['*', '*::before', '*::after']);
  });
});

describe('text size (DS-7)', () => {
  it('flags font sizes under 11 px', () => {
    expect(
      tinyText('.a { font-size: 10.5px } .b { font-size: 0.5rem } .c { font-size: 11px }'),
    ).toEqual(['.a { font-size: 10.5px }', '.b { font-size: 0.5rem }']);
  });

  it('has none in the stylesheets', () => {
    const files = cssFiles();
    expect(files.length).toBeGreaterThan(4);
    expect(files.flatMap((file) => tinyText(readCss(file)))).toEqual([]);
  });
});

describe('backdrop-filter fallback (DS-7)', () => {
  it('requires a solid background in the same rule', () => {
    expect(backdropWithoutFallback('.p { backdrop-filter: blur(12px) }')).toEqual(['.p']);
    expect(
      backdropWithoutFallback('.p { background: var(--panel-2); backdrop-filter: blur(12px) }'),
    ).toEqual([]);
  });

  it('holds for every stylesheet', () => {
    const files = cssFiles();
    expect(files.flatMap((file) => backdropWithoutFallback(readCss(file)))).toEqual([]);
  });
});

describe('safe areas and dynamic viewport (DS-7)', () => {
  it('exposes the four safe-area insets as tokens', () => {
    const root = toMap(declsFor(base, ':root'));
    for (const side of ['top', 'right', 'bottom', 'left']) {
      expect(root[`--safe-${side}`]).toBe(`env(safe-area-inset-${side}, 0px)`);
    }
  });

  it('sizes the page with 100dvh after a 100vh fallback', () => {
    const heights = declsFor(base, 'body')
      .filter(({ prop }) => prop === 'min-height')
      .map(({ value }) => value);
    expect(heights).toEqual(['100vh', '100dvh']);
  });
});
