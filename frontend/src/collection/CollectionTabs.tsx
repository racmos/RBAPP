import { NavLink } from 'react-router';
import { useTranslation } from 'react-i18next';
import { useAlertsBadge } from '@/wishlists';
import styles from './CollectionTabs.module.css';

export type TabLink = {
  to: string;
  label: string;
  /** Current only on its own path (default), or also on the paths below it. */
  end?: boolean;
  /** A count after the label, named by `label` for assistive technology ("2 unread alerts"). */
  badge?: { count: number; label: string };
};

/** The count a tab shows: "99+" above 99; its name is the full sentence. */
export function TabBadge({ count, label }: { count: number; label: string }) {
  return (
    <span role="img" aria-label={label} className={styles.badge}>
      {count > 99 ? '99+' : count}
    </span>
  );
}

/** A row of links shown as tabs; the current one carries `aria-current="page"`. */
export function TabLinks({
  label,
  links,
  size = 'md',
}: {
  label: string;
  links: readonly TabLink[];
  size?: 'md' | 'sm';
}) {
  return (
    <nav aria-label={label} className={[styles.tabs, styles[size]].join(' ')}>
      {links.map((link) => (
        <NavLink key={link.to} to={link.to} end={link.end ?? true} className={styles.tab}>
          {link.label}
          {link.badge && <TabBadge {...link.badge} />}
        </NavLink>
      ))}
    </nav>
  );
}

/**
 * "Collection | Wishlists": the two areas of the collection (F3-j). The Wishlists tab carries the
 * unread price alerts badge (F4-g-2).
 */
export function CollectionTabs() {
  const { t } = useTranslation('wishlists');
  const unread = useAlertsBadge();
  return (
    <TabLinks
      label={t('tabs.label')}
      links={[
        { to: '/collection', label: t('tabs.collection') },
        {
          to: '/collection/wishlists',
          label: t('tabs.wishlists'),
          end: false,
          badge: unread
            ? { count: unread, label: t('alerts.badge', { count: unread }) }
            : undefined,
        },
      ]}
    />
  );
}
