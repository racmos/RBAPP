/** Admin navigation (F13-a S6, F13-f S3): one entry per section, in display order. */
export type AdminNavEntry = {
  id: 'overview' | 'sets' | 'cards' | 'riot';
  to: string;
  labelKey: 'nav.overview' | 'nav.sets' | 'nav.cards' | 'nav.riot';
};

export const ADMIN_NAV: readonly AdminNavEntry[] = [
  { id: 'overview', to: '/admin', labelKey: 'nav.overview' },
  { id: 'sets', to: '/admin/sets', labelKey: 'nav.sets' },
  { id: 'cards', to: '/admin/cards', labelKey: 'nav.cards' },
  { id: 'riot', to: '/admin/riot', labelKey: 'nav.riot' },
];
