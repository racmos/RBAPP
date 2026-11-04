import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Icon } from '@/components/ui/Icon';
import { PageHeader } from '@/components/ui/PageHeader';
import { Skeleton } from '@/components/ui/Skeleton';
import { useLocationCounts } from './labels';
import { LocationBadges } from './LocationSheets';
import type { LocationsScreen } from './useLocationsScreen';
import styles from './LocationsPage.module.css';

/** The copies in no location: always last, never movable (F16 D1). */
export function UnassignedRow({ count }: { count: number }) {
  const { t } = useTranslation('locations');
  return (
    <p className={styles.unassigned}>
      <span className={styles.unassignedText}>{t('unassigned', { count })}</span>
      <span className={styles.hint}>{t('unassignedHint')}</span>
    </p>
  );
}

/** The header of both layouts: title, what the order means and the create button. */
export function LocationsHeader({ s }: { s: LocationsScreen }) {
  const { t, offline, setCreating } = s;
  const { t: tCommon } = useTranslation('common');
  return (
    <>
      <PageHeader
        title={t('title')}
        subtitle={t('subtitle')}
        actions={
          <Button disabled={offline} onClick={() => setCreating(true)}>
            <Icon name="plus" size={16} />
            {t('new')}
          </Button>
        }
      />
      {offline && <p className={styles.note}>{tCommon('offline.editDisabled')}</p>}
    </>
  );
}

/** Loading, failure and nothing yet; null when there is a list to show. */
export function LocationsState({ s }: { s: LocationsScreen }) {
  const { t, query, items, unassigned, offline, setCreating } = s;
  if (query.isPending) return <Skeleton label={t('loading')} lines={5} />;
  if (query.isError && !query.data) {
    return <ErrorState message={t('error')} onRetry={() => void query.refetch()} />;
  }
  if (items.length > 0) return null;
  return (
    <>
      <EmptyState
        icon="pin"
        title={t('empty.title')}
        body={t('empty.body')}
        action={offline ? undefined : { label: t('new'), onAction: () => setCreating(true) }}
      />
      <UnassignedRow count={unassigned} />
    </>
  );
}

/** The layout below 1240 px (F16-c): the locations in order, each with its up and down buttons. */
export function LocationsMobile({ s }: { s: LocationsScreen }) {
  const { t, offline, items, unassigned, moveBy, setEditing, query } = s;
  const counts = useLocationCounts();
  const state = <LocationsState s={s} />;

  return (
    <div className={styles.page}>
      <LocationsHeader s={s} />
      {items.length === 0 ? (
        state
      ) : (
        <>
          <ol
            className={styles.list}
            aria-label={t('list')}
            aria-busy={query.isFetching || undefined}
          >
            {items.map((location, index) => (
              <li key={location.id} className={styles.item}>
                <button
                  type="button"
                  className={styles.open}
                  aria-haspopup="dialog"
                  onClick={() => setEditing(location.id)}
                >
                  <span className={styles.code} data-slot="code">
                    {location.code}
                  </span>
                  <span className={location.description ? styles.description : styles.muted}>
                    {location.description ?? t('noDescription')}
                  </span>
                  <span className={styles.counts}>{counts(location)}</span>
                  <LocationBadges location={location} />
                </button>
                <span className={styles.moves}>
                  <Button
                    variant="ghost"
                    size="sm"
                    aria-label={t('moveUp', { code: location.code })}
                    title={t('moveUp', { code: location.code })}
                    disabled={offline || index === 0}
                    onClick={() => moveBy(location.id, -1)}
                  >
                    <Icon name="arrow-up" size={16} />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    aria-label={t('moveDown', { code: location.code })}
                    title={t('moveDown', { code: location.code })}
                    disabled={offline || index === items.length - 1}
                    onClick={() => moveBy(location.id, 1)}
                  >
                    <Icon name="arrow-down" size={16} />
                  </Button>
                </span>
              </li>
            ))}
          </ol>
          <UnassignedRow count={unassigned} />
        </>
      )}
    </div>
  );
}
