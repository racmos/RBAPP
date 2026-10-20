import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Icon } from './Icon';
import { ICONS, type IconName } from './icons';

/** The 47 icons of the prototype (`eyeoff` is written `eye-off`) plus the shell's own (DS-8). */
const PROTOTYPE = [
  'dashboard',
  'cards',
  'collection',
  'decks',
  'sales',
  'stats',
  'search',
  'filter',
  'image',
  'export',
  'trash',
  'plus',
  'minus',
  'globe',
  'logout',
  'menu',
  'close',
  'edit',
  'tag',
  'check',
  'star',
  'grid',
  'list',
  'arrow',
  'coin',
  'account',
  'shield',
  'key',
  'sliders',
  'mail',
  'link',
  'device',
  'copy',
  'gift',
  'card',
  'refresh',
  'lock',
  'camera',
  'eye',
  'eye-off',
  'calendar',
  'pin',
  'users',
  'trophy',
  'clock',
  'ticket',
  'bookmark',
] as const;
const SHELL = [
  'more',
  'install',
  'warning',
  'offline',
  'settings',
  'info',
  'external-link',
  'check-circle',
] as const;

describe('icon set (DS-8)', () => {
  it('has the 47 prototype icons', () => {
    expect(PROTOTYPE).toHaveLength(47);
    for (const name of PROTOTYPE) expect(ICONS, name).toHaveProperty(name);
  });

  it('has the eight icons of the shell', () => {
    for (const name of SHELL) expect(ICONS, name).toHaveProperty(name);
  });

  it('has nothing else', () => {
    expect(Object.keys(ICONS).sort()).toEqual([...PROTOTYPE, ...SHELL].sort());
  });

  it.each([...PROTOTYPE, ...SHELL])('%s is plain path data on the 24 grid', (name) => {
    const paths = ICONS[name as IconName];
    expect(paths.length).toBeGreaterThan(0);
    for (const d of paths) {
      expect(d).toMatch(/^M[MmLlHhVvCcSsQqTtAaZz0-9 ,.-]+$/);
      const numbers = (d.match(/-?\d*\.?\d+/g) ?? []).map(Number);
      expect(numbers.every((n) => Number.isFinite(n))).toBe(true);
    }
  });

  it.each([...PROTOTYPE, ...SHELL])(
    '<Icon name="%s"> is hidden from assistive technology',
    (name) => {
      const { container } = render(<Icon name={name as IconName} />);
      const svg = container.querySelector('svg');
      expect(svg).toHaveAttribute('aria-hidden', 'true');
      expect(svg?.querySelectorAll('path').length).toBe(ICONS[name as IconName].length);
    },
  );

  it('no two icons share the same drawing', () => {
    const drawings = Object.values(ICONS).map((paths) => paths.join('|'));
    expect(new Set(drawings).size).toBe(drawings.length);
  });
});
