import { Outlet } from 'react-router';
import { Brand } from '@/components/ui/Brand';
import { AccountLanguageToggle } from '@/prefs';
import styles from './AuthLayout.module.css';

/** Frame of the login and register screens: wordmark, language toggle, one panel. */
export function AuthLayout() {
  return (
    <div className={styles.page}>
      <div className={styles.language}>
        <AccountLanguageToggle />
      </div>
      <main className={styles.panel}>
        <Brand variant="wordmark" className={styles.brand} />
        <Outlet />
      </main>
    </div>
  );
}
