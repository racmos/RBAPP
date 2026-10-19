// @vitest-environment node
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { SRC_DIR, cssFiles, declsFor, readCss, rules } from '@/test/css';

const tokens = readCss(join(SRC_DIR, 'styles', 'tokens.css'));
const toMap = (decls: { prop: string; value: string }[]) =>
  Object.fromEntries(decls.map(({ prop, value }) => [prop, value]));

const ACCENT_TOKENS = ['--accent', '--accent-bright', '--accent-dim', '--accent-ink'];

describe('[data-accent] (DS-2)', () => {
  it.each([
    ['orange', '#160d03'],
    ['cyan', '#04222b'],
  ])('%s defines the four accent tokens with ink %s', (name, ink) => {
    const block = toMap(declsFor(tokens, `[data-accent='${name}']`));
    expect(Object.keys(block).sort()).toEqual([...ACCENT_TOKENS].sort());
    expect(block['--accent-ink']).toBe(ink);
  });

  it('points orange at the orange palette and cyan at the cyan palette', () => {
    expect(toMap(declsFor(tokens, "[data-accent='orange']"))).toMatchObject({
      '--accent': 'var(--orange)',
      '--accent-bright': 'var(--orange-bright)',
    });
    expect(toMap(declsFor(tokens, "[data-accent='cyan']"))).toMatchObject({
      '--accent': 'var(--cyan)',
      '--accent-bright': 'var(--cyan-bright)',
      '--accent-dim': 'var(--cyan-dim)',
    });
  });

  it('derives the tints from --accent with color-mix', () => {
    const root = toMap(declsFor(tokens, ':root'));
    expect(root['--accent-soft']).toBe('color-mix(in srgb, var(--accent) 16%, transparent)');
    expect(root['--accent-ring']).toBe('color-mix(in srgb, var(--accent) 45%, transparent)');
    expect(root['--accent-glow']).toBe('color-mix(in srgb, var(--accent) 50%, transparent)');
  });
});

/** Declarations that hard-code the info cyan, except the definition of --cyan itself. */
function hardCodedCyan(css: string) {
  return rules(css).flatMap((rule) =>
    rule.decls
      .filter(
        ({ prop, value }) => prop !== '--cyan' && /46\s*,\s*198\s*,\s*230|#2ec6e6/i.test(value),
      )
      .map(({ prop }) => `${rule.selectors.join(', ')} { ${prop} }`),
  );
}

describe('no hard-coded interactive cyan (DS-2)', () => {
  it('flags rgba(46,198,230) and #2ec6e6 in any rule but the --cyan definition', () => {
    const css = `
      :root { --cyan: #2ec6e6; }
      .btn:hover { box-shadow: 0 0 0 3px rgba(46, 198, 230, 0.14); }
      .link { color: #2EC6E6; }
      .ok { color: var(--accent); }
    `;
    expect(hardCodedCyan(css)).toEqual(['.btn:hover { box-shadow }', '.link { color }']);
  });

  it('finds none in the real stylesheets', () => {
    const files = cssFiles();
    expect(files.length).toBeGreaterThan(4);
    const offenders = files.flatMap((file) =>
      hardCodedCyan(readCss(file)).map((o) => `${file}: ${o}`),
    );
    expect(offenders).toEqual([]);
  });
});
