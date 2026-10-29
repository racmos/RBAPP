/** Admin navigation (F13-a S6, F13-f S3, F14-d S5): one entry per section, in display order. */
export type AdminNavEntry = {
  id: 'overview' | 'sets' | 'cards' | 'products' | 'riot' | 'changes';
  to: string;
  labelKey:
    | 'nav.overview'
    | 'nav.sets'
    | 'nav.cards'
    | 'nav.products'
    | 'nav.riot'
    | 'nav.changes'
    | 'nav.changesCount';
};

export const ADMIN_NAV: readonly AdminNavEntry[] = [
  { id: 'overview', to: '/admin', labelKey: 'nav.overview' },
  { id: 'sets', to: '/admin/sets', labelKey: 'nav.sets' },
  { id: 'cards', to: '/admin/cards', labelKey: 'nav.cards' },
  { id: 'products', to: '/admin/products', labelKey: 'nav.products' },
  { id: 'riot', to: '/admin/riot', labelKey: 'nav.riot' },
  { id: 'changes', to: '/admin/riot/changes', labelKey: 'nav.changes' },
];

// The label for the changes entry shows the pending count when it is not zero (F13-g S1).
export function changesLabelKey(pending: number | undefined): AdminNavEntry['labelKey'] {
  return pending ? 'nav.changesCount' : 'nav.changes';
}
