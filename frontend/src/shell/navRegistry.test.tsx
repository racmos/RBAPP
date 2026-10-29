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

  it('adds products as spa at /products right after collection (F14-e S1)', () => {
    const index = NAV.findIndex((entry) => entry.id === 'products');
    const products = NAV[index];
    expect(products).toEqual({
      id: 'products',
      icon: 'gift',
      status: 'spa',
      to: '/products',
      placements: ['top', 'hub', 'more'],
    });
    expect(NAV[index - 1].id).toBe('collection');
    expect(entryHref(products)).toBe('/products');
    for (const placement of ['top', 'hub', 'more'] as const) {
      expect(navEntries(placement, { isAdmin: false }).map((entry) => entry.id)).toContain(
        'products',
      );
    }
    expect(navEntries('bottom', { isAdmin: false }).map((entry) => entry.id)).not.toContain(
      'products',
    );
  });
});
