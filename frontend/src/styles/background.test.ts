// @vitest-environment node
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { SRC_DIR, readCss, rules } from '@/test/css';

const css = readCss(join(SRC_DIR, 'styles', 'background.css'));
const all = rules(css);

/** Merged declarations of the rules that list `selector`, outside or inside a media query. */
const declsOf = (selector: string, atRule?: string) =>
  Object.fromEntries(
    all
      .filter(
        (rule) =>
          rule.selectors.includes(selector) &&
          (atRule
            ? rule.atRules.some((a) => a.includes(atRule))
            : !rule.atRules.some((a) => a.startsWith('media'))),
      )
      .flatMap((rule) => rule.decls.map(({ prop, value }) => [prop, value])),
  );

describe('background.css image layer (DS-5)', () => {
  const layer = declsOf('html::before');

  it('is a fixed layer behind the content, inset so blurred edges stay off screen', () => {
    expect(layer).toMatchObject({
      position: 'fixed',
      inset: '-3%',
      'z-index': 'var(--z-bg)',
      'pointer-events': 'none',
    });
  });

  it('takes its filter and opacity from the variables bgVars() sets', () => {
    expect(layer.filter).toBe('var(--bg-image-filter)');
    expect(layer.opacity).toBe('var(--bg-image-opacity)');
  });

  it('covers the viewport with the 1920 px map by default', () => {
    expect(layer['background-image']).toContain('new_rift-1920.webp');
    expect(layer['background-size']).toBe('cover');
  });

  it('switches to the 1280 px map below 860 px with a width media query, not image-set (R5)', () => {
    const phone = declsOf('html::before', 'media (max-width: 859.98px)');
    expect(phone['background-image']).toContain('new_rift-1280.webp');
    expect(css).not.toContain('image-set');
  });

  it('uses the map turned 90 degrees on portrait screens, so phones are not zoomed in', () => {
    const portrait = declsOf('html::before', 'media (orientation: portrait)');
    expect(portrait['background-image']).toContain('new_rift-portrait.webp');
    // after the width query, so it wins on narrow portrait screens too
    expect(css.indexOf('orientation: portrait')).toBeGreaterThan(
      css.indexOf('max-width: 859.98px'),
    );
  });

  it('does not repeat the 1280 map outside the phone query', () => {
    const outside = all.filter(
      (rule) =>
        !rule.atRules.some((a) => a.startsWith('media')) &&
        rule.decls.some(({ value }) => value.includes('new_rift-1280')),
    );
    expect(outside).toEqual([]);
  });
});

describe('background.css overlay and off state', () => {
  it('paints the overlay gradients from --bg-overlay above the image', () => {
    expect(declsOf('html::after')).toMatchObject({
      position: 'fixed',
      inset: '0',
      'z-index': 'var(--z-bg)',
      background: 'var(--bg-overlay)',
      'pointer-events': 'none',
    });
  });

  it('hides the image layer when the background is off or not yet applied', () => {
    const hidden = all.find((rule) => rule.selectors.includes("html[data-bg='off']::before"));
    expect(hidden?.selectors).toContain('html:not([data-bg])::before');
    expect(Object.fromEntries(hidden?.decls.map((d) => [d.prop, d.value]) ?? [])).toEqual({
      display: 'none',
    });
  });

  it('keeps the solid page colour under both layers', () => {
    expect(declsOf('html')).toMatchObject({ background: 'var(--bg-0)' });
  });
});
