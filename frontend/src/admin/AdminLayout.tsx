import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router';
import { getAdminOverview } from '@/api/endpoints';
import { Select } from '@/components/ui/Select';
import { SidePanel } from '@/components/ui/SidePanel';
import { down, up } from '@/lib/breakpoints';
import { useMediaQuery } from '@/lib/useMediaQuery';
import { ADMIN_NAV, changesLabelKey, type AdminNavEntry } from './adminNav';
import styles from './AdminLayout.module.css';

/** Frame of the admin area (F13-a S6): side navigation on desktop, a select below it. */
export function AdminLayout() {
  const { t } = useTranslation('admin');
  const desktop = useMediaQuery(up('xl'));
  const phone = useMediaQuery(down('md'));
  const location = useLocation();
  const navigate = useNavigate();
  const overview = useQuery({
    queryKey: ['admin', 'overview'],
    queryFn: ({ signal }) => getAdminOverview(signal),
  });
  const pending = overview.data?.riot?.pending_changes ?? 0;
  const labelOf = (entry: AdminNavEntry) =>
    entry.id === 'changes' && entry.labelKey === 'nav.changes'
      ? t(changesLabelKey(pending), pending ? { count: pending } : undefined)
      : t(entry.labelKey);

  return (
    <div className={styles.layout}>
      {desktop ? (
        // Folds away to its toggle, the page takes the width (owner feedback S23).
        <SidePanel
          as="nav"
          id="admin-nav"
          kind="menu"
          label={t('nav.label')}
          className={styles.nav}
        >
          {ADMIN_NAV.map((entry) => (
            <NavLink key={entry.id} to={entry.to} end className={styles.link}>
              {labelOf(entry)}
            </NavLink>
          ))}
        </SidePanel>
      ) : (
        <Select
          aria-label={t('nav.label')}
          className={styles.select}
          value={location.pathname.replace(/^\/riftbound\/app/, '') || '/'}
          onChange={(event) => {
            void navigate(event.target.value);
          }}
        >
          {ADMIN_NAV.map((entry) => (
            <option key={entry.id} value={entry.to}>
              {labelOf(entry)}
            </option>
          ))}
        </Select>
      )}
      <div>
        {phone && <p className={styles.hint}>{t('mobileHint')}</p>}
        <Outlet />
      </div>
    </div>
  );
}
