import { useTranslation } from 'react-i18next';
import { Icon } from './Icon';
import styles from './OfflineBanner.module.css';

/**
 * A non-blocking notice that the app is offline and read-only (PWA-7). A status region: it is
 * announced politely when it appears and never takes focus.
 */
export function OfflineBanner() {
  const { t } = useTranslation('common');
  return (
    <div role="status" className={styles.banner}>
      <Icon name="offline" size={16} className={styles.icon} />
      <span>{t('offline.banner')}</span>
    </div>
  );
}
