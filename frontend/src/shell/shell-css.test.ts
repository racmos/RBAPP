// @vitest-environment node
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { SRC_DIR, declsFor, readCss, rules } from '@/test/css';

const css = (file: string) => readCss(join(SRC_DIR, 'shell', file));
const find = (file: string, selector: string, prop: string) =>
  declsFor(css(file), selector).find((decl) => decl.prop === prop)?.value;

/** The values of `prop` for `selector` inside the rules whose at-rules include `media`. */
const inMedia = (file: string, selector: string, prop: string, media: string) =>
  rules(css(file))
    .filter((rule) => rule.selectors.includes(selector) && rule.atRules.includes(`media ${media}`))
    .flatMap((rule) => rule.decls)
    .find((decl) => decl.prop === prop)?.value;

describe('shell CSS (SHELL-1..3)', () => {
  describe('topbar', () => {
    it('is sticky and stays under the dialogs', () => {
      expect(find('Topbar.module.css', '.topbar', 'position')).toBe('sticky');
      expect(find('Topbar.module.css', '.topbar', 'top')).toBe('0');
      expect(find('Topbar.module.css', '.topbar', 'z-index')).toBe('var(--z-topbar)');
    });

    it('is 56 px high on a phone and 64 px from sm', () => {
      expect(find('Topbar.module.css', '.bar', 'height')).toBe('56px');
      expect(inMedia('Topbar.module.css', '.bar', 'height', '(min-width: 680px)')).toBe('64px');
    });

    it('has a solid background wherever it blurs (DS-7)', () => {
      expect(find('Topbar.module.css', '.topbar', 'background')).toBeTruthy();
    });
  });

  describe('content width', () => {
    it('is capped at --maxw and --maxw-wide from 2xl', () => {
      expect(find('AppShell.module.css', '.content', 'max-width')).toBe('var(--maxw)');
      expect(inMedia('AppShell.module.css', '.content', 'max-width', '(min-width: 1600px)')).toBe(
        'var(--maxw-wide)',
      );
    });
  });

  describe('bottom navigation', () => {
    it('has labels of at least 11 px', () => {
      const size = find('BottomNav.module.css', '.label', 'font-size');
      expect(size).toMatch(/^\d+(\.\d+)?px$/);
      expect(parseFloat(size!)).toBeGreaterThanOrEqual(11);
    });

    it('respects the bottom safe-area inset and sits above the content', () => {
      expect(find('BottomNav.module.css', '.nav', 'padding-bottom')).toContain(
        'var(--safe-bottom)',
      );
      expect(find('BottomNav.module.css', '.nav', 'z-index')).toBe('var(--z-botnav)');
      expect(find('BottomNav.module.css', '.nav', 'position')).toBe('fixed');
    });

    it('has targets of at least 24 px', () => {
      const height = find('BottomNav.module.css', '.item', 'min-height');
      expect(parseFloat(height!)).toBeGreaterThanOrEqual(24);
    });
  });

  describe('bottom padding', () => {
    it('is applied only to main with the botnav marker, inside the phone rule', () => {
      expect(find('AppShell.module.css', '.main', 'padding-bottom')).toBeUndefined();
      const phone = '(max-width: 859.98px)';
      const padding = inMedia(
        'AppShell.module.css',
        ".main[data-botnav='true']",
        'padding-bottom',
        phone,
      );
      expect(padding).toContain('var(--safe-bottom)');
      expect(find('AppShell.module.css', ".main[data-botnav='true']", 'padding-bottom')).toBe(
        padding,
      );
    });
  });
});
