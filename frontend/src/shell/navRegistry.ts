import type { IconName } from '@/components/ui/icons';

/**
 * One registry feeds the topbar, the bottom navigation, the "More" sheet and the home hub
 * (SHELL-5). Each entry is `spa` (a router link) or `planned` (not rendered anywhere). The app
 * never links to the old Jinja web (Jinja retirement 2/3).
 */
export type NavStatus = 'spa' | 'planned';
export type NavPlacement = 'top' | 'bottom' | 'hub' | 'more';
export type NavId =
  | 'home'
  | 'cards'
  | 'collection'
  | 'products'
  | 'locations'
  | 'decks'
  | 'profile'
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
  ({ status: 'spa'; /** Router path, without the basename. */ to: string } | { status: 'planned' });

export const isSpa = (entry: NavEntry): entry is Extract<NavEntry, { status: 'spa' }> =>
  entry.status === 'spa';

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
    id: 'cards',
    icon: 'cards',
    status: 'spa',
    to: '/cards',
    placements: ['top', 'bottom', 'hub', 'more'],
  },
  {
    id: 'collection',
    icon: 'collection',
    status: 'spa',
    to: '/collection',
    placements: ['top', 'bottom', 'hub', 'more'],
  },
  {
    id: 'products',
    icon: 'gift',
    status: 'spa',
    to: '/products',
    placements: ['top', 'hub', 'more'],
  },
  {
    id: 'locations',
    icon: 'pin',
    status: 'spa',
    to: '/locations',
    placements: ['top', 'hub', 'more'],
  },
  {
    id: 'decks',
    icon: 'decks',
    status: 'spa',
    to: '/decks',
    placements: ['top', 'bottom', 'hub', 'more'],
  },
  {
    id: 'profile',
    icon: 'account',
    status: 'spa',
    to: '/account/profile',
    placements: ['hub', 'more'],
  },
  {
    id: 'admin',
    icon: 'shield',
    status: 'spa',
    to: '/admin',
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

/** Where an entry leads: its router path (`#` for a planned entry). */
export const entryHref = (entry: NavEntry): string => (isSpa(entry) ? entry.to : '#');
