import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSession } from '@/auth';
import { Icon } from '@/components/ui/Icon';
import { InstallItem } from '@/pwa';
import styles from './BottomNav.module.css';
import { MoreSheet } from './MoreSheet';
import { NavItem } from './NavItem';
import { navEntries } from './navRegistry';

/** Phone navigation (SHELL-3, R3): four destinations from the registry and "More". */
export function BottomNav() {
  const { t } = useTranslation('nav');
  const session = useSession();
  const [moreOpen, setMoreOpen] = useState(false);
  const moreButton = useRef<HTMLButtonElement>(null);
  const entries = navEntries('bottom', { isAdmin: session?.user?.is_admin === true });

  return (
    <>
      <nav aria-label={t('primary')} className={styles.nav}>
        <ul className={styles.list}>
          {entries.map((entry) => (
            <li key={entry.id} className={styles.cell}>
              <NavItem entry={entry} className={styles.item}>
                <Icon name={entry.icon} size={21} />
                <span className={styles.label}>{t(`items.${entry.id}.label`)}</span>
              </NavItem>
            </li>
          ))}
          <li className={styles.cell}>
            <button
              ref={moreButton}
              type="button"
              className={styles.item}
              aria-haspopup="dialog"
              aria-expanded={moreOpen}
              onClick={() => setMoreOpen(true)}
            >
              <Icon name="more" size={21} />
              <span className={styles.label}>{t('more.label')}</span>
            </button>
          </li>
        </ul>
      </nav>
      <MoreSheet
        open={moreOpen}
        onClose={() => setMoreOpen(false)}
        returnFocusRef={moreButton}
        install={<InstallItem />}
      />
    </>
  );
}
