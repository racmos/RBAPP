import { useRef, type MouseEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Outlet } from 'react-router';
import { useOffline, useOfflineRecovery } from '@/auth';
import { OfflineBanner } from '@/components/ui/OfflineBanner';
import { up } from '@/lib/breakpoints';
import { useMediaQuery } from '@/lib/useMediaQuery';
import styles from './AppShell.module.css';
import { BottomNav } from './BottomNav';
import { Topbar } from './Topbar';

/**
 * Frame of every signed-in screen (SHELL-1): skip link, topbar, one `main`, and below `md` the
 * bottom navigation. The navigation is mounted by viewport (D16), not just hidden, so a screen
 * reader never walks a nav that is not on screen.
 */
export function AppShell() {
  const { t } = useTranslation('common');
  const desktop = useMediaQuery(up('md'));
  const main = useRef<HTMLElement>(null);
  const offline = useOffline();
  useOfflineRecovery();

  const skip = (event: MouseEvent) => {
    event.preventDefault(); // keep the router out of a same-page jump
    main.current?.focus();
  };

  return (
    <div className={styles.shell}>
      <a href="#main" className={styles.skip} onClick={skip}>
        {t('skipToContent')}
      </a>
      <Topbar desktop={desktop} />
      {offline && <OfflineBanner />}
      <main
        id="main"
        ref={main}
        tabIndex={-1}
        className={styles.main}
        data-botnav={!desktop || undefined}
      >
        <div className={styles.content}>
          <Outlet />
        </div>
      </main>
      {!desktop && <BottomNav />}
    </div>
  );
}
