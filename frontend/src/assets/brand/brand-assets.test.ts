// @vitest-environment node
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { JSDOM } from 'jsdom';
import { describe, expect, it } from 'vitest';
import { parseColor, relativeLuminance } from '@/lib/contrast';

const frontend = fileURLToPath(new URL('../../../', import.meta.url));
const brandDir = fileURLToPath(new URL('./', import.meta.url));

function svgDocument(name: string) {
  const source = readFileSync(brandDir + name, 'utf8');
  const doc = new JSDOM(source, { contentType: 'image/svg+xml' }).window.document;
  return { source, doc, root: doc.documentElement };
}

/** Every colour an SVG paints with: fill and stop-color attributes and style declarations. */
function paintColors(doc: Document, source: string): string[] {
  const colours = new Set<string>();
  doc.querySelectorAll('[fill], [stop-color]').forEach((node) => {
    for (const attr of ['fill', 'stop-color']) {
      const value = node.getAttribute(attr);
      if (value && !value.startsWith('url(') && value !== 'none') colours.add(value);
    }
  });
  for (const match of source.matchAll(/(?:fill|stop-color)\s*:\s*(#[\da-f]{3,8})/gi)) {
    colours.add(match[1]);
  }
  return [...colours];
}

describe('originals (DS-9 "Assets exist")', () => {
  it.each(['rift-manager-mark.webp', 'rift-manager-wordmark.webp'])(
    'keeps %s as a source',
    (file) => {
      expect(existsSync(frontend + 'assets-src/brand/' + file)).toBe(true);
    },
  );

  it('has the README with provenance and the regeneration command', () => {
    const readme = readFileSync(frontend + 'assets-src/brand/README.md', 'utf8');
    expect(readme).toContain('npm run brand:trace');
    expect(readme).toMatch(/never shipped/i);
  });
});

describe.each(['mark.svg', 'wordmark.svg'])('%s (DS-9)', (name) => {
  it('exists and parses as SVG', () => {
    expect(existsSync(brandDir + name)).toBe(true);
    const { root } = svgDocument(name);
    expect(root.localName).toBe('svg');
    expect(root.querySelector('parsererror')).toBeNull();
  });

  it('has a viewBox and is made of vector paths only', () => {
    const { source, root } = svgDocument(name);
    expect(root.getAttribute('viewBox')).toMatch(/^-?[\d.]+ -?[\d.]+ [\d.]+ [\d.]+$/);
    expect(root.querySelectorAll('path').length).toBeGreaterThan(0);
    expect(source).not.toMatch(/<image\b/i);
    expect(source).not.toMatch(/<script\b/i);
    expect(source).not.toMatch(/base64/i);
    expect(source).not.toMatch(/data:/i);
  });

  it('paints with brand gradients and no near-white fill (a white halo proxy)', () => {
    const { source, doc } = svgDocument(name);
    expect(doc.querySelectorAll('linearGradient').length).toBe(1);
    const colours = paintColors(doc, source);
    expect(colours.length).toBeGreaterThanOrEqual(2);
    for (const colour of colours) {
      expect(relativeLuminance(parseColor(colour))).toBeLessThanOrEqual(0.95);
    }
  });
});

describe('viewBox crop', () => {
  const size = (name: string) => {
    const [, , width, height] = svgDocument(name)
      .root.getAttribute('viewBox')!
      .split(' ')
      .map(Number);
    return { width, height };
  };

  it('crops the wordmark to its glyphs: wider than 2:1', () => {
    const { width, height } = size('wordmark.svg');
    expect(width / height).toBeGreaterThan(2);
  });

  it('crops the mark close to square', () => {
    const { width, height } = size('mark.svg');
    expect(width / height).toBeGreaterThan(0.8);
    expect(width / height).toBeLessThan(1.25);
  });
});
