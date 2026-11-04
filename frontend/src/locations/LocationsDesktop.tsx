import { useState, type DragEvent } from 'react';
import { useTranslation } from 'react-i18next';
import type { StorageLocation } from '@/api/types';
import { DebouncedInput } from '@/catalog';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import { TableScroll } from '@/components/ui/TableScroll';
import { pushToast } from '@/components/ui/toastStore';
import { translateError } from '@/i18n';
import { up } from '@/lib/breakpoints';
import { useMediaQuery } from '@/lib/useMediaQuery';
import { DESCRIPTION_MAX, cleanDescription } from './labels';
import { LocationPanel } from './LocationPanel';
import { ConfirmLocationDelete } from './LocationSheets';
import { LocationsHeader, LocationsState, UnassignedRow } from './LocationsMobile';
import { useDeleteLocation, usePatchLocation } from './queries';
import type { LocationsScreen } from './useLocationsScreen';
import styles from './LocationsDesktop.module.css';

const COLUMNS = ['position', 'code', 'description', 'copies', 'cards', 'lock', 'actions'] as const;
const DRAG_TYPE = 'text/plain';

/** The inline editors and buttons keep their clicks: they never select the row. */
const keep = (event: { stopPropagation: () => void }) => event.stopPropagation();

type RowProps = {
  location: StorageLocation;
  index: number;
  last: boolean;
  s: LocationsScreen;
  active: boolean;
  draggable: boolean;
  dropTarget: boolean;
  onSelect: () => void;
  onDelete: () => void;
  drag: {
    start: (event: DragEvent) => void;
    over: (event: DragEvent) => void;
    drop: (event: DragEvent) => void;
    end: () => void;
  };
};

function Row({
  location,
  index,
  last,
  s,
  active,
  draggable,
  dropTarget,
  onSelect,
  onDelete,
  drag,
}: RowProps) {
  const { t, offline, moveBy, setEditing } = s;
  const { i18n } = useTranslation();
  const patch = usePatchLocation();
  const { code } = location;
  const save = (body: { description?: string | null; locked?: boolean }) =>
    patch.mutate(
      { id: location.id, body },
      {
        onError: (error) => pushToast({ kind: 'error', message: translateError(error, i18n) }),
      },
    );

  return (
    <tr
      data-active={active || undefined}
      data-drop-target={dropTarget || undefined}
      draggable={draggable}
      onDragStart={drag.start}
      onDragOver={drag.over}
      onDrop={drag.drop}
      onDragEnd={drag.end}
      onClick={onSelect}
    >
      <td className={styles.position}>
        {draggable && <Icon name="grip" size={14} className={styles.grip} />}
        {location.position}
      </td>
      <td>
        <span className={styles.codeCell}>
          <span className={styles.code} data-slot="code">
            {code}
          </span>
          {location.deck_id !== null && <Badge tone="accent">{t('deck')}</Badge>}
        </span>
      </td>
      <td onClick={keep}>
        <DebouncedInput
          className={styles.description}
          aria-label={t('table.descriptionOf', { code })}
          maxLength={DESCRIPTION_MAX}
          disabled={offline}
          value={location.description ?? ''}
          delay={500}
          onCommit={(next) => {
            const description = cleanDescription(next);
            if (description !== location.description) save({ description });
          }}
        />
      </td>
      <td className={styles.numeric}>{location.copies}</td>
      <td className={styles.numeric}>{location.cards}</td>
      <td onClick={keep}>
        <button
          type="button"
          role="switch"
          aria-checked={location.locked}
          aria-label={t('lockRow', { code })}
          title={t('lockRow', { code })}
          className={styles.switch}
          disabled={offline || patch.isPending}
          onClick={() => save({ locked: !location.locked })}
        >
          <span aria-hidden="true" />
        </button>
      </td>
      <td onClick={keep}>
        <span className={styles.actions}>
          <Button
            variant="ghost"
            size="sm"
            aria-label={t('moveUp', { code })}
            title={t('moveUp', { code })}
            disabled={offline || index === 0}
            onClick={() => moveBy(location.id, -1)}
          >
            <Icon name="arrow-up" size={16} />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            aria-label={t('moveDown', { code })}
            title={t('moveDown', { code })}
            disabled={offline || last}
            onClick={() => moveBy(location.id, 1)}
          >
            <Icon name="arrow-down" size={16} />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            aria-label={t('edit', { code })}
            title={t('edit', { code })}
            aria-haspopup="dialog"
            onClick={() => setEditing(location.id)}
          >
            <Icon name="edit" size={16} />
          </Button>
          <Button
            variant="danger"
            size="sm"
            aria-label={t('deleteRow', { code })}
            title={t('deleteRow', { code })}
            disabled={offline}
            onClick={onDelete}
          >
            <Icon name="trash" size={16} />
          </Button>
        </span>
      </td>
    </tr>
  );
}

/**
 * The layout from 1240 px (F16-d): the locations as a table with inline edits, reordered with the
 * arrows (keyboard) or by dragging a row (pointer devices); from 1600 px the selected location
 * in a side panel.
 */
export function LocationsDesktop({ s }: { s: LocationsScreen }) {
  const { t, offline, items, unassigned, moveTo, query } = s;
  const { i18n } = useTranslation();
  const wide = useMediaQuery(up('2xl'));
  const pointer = useMediaQuery('(pointer: fine)');
  const remove = useDeleteLocation();
  const [activeId, setActiveId] = useState<number | null>(null);
  const [deleting, setDeleting] = useState<StorageLocation | null>(null);
  const [dragged, setDragged] = useState<number | null>(null);
  const [over, setOver] = useState<number | null>(null);

  const active = wide ? (items.find((item) => item.id === activeId) ?? items[0] ?? null) : null;

  const dragFor = (location: StorageLocation, index: number) => ({
    start: (event: DragEvent) => {
      if (offline) return;
      setDragged(location.id);
      event.dataTransfer.setData(DRAG_TYPE, String(location.id));
      event.dataTransfer.effectAllowed = 'move';
    },
    over: (event: DragEvent) => {
      if (dragged === null) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = 'move';
      setOver(location.id);
    },
    drop: (event: DragEvent) => {
      event.preventDefault();
      const id = dragged ?? Number(event.dataTransfer.getData(DRAG_TYPE));
      setDragged(null);
      setOver(null);
      if (Number.isInteger(id) && id > 0) moveTo(id, index);
    },
    end: () => {
      setDragged(null);
      setOver(null);
    },
  });

  const confirmDelete = () => {
    const target = deleting;
    setDeleting(null);
    if (!target) return;
    remove
      .mutateAsync(target.id)
      .then(() => pushToast({ kind: 'success', message: t('deleted') }))
      .catch((error) => pushToast({ kind: 'error', message: translateError(error, i18n) }));
  };

  return (
    <div className={styles.page}>
      <div className={styles.layout} data-wide={wide || undefined}>
        <div className={styles.main}>
          <LocationsHeader s={s} />
          {items.length === 0 ? (
            <LocationsState s={s} />
          ) : (
            <>
              {pointer && !offline && <p className={styles.hint}>{t('dragHint')}</p>}
              <TableScroll fit>
                <table className={styles.table} aria-busy={query.isFetching || undefined}>
                  <caption className="sr-only">{t('list')}</caption>
                  <thead>
                    <tr>
                      {COLUMNS.map((key) => (
                        <th
                          key={key}
                          scope="col"
                          className={
                            key === 'copies' || key === 'cards' ? styles.numeric : undefined
                          }
                        >
                          {t(`table.columns.${key}`)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((location, index) => (
                      <Row
                        key={location.id}
                        location={location}
                        index={index}
                        last={index === items.length - 1}
                        s={s}
                        active={active?.id === location.id}
                        draggable={pointer && !offline}
                        dropTarget={over === location.id && dragged !== location.id}
                        onSelect={() => setActiveId(location.id)}
                        onDelete={() => setDeleting(location)}
                        drag={dragFor(location, index)}
                      />
                    ))}
                  </tbody>
                </table>
              </TableScroll>
              <UnassignedRow count={unassigned} />
            </>
          )}
        </div>
        {wide && <LocationPanel location={active} s={s} />}
      </div>
      {deleting && (
        <ConfirmLocationDelete
          location={deleting}
          open
          onConfirm={confirmDelete}
          onCancel={() => setDeleting(null)}
        />
      )}
    </div>
  );
}
