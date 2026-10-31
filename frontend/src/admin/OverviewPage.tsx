import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import { Badge } from '@/components/ui/Badge';
import { ErrorState } from '@/components/ui/ErrorState';
import { PageHeader } from '@/components/ui/PageHeader';
import { Skeleton } from '@/components/ui/Skeleton';
import { useDocumentTitle } from '@/i18n';
import { formatDateTime } from '@/lib/format';
import { getAdminOverview, type AdminRiot } from '@/api/endpoints';
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
      <RiotBand riot={query.data.riot} />
    </>
  );
}

/** Riot band (F13-g S8): pending changes, last sync, sets to name. */
function RiotBand({ riot }: { riot: AdminRiot }) {
  const { t } = useTranslation('admin');
  return (
    <section aria-label={t('overview.riotTitle')}>
      <h2 className={styles.sectionTitle}>{t('overview.riotTitle')}</h2>
      <div className={styles.tiles}>
        <div className={styles.tile}>
          <p className={styles.label}>{t('overview.kpi.pendingChanges')}</p>
          <p className={styles.value}>
            <Link to="/admin/riot/changes">{riot.pending_changes}</Link>
          </p>
        </div>
        <div className={styles.tile}>
          <p className={styles.label}>{t('overview.kpi.activeSets')}</p>
          <p className={styles.value}>
            <Link to="/admin/riot">{riot.active_sets.length}</Link>
          </p>
        </div>
        <div className={styles.tile}>
          <p className={styles.label}>{t('overview.kpi.lastSync')}</p>
          <p className={styles.value}>
            {riot.last_sync ? (
              <>
                <Badge>{riot.last_sync.status}</Badge>{' '}
                {riot.last_sync.finished_at ? formatDateTime(riot.last_sync.finished_at) : '—'}
              </>
            ) : (
              t('overview.noSync')
            )}
          </p>
        </div>
        {riot.placeholder_sets.length > 0 && (
          <div className={styles.tile}>
            <p className={styles.label}>
              <Link to="/admin/sets">
                {t('overview.placeholderSets', {
                  codes: riot.placeholder_sets.join(', '),
                  defaultValue: riot.placeholder_sets.join(', '),
                })}
              </Link>
            </p>
          </div>
        )}
      </div>
    </section>
  );
}
