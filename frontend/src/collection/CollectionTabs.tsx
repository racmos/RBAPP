import { NavLink } from 'react-router';
import { useTranslation } from 'react-i18next';
import styles from './CollectionTabs.module.css';

export type TabLink = {
  to: string;
  label: string;
  /** Current only on its own path (default), or also on the paths below it. */
  end?: boolean;
};

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
        </NavLink>
      ))}
    </nav>
  );
}

/** "Collection | Wishlists": the two areas of the collection (F3-j). */
export function CollectionTabs() {
  const { t } = useTranslation('wishlists');
  return (
    <TabLinks
      label={t('tabs.label')}
      links={[
        { to: '/collection', label: t('tabs.collection') },
        { to: '/collection/wishlists', label: t('tabs.wishlists'), end: false },
      ]}
    />
  );
}
