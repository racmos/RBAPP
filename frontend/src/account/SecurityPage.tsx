import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { useOffline } from '@/auth';
import { ErrorState } from '@/components/ui/ErrorState';
import { Skeleton } from '@/components/ui/Skeleton';
import { translateError, useDocumentTitle } from '@/i18n';
import { AccountHeader } from './AccountNav';
import { MfaCard } from './MfaCard';
import { PasswordCard } from './PasswordCard';
import { meQuery } from './queries';
import styles from './SecurityPage.module.css';
import { SessionsCard } from './SessionsCard';

/**
 * `/account/security` (F9-j S4-S9): the password, two-factor authentication and the signed-in
 * devices. Offline the cards keep what the cache has and every action is disabled (S16).
 */
export function SecurityPage() {
  const { t, i18n } = useTranslation('account');
  const { t: tCommon } = useTranslation('common');
  useDocumentTitle(t('sections.security'));
  const offline = useOffline();
  const me = useQuery({ ...meQuery, enabled: !offline });
  const security = me.data?.security;

  let password;
  let mfa;
  if (security || offline) {
    // Offline without a cached summary the password form is shown read-only.
    password = <PasswordCard hasPassword={security?.has_password ?? true} offline={offline} />;
    mfa = <MfaCard mfa={security?.mfa ?? null} offline={offline} />;
  } else if (me.isError) {
    const error = (
      <ErrorState message={translateError(me.error, i18n)} onRetry={() => void me.refetch()} />
    );
    password = error;
    mfa = null;
  } else {
    const skeleton = (
      <div className={styles.skeletonCard}>
        <Skeleton label={tCommon('loadingRegion')} lines={4} />
      </div>
    );
    password = skeleton;
    mfa = skeleton;
  }

  return (
    <>
      <AccountHeader title={t('sections.security')} subtitle={t('security.subtitle')} />
      {offline && <p className={styles.offline}>{tCommon('offline.editDisabled')}</p>}
      <div className={styles.grid}>
        <div className={styles.password}>{password}</div>
        {mfa && <div className={styles.mfa}>{mfa}</div>}
        <div className={styles.devices}>
          <SessionsCard offline={offline} />
        </div>
      </div>
    </>
  );
}
