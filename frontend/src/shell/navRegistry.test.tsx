import { describe, expect, it } from 'vitest';
import { NAV, entryHref, isSpa, navEntries } from './navRegistry';

describe('navRegistry (F2-h S13)', () => {
  it('flips cards to spa at /cards', () => {
    const cards = NAV.find((entry) => entry.id === 'cards');
    expect(cards).toBeDefined();
    expect(cards && isSpa(cards)).toBe(true);
    expect(cards && entryHref(cards)).toBe('/cards');
  });

  it('lists cards in hub, top and bottom placements', () => {
    for (const placement of ['hub', 'top', 'bottom'] as const) {
      const ids = navEntries(placement, { isAdmin: false }).map((entry) => entry.id);
      expect(ids).toContain('cards');
    }
  });
});
