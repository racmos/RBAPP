import { Outlet } from 'react-router';
import { Brand } from '@/components/ui/Brand';
import { LanguageToggle } from '@/i18n';
import styles from './AuthLayout.module.css';

/** Frame of the login and register screens: wordmark, language toggle, one panel. */
export function AuthLayout() {
  return (
    <div className={styles.page}>
      <div className={styles.language}>
        <LanguageToggle />
      </div>
      <main className={styles.panel}>
        <Brand variant="wordmark" className={styles.brand} />
        <Outlet />
      </main>
    </div>
  );
}
