// @vitest-environment node
import { join } from 'node:path';
import postcss from 'postcss';
import { describe, expect, it } from 'vitest';
import { SRC_DIR, readCss } from '@/test/css';

const read = (file: string) => readCss(join(SRC_DIR, 'styles', file));

const faces: Record<string, string>[] = [];
postcss.parse(read('fonts.css')).walkAtRules('font-face', (face) => {
  const decls: Record<string, string> = {};
  face.walkDecls((decl) => {
    decls[decl.prop] = decl.value;
  });
  faces.push(decls);
});

describe('fonts.css (DS-6)', () => {
  it('declares a latin and a latin-ext face for each of the two families', () => {
    const summary = faces.map((face) => [
      face['font-family'],
      face.src.match(/(latin(?:-ext)?)-wght/)?.[1],
    ]);
    expect(summary).toEqual([
      ["'Manrope Variable'", 'latin-ext'],
      ["'Manrope Variable'", 'latin'],
      ["'Space Grotesk Variable'", 'latin-ext'],
      ["'Space Grotesk Variable'", 'latin'],
    ]);
  });

  it('swaps while loading and uses variable weight ranges', () => {
    expect(faces.every((face) => face['font-display'] === 'swap')).toBe(true);
    expect(faces.map((face) => face['font-weight'])).toEqual([
      '200 800',
      '200 800',
      '300 700',
      '300 700',
    ]);
  });

  it('loads the self-hosted woff2 files from the fontsource packages', () => {
    for (const face of faces) {
      expect(face.src).toMatch(
        /^url\('?@fontsource-variable\/[\w-]+\/files\/[\w-]+\.woff2'?\)\s+format\('woff2-variations'\)$/,
      );
    }
  });

  it('does not reference any third-party font host', () => {
    expect(read('fonts.css')).not.toMatch(/fonts\.(googleapis|gstatic)\.com/);
  });
});

describe('index.css layer order (D15)', () => {
  it('declares the layers first, in order', () => {
    expect(read('index.css')).toMatch(/@layer reset, tokens, base, layout, components, utilities;/);
  });

  it('imports the six style files', () => {
    const imports = [...read('index.css').matchAll(/@import '([^']+)'/g)].map((match) => match[1]);
    expect(imports).toEqual([
      './reset.css',
      './fonts.css',
      './tokens.css',
      './base.css',
      './background.css',
      './utilities.css',
    ]);
  });
});
