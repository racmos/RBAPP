/** Admin navigation (F13-a S6): one entry per section, in display order. */
export type AdminNavEntry = { id: 'overview'; to: string; labelKey: 'nav.overview' };

export const ADMIN_NAV: readonly AdminNavEntry[] = [
  { id: 'overview', to: '/admin', labelKey: 'nav.overview' },
];
