// @vitest-environment node
import { relative } from 'node:path';
import { describe, expect, it } from 'vitest';
import { SRC_DIR, cssFiles, readCss, unlayeredRules } from '@/test/css';

describe('unlayeredRules', () => {
  it('reports rules outside the component layer, at the top level or in a media query', () => {
    const css = `
      @layer components { .a { color: red } @media (min-width: 860px) { .b { color: red } } }
      .c { color: red }
      @media (min-width: 860px) { .d { color: red } }
      @layer utilities { .e { color: red } }
    `;
    expect(unlayeredRules(css, 'components')).toEqual(['.c', '.d', '.e']);
  });

  it('accepts a file whose rules are all inside the layer, keyframes included', () => {
    const css =
      '@layer components { .a { color: red } @keyframes k { from { top: 0 } to { top: 1px } } }';
    expect(unlayeredRules(css, 'components')).toEqual([]);
  });
});

describe('CSS Modules (D15)', () => {
  const modules = cssFiles().filter((file) => file.endsWith('.module.css'));

  it('finds the module stylesheets', () => {
    expect(modules.map((file) => relative(SRC_DIR, file))).toContain(
      'components/ui/Brand.module.css',
    );
  });

  it.each(modules.map((file) => [relative(SRC_DIR, file), file]))(
    '%s wraps all its rules in @layer components',
    (_name, file) => {
      expect(unlayeredRules(readCss(file), 'components')).toEqual([]);
    },
  );
});
