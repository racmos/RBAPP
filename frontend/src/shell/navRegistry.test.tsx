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

  it('adds locations as spa at /locations right after products (F16-c)', () => {
    const index = NAV.findIndex((entry) => entry.id === 'locations');
    const locations = NAV[index];
    expect(locations).toEqual({
      id: 'locations',
      icon: 'pin',
      status: 'spa',
      to: '/locations',
      placements: ['top', 'hub', 'more'],
    });
    expect(NAV[index - 1].id).toBe('products');
    expect(entryHref(locations)).toBe('/locations');
    for (const placement of ['top', 'hub', 'more'] as const) {
      expect(navEntries(placement, { isAdmin: false }).map((entry) => entry.id)).toContain(
        'locations',
      );
    }
    expect(navEntries('bottom', { isAdmin: false }).map((entry) => entry.id)).not.toContain(
      'locations',
    );
  });

  it('flips decks to spa at /decks (F5-h)', () => {
    const decks = NAV.find((entry) => entry.id === 'decks');
    expect(decks).toEqual({
      id: 'decks',
      icon: 'decks',
      status: 'spa',
      to: '/decks',
      placements: ['top', 'bottom', 'hub', 'more'],
    });
    expect(decks && entryHref(decks)).toBe('/decks');
    for (const placement of ['top', 'bottom', 'hub', 'more'] as const) {
      expect(navEntries(placement, { isAdmin: false }).map((entry) => entry.id)).toContain('decks');
    }
  });

  it('flips profile to spa at /account/profile', () => {
    const profile = NAV.find((entry) => entry.id === 'profile');
    expect(profile).toEqual({
      id: 'profile',
      icon: 'account',
      status: 'spa',
      to: '/account/profile',
      placements: ['hub', 'more'],
    });
    expect(profile && entryHref(profile)).toBe('/account/profile');
    for (const placement of ['hub', 'more'] as const) {
      expect(navEntries(placement, { isAdmin: false }).map((entry) => entry.id)).toContain(
        'profile',
      );
    }
  });
});

describe('navRegistry without the old web (Jinja retirement 2/3)', () => {
  it('every entry is an app route or planned: none links to a Jinja page', () => {
    for (const entry of NAV) expect(['spa', 'planned']).toContain(entry.status);
    const ids = NAV.map((entry) => entry.id as string);
    for (const gone of ['dashboard', 'sets', 'price']) expect(ids).not.toContain(gone);
  });

  it.each([
    ['top', false, ['home', 'cards', 'collection', 'products', 'locations', 'decks']],
    ['top', true, ['home', 'cards', 'collection', 'products', 'locations', 'decks']],
    ['bottom', false, ['home', 'cards', 'collection', 'decks']],
    ['hub', false, ['cards', 'collection', 'products', 'locations', 'decks', 'profile']],
    ['hub', true, ['cards', 'collection', 'products', 'locations', 'decks', 'profile']],
    [
      'more',
      false,
      ['interface', 'cards', 'collection', 'products', 'locations', 'decks', 'profile'],
    ],
    [
      'more',
      true,
      ['interface', 'cards', 'collection', 'products', 'locations', 'decks', 'profile', 'admin'],
    ],
  ] as const)('%s (admin %s) shows %j', (placement, isAdmin, expected) => {
    expect(navEntries(placement, { isAdmin }).map((entry) => entry.id)).toEqual(expected);
  });
});
