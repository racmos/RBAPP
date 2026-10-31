import { Outlet } from 'react-router';
import { Brand } from '@/components/ui/Brand';
import styles from './AuthLayout.module.css';

/** Frame of the login and register screens: wordmark and one panel. */
export function AuthLayout() {
  return (
    <div className={styles.page}>
      <main className={styles.panel}>
        <Brand variant="wordmark" className={styles.brand} />
        <Outlet />
      </main>
    </div>
  );
}
