import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { SRC_DIR, readCss, rules } from '@/test/css';

const css = readCss(join(SRC_DIR, 'shell/AppShell.module.css'));
/** `max-width` of `selector` inside `@media <media>`, or outside any `@media` when `null`. */
const maxWidth = (selector: string, media: string | null) =>
  rules(css)
    .filter(
      (rule) =>
        rule.selectors.includes(selector) &&
        (media === null
          ? !rule.atRules.some((at) => at.startsWith('media'))
          : rule.atRules.includes(media)),
    )
    .flatMap((rule) => rule.decls)
    .findLast((decl) => decl.prop === 'max-width')?.value;

describe('AppShell content width', () => {
  it('caps the content at --maxw, at --maxw-wide from 1600 px', () => {
    expect(maxWidth('.content', null)).toBe('var(--maxw)');
    expect(maxWidth('.content', 'media (min-width: 1600px)')).toBe('var(--maxw-wide)');
  });

  it('a page marked data-width="wide" gets the wide cap from 1240 px (owner feedback S22, S24 q)', () => {
    expect(maxWidth(".content:has([data-width='wide'])", 'media (min-width: 1240px)')).toBe(
      'var(--maxw-wide)',
    );
  });
});

describe('Topbar width follows the content', () => {
  it('is as wide as a wide page from 1240 px, so their edges line up', () => {
    const topbar = readCss(join(SRC_DIR, 'shell/Topbar.module.css'));
    const rule = rules(topbar).find(
      (r) =>
        r.selectors.includes(":global(body:has([data-width='wide'])) .bar") &&
        r.atRules.includes('media (min-width: 1240px)'),
    );
    expect(rule?.decls).toContainEqual({ prop: 'max-width', value: 'var(--maxw-wide)' });
  });
});
