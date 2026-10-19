// @vitest-environment node
import { describe, expect, it } from 'vitest';
import { BREAKPOINTS } from '@/lib/breakpoints';
import { allowedMediaWidths, cssFiles, readCss, scanMediaWidths } from '@/test/css';

describe('allowedMediaWidths (DS-4)', () => {
  it('is the breakpoint set plus each value minus 0.02', () => {
    expect([...allowedMediaWidths(Object.values(BREAKPOINTS))].sort((a, b) => a - b)).toEqual([
      679.98, 680, 859.98, 860, 959.98, 960, 1239.98, 1240, 1599.98, 1600,
    ]);
  });
});

describe('scanMediaWidths', () => {
  const allowed = allowedMediaWidths(Object.values(BREAKPOINTS));

  it('accepts widths from the scale', () => {
    const css =
      '@media (min-width: 860px) { a { b: c } } @media (max-width: 859.98px) { a { b: c } }';
    expect(scanMediaWidths([{ file: 'ok.css', css }], allowed)).toEqual([]);
  });

  it('fails naming the file and value for a stray width', () => {
    const css = '@media (max-width: 920px) { a { b: c } }';
    expect(scanMediaWidths([{ file: 'src/x.css', css }], allowed)).toEqual([
      { file: 'src/x.css', value: 920 },
    ]);
  });

  it('reports every offender across files and keeps valid ones out', () => {
    const files = [
      { file: 'a.css', css: '@media (min-width: 1080px) { a { b: c } }' },
      { file: 'b.css', css: '@media (min-width: 960px) { a { b: c } }' },
      { file: 'c.css', css: '@media (min-width: 420px) and (max-width: 1240px) { a { b: c } }' },
    ];
    expect(scanMediaWidths(files, allowed)).toEqual([
      { file: 'a.css', value: 1080 },
      { file: 'c.css', value: 420 },
    ]);
  });
});

describe('the real tree', () => {
  it('uses only scale widths in every src/**/*.css', () => {
    const files = cssFiles().map((file) => ({ file, css: readCss(file) }));
    expect(files.length).toBeGreaterThan(4);
    expect(scanMediaWidths(files, allowedMediaWidths(Object.values(BREAKPOINTS)))).toEqual([]);
  });
});
