import type { ReactNode, RefObject } from 'react';
import { useTranslation } from 'react-i18next';
import { useLogout, useSession } from '@/auth';
import { Icon } from '@/components/ui/Icon';
import { Sheet } from '@/components/ui/Sheet';
import { AccountLanguageToggle } from '@/prefs';
import styles from './MoreSheet.module.css';
import { NavItem } from './NavItem';
import { navEntries, type NavEntry } from './navRegistry';

type MoreSheetProps = {
  open: boolean;
  onClose: () => void;
  returnFocusRef?: RefObject<HTMLElement | null>;
  /** The install entry of the PWA unit (PWA-6) goes here; nothing is rendered without it. */
  install?: ReactNode;
};

/** The phone's "Más" menu (SHELL-4): Interface, classic modules, language, install, Admin, logout. */
export function MoreSheet({ open, onClose, returnFocusRef, install }: MoreSheetProps) {
  const { t } = useTranslation('nav');
  const session = useSession();
  const { logout, pending } = useLogout();
  const entries = navEntries('more', { isAdmin: session?.user?.is_admin === true });
  const account = entries.filter((entry) => entry.id === 'interface');
  const admin = entries.filter((entry) => entry.id === 'admin');
  const modules = entries.filter((entry) => !account.includes(entry) && !admin.includes(entry));

  const renderEntries = (list: NavEntry[]) => (
    <ul className={styles.list}>
      {list.map((entry) => (
        <li key={entry.id}>
          <NavItem entry={entry} className={styles.item} onActivate={onClose}>
            <Icon name={entry.icon} size={20} />
            <span className={styles.text}>{t(`items.${entry.id}.label`)}</span>
            {entry.status === 'legacy' && (
              <Icon name="external-link" size={15} className={styles.out} />
            )}
          </NavItem>
        </li>
      ))}
    </ul>
  );

  return (
    <Sheet open={open} onClose={onClose} title={t('more.title')} returnFocusRef={returnFocusRef}>
      <div className={styles.sections}>
        <section className={styles.section}>
          <h3 className={styles.heading}>{t('more.account')}</h3>
          {renderEntries(account)}
        </section>

        <section className={styles.section}>
          <h3 className={styles.heading}>{t('more.modules')}</h3>
          {renderEntries(modules)}
        </section>

        <section className={styles.section}>
          <h3 className={styles.heading}>{t('more.language')}</h3>
          <AccountLanguageToggle />
        </section>

        {install}

        {admin.length > 0 && <section className={styles.section}>{renderEntries(admin)}</section>}

        <button
          type="button"
          className={styles.logout}
          aria-busy={pending || undefined}
          disabled={pending}
          onClick={() => {
            onClose();
            logout();
          }}
        >
          <Icon name="logout" size={18} />
          {t('logout')}
        </button>
      </div>
    </Sheet>
  );
}
