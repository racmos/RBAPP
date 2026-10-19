// @vitest-environment node
import { mkdirSync, mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { cssFiles, declsFor, mediaWidths, readCss, rules } from './css';

const SAMPLE = `
:root { --a: 1px; --b: 2px; }
.btn, .link { color: red; }
.btn { color: blue; padding: 4px }
@layer components {
  @media (min-width: 860px) and (max-width: 1239.98px) { .btn { margin: 0 } }
}
@media (max-width: 680px) { .link { display: none } }
@media (prefers-reduced-motion: reduce) { .btn { transition: none } }
`;

describe('mediaWidths', () => {
  it('returns every min/max width in document order, ignoring other features', () => {
    expect(mediaWidths(SAMPLE)).toEqual([860, 1239.98, 680]);
  });

  it('returns an empty list for a stylesheet without media queries', () => {
    expect(mediaWidths('.a { color: red }')).toEqual([]);
  });
});

describe('declsFor', () => {
  it('collects declarations for a selector, including grouped and nested rules, in order', () => {
    expect(declsFor(SAMPLE, '.btn')).toEqual([
      { prop: 'color', value: 'red' },
      { prop: 'color', value: 'blue' },
      { prop: 'padding', value: '4px' },
      { prop: 'margin', value: '0' },
      { prop: 'transition', value: 'none' },
    ]);
  });

  it('matches whole selectors only and reads custom properties', () => {
    expect(declsFor(SAMPLE, ':root')).toEqual([
      { prop: '--a', value: '1px' },
      { prop: '--b', value: '2px' },
    ]);
    expect(declsFor(SAMPLE, '.bt')).toEqual([]);
  });
});

describe('rules', () => {
  it('reports the at-rule context of each rule', () => {
    const nested = rules(SAMPLE).find((rule) => rule.decls.some((d) => d.prop === 'margin'));
    expect(nested?.atRules).toEqual([
      'layer components',
      'media (min-width: 860px) and (max-width: 1239.98px)',
    ]);
    expect(nested?.selectors).toEqual(['.btn']);
  });
});

describe('cssFiles / readCss', () => {
  it('finds every .css file below a directory, recursively and sorted', () => {
    const dir = mkdtempSync(join(tmpdir(), 'css-'));
    mkdirSync(join(dir, 'a'));
    writeFileSync(join(dir, 'z.css'), '.z{}');
    writeFileSync(join(dir, 'a', 'b.module.css'), '.b{color:red}');
    writeFileSync(join(dir, 'a', 'note.txt'), 'x');
    const files = cssFiles(dir);
    expect(files).toEqual([join(dir, 'a', 'b.module.css'), join(dir, 'z.css')]);
    expect(readCss(files[0])).toBe('.b{color:red}');
  });
});
