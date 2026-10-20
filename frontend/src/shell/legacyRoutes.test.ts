import { describe, expect, it } from 'vitest';
import routes from './legacy-routes.json';
import { LEGACY_ROUTES, legacyHref } from './legacyRoutes';

describe('legacyRoutes (SHELL-5)', () => {
  it('lists the Jinja modules the shell links to', () => {
    expect(Object.keys(LEGACY_ROUTES).sort()).toEqual(
      ['cards', 'collection', 'dashboard', 'decks', 'price', 'profile', 'sets'].sort(),
    );
  });

  it('is the JSON file the backend contract test checks against the Flask url_map', () => {
    expect(LEGACY_ROUTES).toEqual(routes);
    expect(legacyHref('collection')).toBe('/riftbound/collection');
    expect(legacyHref('dashboard')).toBe('/riftbound/');
  });

  it('only holds absolute /riftbound/ paths outside the SPA', () => {
    for (const url of Object.values(LEGACY_ROUTES)) {
      expect(url).toMatch(/^\/riftbound\//);
      expect(url.startsWith('/riftbound/app')).toBe(false);
      expect(url).not.toMatch(/[?#]|\/\//);
    }
  });

  it('has no duplicate URL', () => {
    const urls = Object.values(LEGACY_ROUTES);
    expect(new Set(urls).size).toBe(urls.length);
  });
});
