import type { IconName } from '@/components/ui/icons';
import { legacyHref, type LegacyKey } from './legacyRoutes';

/**
 * One registry feeds the topbar, the bottom navigation, the "Más" sheet and the home hub
 * (SHELL-5). Each entry is `spa` (a router link), `legacy` (a plain link to a Jinja page) or
 * `planned` (not rendered anywhere). When a phase ports a module, flip its entry to `spa`.
 */
export type NavStatus = 'spa' | 'legacy' | 'planned';
export type NavPlacement = 'top' | 'bottom' | 'hub' | 'more';
export type NavId =
  | 'home'
  | 'dashboard'
  | 'sets'
  | 'cards'
  | 'collection'
  | 'decks'
  | 'profile'
  | 'price'
  | 'admin'
  | 'interface'
  | 'events'
  | 'sales'
  | 'stats';

type Common = {
  id: NavId;
  icon: IconName;
  placements: readonly NavPlacement[];
  /** Not rendered for non-admins (UX only: the server still enforces access). */
  adminOnly?: boolean;
};

export type NavEntry = Common &
  (
    | { status: 'spa'; /** Router path, without the basename. */ to: string }
    | { status: 'legacy'; legacy: LegacyKey }
    | { status: 'planned' }
  );

export const isSpa = (entry: NavEntry): entry is Extract<NavEntry, { status: 'spa' }> =>
  entry.status === 'spa';
export const isLegacy = (entry: NavEntry): entry is Extract<NavEntry, { status: 'legacy' }> =>
  entry.status === 'legacy';

/** Order here is the order on screen. */
export const NAV: readonly NavEntry[] = [
  { id: 'home', icon: 'grid', status: 'spa', to: '/', placements: ['top', 'bottom'] },
  {
    id: 'interface',
    icon: 'sliders',
    status: 'spa',
    to: '/account/interface',
    placements: ['more'],
  },
  {
    id: 'dashboard',
    icon: 'dashboard',
    status: 'legacy',
    legacy: 'dashboard',
    placements: ['top', 'hub', 'more'],
  },
  {
    id: 'sets',
    icon: 'bookmark',
    status: 'legacy',
    legacy: 'sets',
    placements: ['top', 'hub', 'more'],
  },
  {
    id: 'cards',
    icon: 'cards',
    status: 'legacy',
    legacy: 'cards',
    placements: ['top', 'bottom', 'hub', 'more'],
  },
  {
    id: 'collection',
    icon: 'collection',
    status: 'legacy',
    legacy: 'collection',
    placements: ['top', 'bottom', 'hub', 'more'],
  },
  {
    id: 'decks',
    icon: 'decks',
    status: 'legacy',
    legacy: 'decks',
    placements: ['top', 'bottom', 'hub', 'more'],
  },
  {
    id: 'profile',
    icon: 'account',
    status: 'legacy',
    legacy: 'profile',
    placements: ['hub', 'more'],
  },
  {
    id: 'price',
    icon: 'coin',
    status: 'legacy',
    legacy: 'price',
    placements: ['top', 'hub'],
    adminOnly: true,
  },
  {
    id: 'admin',
    icon: 'shield',
    status: 'legacy',
    legacy: 'price',
    placements: ['more'],
    adminOnly: true,
  },
  { id: 'events', icon: 'calendar', status: 'planned', placements: ['top', 'hub'] },
  { id: 'sales', icon: 'sales', status: 'planned', placements: ['top', 'hub'] },
  { id: 'stats', icon: 'stats', status: 'planned', placements: ['top', 'hub'] },
];

/** What a given user sees in a place: planned entries and other people's admin entries are out. */
export function navEntries(
  placement: NavPlacement,
  { isAdmin }: { isAdmin: boolean },
  registry: readonly NavEntry[] = NAV,
): NavEntry[] {
  return registry.filter(
    (entry) =>
      entry.status !== 'planned' &&
      entry.placements.includes(placement) &&
      (isAdmin || !entry.adminOnly),
  );
}

/** Where an entry leads: the router path or the Jinja URL. */
export const entryHref = (entry: NavEntry): string =>
  isSpa(entry) ? entry.to : isLegacy(entry) ? legacyHref(entry.legacy) : '#';
