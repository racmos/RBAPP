import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { ErrorState } from '@/components/ui/ErrorState';
import { PageHeader } from '@/components/ui/PageHeader';
import { Skeleton } from '@/components/ui/Skeleton';
import { useDocumentTitle } from '@/i18n';
import { getAdminOverview } from '@/api/endpoints';
import styles from './OverviewPage.module.css';

/** Admin overview (F13-a S6): the four catalog counters. */
export function OverviewPage() {
  const { t } = useTranslation('admin');
  const { t: common } = useTranslation('common');
  useDocumentTitle(t('overview.title'));

  const query = useQuery({
    queryKey: ['admin', 'overview'],
    queryFn: ({ signal }) => getAdminOverview(signal),
  });

  if (query.isPending) {
    return (
      <>
        <PageHeader title={t('overview.title')} subtitle={t('overview.subtitle')} />
        <div className={styles.tiles} aria-label={t('overview.title')}>
          {[0, 1, 2, 3].map((index) => (
            <div key={index} className={styles.tile}>
              <Skeleton label={t('overview.title')} />
            </div>
          ))}
        </div>
      </>
    );
  }

  if (query.isError) {
    return (
      <>
        <PageHeader title={t('overview.title')} subtitle={t('overview.subtitle')} />
        <ErrorState
          message={common('errorState.title')}
          onRetry={() => {
            void query.refetch();
          }}
        />
      </>
    );
  }

  const catalog = query.data.catalog;
  const tiles: Array<[string, number]> = [
    [t('overview.kpi.sets'), catalog.sets],
    [t('overview.kpi.setsWithoutDate'), catalog.sets_without_release_date],
    [t('overview.kpi.cards'), catalog.cards],
    [t('overview.kpi.cardsWithoutImage'), catalog.cards_without_image],
  ];

  return (
    <>
      <PageHeader title={t('overview.title')} subtitle={t('overview.subtitle')} />
      <div className={styles.tiles}>
        {tiles.map(([label, value]) => (
          <div key={label} className={styles.tile}>
            <p className={styles.label}>{label}</p>
            <p className={styles.value}>{value}</p>
          </div>
        ))}
      </div>
    </>
  );
}
