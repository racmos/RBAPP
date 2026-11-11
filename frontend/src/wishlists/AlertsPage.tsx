import { useTranslation } from 'react-i18next';
import { CollectionTabs } from '@/collection/CollectionTabs';
import { EmptyState } from '@/components/ui/EmptyState';
import { PageHeader } from '@/components/ui/PageHeader';
import { useDocumentTitle } from '@/i18n';
import { WishlistTabs } from './WishlistsPage';
import styles from './Wishlists.module.css';

/**
 * `/collection/wishlists/alerts` (F3-j): the shell of the price alerts. The alerts and their API
 * arrive with F4-g; until then the screen explains what will appear here and asks for nothing.
 */
export function AlertsPage() {
  const { t } = useTranslation('wishlists');
  useDocumentTitle(t('alerts.title'));
  return (
    <div className={styles.page}>
      <CollectionTabs />
      <PageHeader title={t('alerts.title')} subtitle={t('alerts.intro')} />
      <WishlistTabs />
      <EmptyState icon="clock" title={t('alerts.empty.title')} body={t('alerts.empty.body')} />
    </div>
  );
}
