/** Admin navigation (F13-a S6, F13-f S3, F14-d S5, CM-a): one entry per section, in display order. */
export type AdminNavEntry = {
  id: 'overview' | 'sets' | 'cards' | 'products' | 'cardmarket' | 'riot' | 'changes';
  to: string;
  labelKey:
    | 'nav.overview'
    | 'nav.sets'
    | 'nav.cards'
    | 'nav.products'
    | 'nav.cardmarket'
    | 'nav.riot'
    | 'nav.changes'
    | 'nav.changesCount';
};

export const ADMIN_NAV: readonly AdminNavEntry[] = [
  { id: 'overview', to: '/admin', labelKey: 'nav.overview' },
  { id: 'sets', to: '/admin/sets', labelKey: 'nav.sets' },
  { id: 'cards', to: '/admin/cards', labelKey: 'nav.cards' },
  { id: 'products', to: '/admin/products', labelKey: 'nav.products' },
  { id: 'cardmarket', to: '/admin/cardmarket', labelKey: 'nav.cardmarket' },
  { id: 'riot', to: '/admin/riot', labelKey: 'nav.riot' },
  { id: 'changes', to: '/admin/riot/changes', labelKey: 'nav.changes' },
];

// The label for the changes entry shows the pending count when it is not zero (F13-g S1).
export function changesLabelKey(pending: number | undefined): AdminNavEntry['labelKey'] {
  return pending ? 'nav.changesCount' : 'nav.changes';
}

/**
 * The entry of a path: the exact one, else the longest entry the path lies under (the matching
 * workbench at `/admin/cardmarket/matching` belongs to Cardmarket, CM-b).
 */
export function navEntryFor(path: string): AdminNavEntry | undefined {
  return (
    ADMIN_NAV.find((entry) => entry.to === path) ??
    ADMIN_NAV.filter((entry) => entry.to !== '/admin' && path.startsWith(`${entry.to}/`)).sort(
      (a, b) => b.to.length - a.to.length,
    )[0]
  );
}

/** A link stays current on the pages under it, unless another entry lives there. */
export const matchesExactly = (entry: AdminNavEntry): boolean =>
  entry.to === '/admin' || ADMIN_NAV.some((other) => other.to.startsWith(`${entry.to}/`));
