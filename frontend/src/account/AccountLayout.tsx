import { Outlet } from 'react-router';
import { up } from '@/lib/breakpoints';
import { useMediaQuery } from '@/lib/useMediaQuery';
import { AccountSidebar } from './AccountNav';
import { ReauthProvider } from './reauth/ReauthProvider';
import styles from './AccountLayout.module.css';

/**
 * Frame of `/account/*` (F9-i S1, S2): from `xl` a sticky sidebar with the identity summary and
 * the section links beside the section; below it each section shows the tabs under its header
 * (`AccountHeader`). The sidebar is mounted by viewport, so only one section nav exists.
 */
export function AccountLayout() {
  const wide = useMediaQuery(up('xl'));
  return (
    <div className={styles.layout}>
      {wide && <AccountSidebar />}
      <div className={styles.content}>
        {/* F9-j S2: the sections share one re-authentication dialog. */}
        <ReauthProvider>
          <Outlet />
        </ReauthProvider>
      </div>
    </div>
  );
}
