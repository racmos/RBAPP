import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import { LEGACY_ROUTES } from './legacyRoutes';
import { NavItem } from './NavItem';
import { NAV, isLegacy, isSpa, navEntries, type NavEntry } from './navRegistry';

const ids = (entries: readonly NavEntry[]) => entries.map((entry) => entry.id);
const member = { isAdmin: false };
const admin = { isAdmin: true };

describe('navigation registry (SHELL-5, R3)', () => {
  it('every entry has a status of spa, legacy or planned', () => {
    expect(NAV.length).toBeGreaterThan(0);
    for (const entry of NAV) expect(['spa', 'legacy', 'planned']).toContain(entry.status);
  });

  it('spa entries have a router path and legacy ones a key of legacyRoutes', () => {
    const spa = NAV.filter(isSpa);
    const legacy = NAV.filter(isLegacy);
    expect(spa.length).toBeGreaterThan(0);
    expect(legacy.length).toBeGreaterThan(0);
    for (const entry of spa) expect(entry.to).toMatch(/^\//);
    for (const entry of legacy) expect(Object.keys(LEGACY_ROUTES)).toContain(entry.legacy);
  });

  it('ids are unique', () => {
    expect(new Set(ids(NAV)).size).toBe(NAV.length);
  });

  describe('bottom navigation set (R3)', () => {
    it('holds Inicio, Cartas, Colección and Mazos; "Más" is added by the component', () => {
      expect(ids(navEntries('bottom', member))).toEqual(['home', 'cards', 'collection', 'decks']);
    });
  });

  describe('top navigation set', () => {
    it('hides admin-only entries from a member and shows them to an admin', () => {
      expect(ids(navEntries('top', member))).not.toContain('price');
      expect(ids(navEntries('top', admin))).toContain('price');
    });

    it('starts with the home hub', () => {
      expect(ids(navEntries('top', member))[0]).toBe('home');
    });
  });

  describe('planned entries (SHELL-5 "Planned hidden")', () => {
    const fixture: NavEntry[] = [
      { id: 'home', icon: 'grid', status: 'spa', to: '/', placements: ['top'] },
      { id: 'events', icon: 'calendar', status: 'planned', placements: ['top', 'hub'] },
    ];

    it('are never returned, whatever their placement', () => {
      expect(ids(navEntries('top', member, fixture))).toEqual(['home']);
      expect(ids(navEntries('hub', member, fixture))).toEqual([]);
    });

    it('the real registry keeps events, sales and stats planned', () => {
      const planned = NAV.filter((entry) => entry.status === 'planned').map((entry) => entry.id);
      expect(planned).toEqual(expect.arrayContaining(['events', 'sales', 'stats']));
      for (const id of planned) {
        expect(ids(navEntries('top', admin))).not.toContain(id);
        expect(ids(navEntries('hub', admin))).not.toContain(id);
      }
    });
  });

  describe('hub set (SHELL-6)', () => {
    it('has six launchers for a member and seven with Price for an admin', () => {
      expect(ids(navEntries('hub', member))).toEqual([
        'dashboard',
        'sets',
        'cards',
        'collection',
        'decks',
        'profile',
      ]);
      expect(ids(navEntries('hub', admin))).toEqual([
        'dashboard',
        'sets',
        'cards',
        'collection',
        'decks',
        'profile',
        'price',
      ]);
    });
  });

  describe('more-sheet set (SHELL-4)', () => {
    it('has Admin only for admins', () => {
      expect(ids(navEntries('more', member))).not.toContain('admin');
      expect(ids(navEntries('more', admin))).toContain('admin');
    });

    it('has the Interface page and the classic modules', () => {
      expect(ids(navEntries('more', member))).toEqual([
        'interface',
        'dashboard',
        'sets',
        'cards',
        'collection',
        'decks',
        'profile',
      ]);
    });
  });
});

describe('NavItem (SHELL-5)', () => {
  const entry = (id: string) => NAV.find((candidate) => candidate.id === id)!;

  /** Records whether the click was already handled (default prevented) by the time it reaches `document`. */
  const watchClick = () => {
    const seen: { prevented: boolean | null } = { prevented: null };
    document.addEventListener(
      'click',
      (event) => {
        seen.prevented = event.defaultPrevented;
        event.preventDefault(); // keep jsdom from "navigating"
      },
      { once: true },
    );
    return seen;
  };

  it('renders a legacy entry as a plain anchor with the real URL, not a router link', async () => {
    render(
      <MemoryRouter basename="/riftbound/app" initialEntries={['/riftbound/app/']}>
        <NavItem entry={entry('collection')}>Colección</NavItem>
      </MemoryRouter>,
    );
    const link = screen.getByRole('link', { name: 'Colección' });
    expect(link).toHaveAttribute('href', '/riftbound/collection');
    expect(link).not.toHaveAttribute('aria-current');
    const seen = watchClick();
    await userEvent.click(link);
    expect(seen.prevented).toBe(false); // the browser navigates; the router does not intercept
  });

  it('renders a spa entry as a router link under the basename', async () => {
    render(
      <MemoryRouter basename="/riftbound/app" initialEntries={['/riftbound/app/']}>
        <NavItem entry={entry('interface')}>Interfaz</NavItem>
      </MemoryRouter>,
    );
    const link = screen.getByRole('link', { name: 'Interfaz' });
    expect(link).toHaveAttribute('href', '/riftbound/app/account/interface');
    const seen = watchClick();
    await userEvent.click(link);
    expect(seen.prevented).toBe(true); // handled client side
  });

  it('marks the current spa entry with aria-current="page"', () => {
    render(
      <MemoryRouter basename="/riftbound/app" initialEntries={['/riftbound/app/account/interface']}>
        <NavItem entry={entry('interface')}>Interfaz</NavItem>
        <NavItem entry={entry('home')}>Inicio</NavItem>
      </MemoryRouter>,
    );
    expect(screen.getByRole('link', { name: 'Interfaz' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('link', { name: 'Inicio' })).not.toHaveAttribute('aria-current');
  });

  it('home matches only the exact root', () => {
    render(
      <MemoryRouter basename="/riftbound/app" initialEntries={['/riftbound/app/']}>
        <NavItem entry={entry('home')}>Inicio</NavItem>
      </MemoryRouter>,
    );
    expect(screen.getByRole('link', { name: 'Inicio' })).toHaveAttribute('aria-current', 'page');
  });
});
