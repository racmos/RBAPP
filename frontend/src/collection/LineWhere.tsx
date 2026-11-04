import { useId, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { CollectionLine, LineLocations } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Select } from '@/components/ui/Select';
import { Skeleton } from '@/components/ui/Skeleton';
import { pushToast } from '@/components/ui/toastStore';
import { translateError } from '@/i18n';
import {
  useLineLocations,
  useLocationLabel,
  useLocations,
  useMoveLineLocations,
} from '@/locations';
import { Stepper } from './Stepper';
import styles from './LineSheet.module.css';

/** `none` is "unassigned" in the selects (copies in no location, F16 D1). */
const NONE = 'none';
const idOf = (value: string): number | null => (value === NONE ? null : Number(value));

type Place = { location_id: number; code: string; description: string | null; qty: number };

function PlaceItem({ place, locked }: { place: Place; locked?: boolean }) {
  const { t } = useTranslation('collection');
  return (
    <li>
      <span className={styles.placeCode}>{place.code}</span>
      {place.description ? ` — ${place.description}` : ''}
      {` × ${place.qty}`}
      {locked ? ` · ${t('where.locked')}` : ''}
    </li>
  );
}

/**
 * Moves copies of the line between its places (F16-R4): from unassigned or one of its locations
 * to another location or back to unassigned. Locked locations are read-only: they are listed but
 * cannot be chosen, and the quantity never goes above what the source holds.
 */
function PlaceMover({ line, places }: { line: CollectionLine; places: LineLocations }) {
  const { t, i18n } = useTranslation('collection');
  const label = useLocationLabel();
  const locations = useLocations();
  const move = useMoveLineLocations();
  const [from, setFrom] = useState<string | null>(null);
  const [to, setTo] = useState<string | null>(null);
  const [qty, setQty] = useState(1);
  const [error, setError] = useState<string | null>(null);

  const all = locations.data?.items ?? [];
  const sources = places.locations.filter((place) => !place.locked);
  const fromValue =
    from ?? (places.unassigned > 0 || sources.length === 0 ? NONE : String(sources[0].location_id));
  const available =
    fromValue === NONE
      ? places.unassigned
      : (places.locations.find((place) => String(place.location_id) === fromValue)?.qty ?? 0);
  const firstTarget = all.find((item) => !item.locked && String(item.id) !== fromValue);
  const toValue = to ?? (firstTarget ? String(firstTarget.id) : NONE);
  const count = Math.max(1, Math.min(qty, available));

  if (locations.isPending) return <Skeleton label={t('where.loading')} lines={2} />;
  if (all.length === 0) return <p className={styles.muted}>{t('where.noLocations')}</p>;

  const submit = () => {
    setError(null);
    move.mutate(
      {
        lineId: line.id,
        body: { from_location_id: idOf(fromValue), to_location_id: idOf(toValue), qty: count },
      },
      {
        onSuccess: () => {
          pushToast({ kind: 'success', message: t('where.moved'), duration: 1500 });
          setFrom(null);
          setTo(null);
          setQty(1);
        },
        onError: (failure) => setError(translateError(failure, i18n)),
      },
    );
  };

  return (
    <div className={styles.mover}>
      <Field label={t('where.from')}>
        {(control) => (
          <Select {...control} value={fromValue} onChange={(event) => setFrom(event.target.value)}>
            <option value={NONE} disabled={places.unassigned === 0}>
              {t('where.unassignedFrom', { qty: places.unassigned })}
            </option>
            {places.locations.map((place) => (
              <option key={place.location_id} value={place.location_id} disabled={place.locked}>
                {`${place.code} (${place.qty})${place.locked ? ` · ${t('where.locked')}` : ''}`}
              </option>
            ))}
          </Select>
        )}
      </Field>
      <Field label={t('where.to')}>
        {(control) => (
          <Select {...control} value={toValue} onChange={(event) => setTo(event.target.value)}>
            <option value={NONE} disabled={fromValue === NONE}>
              {t('where.unassignedTo')}
            </option>
            {all.map((item) => (
              <option
                key={item.id}
                value={item.id}
                disabled={item.locked || String(item.id) === fromValue}
              >
                {label(item)}
              </option>
            ))}
          </Select>
        )}
      </Field>
      <Stepper
        label={t('where.qty')}
        value={count}
        min={1}
        max={Math.max(1, available)}
        disabled={available === 0}
        onCommit={setQty}
      />
      {error && (
        <p role="alert" className={styles.alert}>
          {error}
        </p>
      )}
      <Button
        size="sm"
        disabled={available === 0 || fromValue === toValue}
        pending={move.isPending}
        onClick={submit}
      >
        {t('where.move')}
      </Button>
    </div>
  );
}

/**
 * "Where they are" (F16-R5): the first 5 locations of the line as `code — description × qty` in
 * the user's order, "and N more" for the full list, the unassigned copies, and the editor.
 */
export function LineWhere({ line, offline }: { line: CollectionLine; offline: boolean }) {
  const { t } = useTranslation('collection');
  const titleId = useId();
  const [showAll, setShowAll] = useState(false);
  const [editing, setEditing] = useState(false);
  const full = useLineLocations(line.id, showAll || editing);

  const loaded = (showAll || editing) && full.data ? full.data : null;
  const places: (Place & { locked?: boolean })[] =
    showAll && loaded ? loaded.locations : (line.locations ?? []);
  const more = showAll ? 0 : (line.locations_more ?? 0);
  const unassigned = loaded?.unassigned ?? line.unassigned ?? line.qty;

  return (
    // a group, not a region: every line of the sheet has one, and landmarks must be unique
    <div role="group" className={styles.where} aria-labelledby={titleId}>
      <h3 id={titleId} className={styles.whereTitle}>
        {t('where.title')}
      </h3>
      {places.length === 0 ? (
        <p className={styles.muted}>{t('where.none')}</p>
      ) : (
        <ul className={styles.places} aria-busy={(showAll && full.isFetching) || undefined}>
          {places.map((place) => (
            <PlaceItem key={place.location_id} place={place} locked={place.locked} />
          ))}
        </ul>
      )}
      {more > 0 && (
        <Button variant="ghost" size="sm" onClick={() => setShowAll(true)}>
          {t('where.more', { n: more })}
        </Button>
      )}
      <p className={styles.unassigned}>{t('where.unassigned', { qty: unassigned })}</p>
      <Button
        variant="ghost"
        size="sm"
        aria-expanded={editing}
        disabled={offline}
        onClick={() => setEditing((open) => !open)}
      >
        {t('where.change')}
      </Button>
      {editing &&
        !offline &&
        (full.data ? (
          <PlaceMover line={line} places={full.data} />
        ) : full.isError ? (
          <p role="alert" className={styles.alert}>
            {t('where.error')}
          </p>
        ) : (
          <Skeleton label={t('where.loading')} lines={2} />
        ))}
    </div>
  );
}
