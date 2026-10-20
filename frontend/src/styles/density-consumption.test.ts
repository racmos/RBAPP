// @vitest-environment node
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { SRC_DIR, declsFor, readCss } from '@/test/css';

const read = (file: string) => readCss(join(SRC_DIR, file));
const value = (file: string, selector: string, prop: string): string | undefined =>
  declsFor(read(file), selector).find((decl) => decl.prop === prop)?.value;

/** DS-3: the density tokens must reach the components, or switching density changes nothing. */
describe('density consumption (DS-3)', () => {
  describe('rows, lists and menus use var(--row-h)', () => {
    it.each([
      ['components/ui/SettingsCard.module.css', '.row'],
      ['shell/MoreSheet.module.css', '.item'],
      ['shell/HomeHub.module.css', '.card'],
    ])('%s %s', (file, selector) => {
      expect(value(file, selector, 'min-height')).toBe('var(--row-h)');
    });
  });

  describe('small controls use var(--radius-sm)', () => {
    it.each([
      ['components/ui/Select.module.css', '.select'],
      ['components/ui/SegmentedControl.module.css', '.group'],
      ['components/ui/Badge.module.css', '.badge'],
      ['components/ui/Button.module.css', '.sm'],
      ['i18n/LanguageToggle.module.css', '.group'],
      ['components/ui/Modal.module.css', '.close'],
    ])('%s %s', (file, selector) => {
      expect(value(file, selector, 'border-radius')).toBe('var(--radius-sm)');
    });
  });

  describe('panels use the density radius and padding', () => {
    it.each([
      ['components/ui/Panel.module.css', '.panel'],
      ['components/ui/SettingsCard.module.css', '.card'],
    ])('%s %s', (file, selector) => {
      expect(value(file, selector, 'border-radius')).toBe('var(--radius)');
      expect(value(file, selector, 'padding')).toBe('var(--pad)');
    });
  });
});
