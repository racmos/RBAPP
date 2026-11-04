import { Link } from 'react-router';
import type { StorageLocation } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { SidePanel } from '@/components/ui/SidePanel';
import { cardsHref } from './labels';
import { LocationBadges } from './LocationSheets';
import type { LocationsScreen } from './useLocationsScreen';
import styles from './LocationsDesktop.module.css';

/**
 * The wide-screen panel (F16-d): the selected location, its counts and a link to its cards in the
 * collection, which filters by location code (`/collection?location=`); there is no endpoint
 * that lists the cards of one location by itself.
 */
export function LocationPanel({
  location,
  s,
}: {
  location: StorageLocation | null;
  s: LocationsScreen;
}) {
  const { t, setEditing } = s;
  return (
    <SidePanel
      id="locations-detail"
      kind="detail"
      side="end"
      label={t('panel.title')}
      className={styles.panel}
      contentClassName={styles.panelBody}
    >
      {location === null ? (
        <p className={styles.hint}>{t('panel.empty')}</p>
      ) : (
        <>
          <h2 className={styles.panelCode}>{location.code}</h2>
          <p className={location.description ? styles.panelText : styles.hint}>
            {location.description ?? t('noDescription')}
          </p>
          <LocationBadges location={location} />
          <dl className={styles.facts}>
            <div>
              <dt>{t('panel.position')}</dt>
              <dd>{location.position}</dd>
            </div>
            <div>
              <dt>{t('panel.copies')}</dt>
              <dd>{location.copies}</dd>
            </div>
            <div>
              <dt>{t('panel.cards')}</dt>
              <dd>{location.cards}</dd>
            </div>
          </dl>
          <Link className={styles.link} to={cardsHref(location.code)}>
            {t('viewCards')}
          </Link>
          <Button
            variant="ghost"
            size="sm"
            aria-haspopup="dialog"
            onClick={() => setEditing(location.id)}
          >
            {t('panel.edit')}
          </Button>
        </>
      )}
    </SidePanel>
  );
}
