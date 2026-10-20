import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import { useLogout, useSession } from '@/auth';
import { Avatar } from '@/components/ui/Avatar';
import { Brand } from '@/components/ui/Brand';
import { Icon } from '@/components/ui/Icon';
import { AccountLanguageToggle } from '@/prefs';
import { NavItem } from './NavItem';
import { navEntries } from './navRegistry';
import styles from './Topbar.module.css';

/**
 * The sticky header (SHELL-2). From `md` it carries the wordmark, the navigation, the ES/EN
 * toggle, the avatar and logout; below it the mark alone, the avatar and an icon-only logout
 * (the language toggle moves to the "Más" sheet).
 */
export function Topbar({ desktop }: { desktop: boolean }) {
  const { t } = useTranslation('nav');
  const session = useSession();
  const { logout, pending } = useLogout();
  const username = session?.user?.username ?? '';
  const entries = navEntries('top', { isAdmin: session?.user?.is_admin === true });

  return (
    <header className={styles.topbar}>
      <div className={styles.bar}>
        <Link to="/" className={styles.brand}>
          <Brand variant={desktop ? 'wordmark' : 'mark'} className={styles.logo} />
        </Link>

        {desktop && (
          <nav aria-label={t('primary')} className={styles.nav}>
            <ul className={styles.list}>
              {entries.map((entry) => (
                <li key={entry.id}>
                  <NavItem entry={entry} className={styles.link}>
                    <Icon name={entry.icon} size={17} className={styles.icon} />
                    {t(`items.${entry.id}.label`)}
                  </NavItem>
                </li>
              ))}
            </ul>
          </nav>
        )}

        <div className={styles.right}>
          {desktop && <AccountLanguageToggle />}
          <Link
            to="/account/interface"
            className={styles.account}
            aria-label={t('account', { username })}
          >
            <Avatar name={username} />
            {desktop && <span className={styles.name}>{username}</span>}
          </Link>
          <button
            type="button"
            className={styles.logout}
            aria-label={t('logout')}
            aria-busy={pending || undefined}
            disabled={pending}
            onClick={logout}
          >
            <Icon name="logout" size={16} />
            {desktop && <span className={styles.logoutText}>{t('logout')}</span>}
          </button>
        </div>
      </div>
    </header>
  );
}
