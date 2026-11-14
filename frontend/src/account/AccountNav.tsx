import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { NavLink } from 'react-router';
import { useSession } from '@/auth';
import { Avatar } from '@/components/ui/Avatar';
import { PageHeader } from '@/components/ui/PageHeader';
import { up } from '@/lib/breakpoints';
import { useMediaQuery } from '@/lib/useMediaQuery';
import styles from './AccountLayout.module.css';
import { ACCOUNT_SECTIONS } from './sections';

/** The section links (F9-i S2): a scrollable row of tabs, or the list of the sidebar. */
export function SectionNav({ variant }: { variant: 'tabs' | 'list' }) {
  const { t } = useTranslation('account');
  return (
    <nav aria-label={t('layout.navLabel')} className={styles[variant]}>
      <ul className={styles.links}>
        {ACCOUNT_SECTIONS.map((section) => (
          <li key={section.id}>
            <NavLink to={section.to} end className={styles.link}>
              {t(`sections.${section.id}`)}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}

/** From `xl` (F9-i S2): the identity summary and the section links, sticky beside the page. */
export function AccountSidebar() {
  const { t } = useTranslation('account');
  const user = useSession()?.user;
  const username = user?.username ?? '';
  const name = user?.display_name || username;
  return (
    <aside aria-label={t('layout.title')} className={styles.sidebar}>
      <div className={styles.who}>
        <Avatar name={name} src={user?.avatar_url} size={42} />
        <div className={styles.whoText}>
          <p className={styles.name}>{name}</p>
          <p className={styles.handle}>@{username}</p>
        </div>
      </div>
      <SectionNav variant="list" />
    </aside>
  );
}

/**
 * The header of an account section: its `h1` and, below `xl` where there is no sidebar, the
 * section tabs right under it (F9-i UI table).
 */
export function AccountHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  const wide = useMediaQuery(up('xl'));
  return (
    <>
      <PageHeader title={title} subtitle={subtitle} actions={actions} />
      {!wide && <SectionNav variant="tabs" />}
    </>
  );
}
