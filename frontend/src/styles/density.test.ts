// @vitest-environment node
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { SRC_DIR, declsFor, readCss, rules } from '@/test/css';

const tokens = readCss(join(SRC_DIR, 'styles', 'tokens.css'));
const toMap = (decls: { prop: string; value: string }[]) =>
  Object.fromEntries(decls.map(({ prop, value }) => [prop, value]));

/** Token values on <html> for a density: :root first, then the attribute block on top. */
function effective(density?: 'compact' | 'comfy') {
  const base = toMap(declsFor(tokens, ':root'));
  const override = density ? toMap(declsFor(tokens, `[data-density='${density}']`)) : {};
  const pick = (name: string) => override[name] ?? base[name];
  return {
    gap: pick('--gap'),
    pad: pick('--pad'),
    rowH: pick('--row-h'),
    radius: pick('--radius'),
    radiusSm: pick('--radius-sm'),
  };
}

describe('[data-density] (DS-3)', () => {
  it('compact: gap 13, pad 13, row 44, radius 11', () => {
    expect(effective('compact')).toEqual({
      gap: '13px',
      pad: '13px',
      rowH: '44px',
      radius: '11px',
      radiusSm: '9px',
    });
  });

  it('comfy follows handoff 1.2: gap 26, pad 24, row 62, radius 14', () => {
    expect(effective('comfy')).toEqual({
      gap: '26px',
      pad: '24px',
      rowH: '62px',
      radius: '14px',
      radiusSm: '9px',
    });
  });

  it('regular (no attribute): gap 20, pad 18, row 54, radius 14', () => {
    expect(effective()).toEqual({
      gap: '20px',
      pad: '18px',
      rowH: '54px',
      radius: '14px',
      radiusSm: '9px',
    });
  });

  it('has no rule for data-density regular: regular is the absence of the attribute', () => {
    const selectors = rules(tokens).flatMap((rule) => rule.selectors);
    expect(selectors.filter((selector) => selector.includes('data-density'))).toEqual([
      "[data-density='compact']",
      "[data-density='comfy']",
    ]);
  });
});
