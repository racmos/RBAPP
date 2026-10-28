import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router';
import type { CardSummary } from '@/api/types';
import { useLogout, useOffline, useSession } from '@/auth';
import { CardCombobox } from '@/catalog';
import { Avatar } from '@/components/ui/Avatar';
import { Brand } from '@/components/ui/Brand';
import { Icon } from '@/components/ui/Icon';
import { up } from '@/lib/breakpoints';
import { useMediaQuery } from '@/lib/useMediaQuery';
import { AccountLanguageToggle } from '@/prefs';
import { InstallItem } from '@/pwa';
import { NavItem } from './NavItem';
import { navEntries } from './navRegistry';
import styles from './Topbar.module.css';

/** A field where typing "/" must type "/" (F2-k S6). */
function isEditable(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName);
}

/**
 * The sticky header (SHELL-2). From `md` it carries the wordmark, the navigation, the ES/EN
 * toggle, the avatar and logout; below it the mark alone, the avatar and an icon-only logout
 * (the language toggle moves to the "Más" sheet).
 */
export function Topbar({ desktop }: { desktop: boolean }) {
  const { t } = useTranslation('nav');
  const session = useSession();
  const { logout, pending } = useLogout();
  const offline = useOffline();
  const { t: tCards } = useTranslation('cards');
  const navigate = useNavigate();
  const wide = useMediaQuery(up('xl'));
  const search = useRef<HTMLInputElement>(null);
  const username = session?.user?.username ?? '';
  const entries = navEntries('top', { isAdmin: session?.user?.is_admin === true });

  // "/" jumps to the card search from anywhere except a field being edited.
  useEffect(() => {
    if (!wide) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== '/' || event.ctrlKey || event.metaKey || event.altKey) return;
      if (event.defaultPrevented || isEditable(event.target)) return;
      event.preventDefault();
      search.current?.focus();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [wide]);

  const openCard = (card: CardSummary) =>
    navigate(`/cards/${card.set_id}/${card.card_id}`, { state: { fromCatalog: true } });

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

        {wide && (
          <div className={styles.search}>
            <CardCombobox
              label={tCards('combobox.globalLabel')}
              hideLabel
              placeholder={tCards('combobox.globalPlaceholder')}
              inputRef={search}
              onSelect={openCard}
            />
            <kbd aria-hidden="true" className={styles.hint}>
              /
            </kbd>
          </div>
        )}

        <div className={styles.right}>
          {desktop && <AccountLanguageToggle />}
          {desktop && (
            <InstallItem className={styles.install} labelClassName={styles.installText} />
          )}
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
            disabled={pending || offline}
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
