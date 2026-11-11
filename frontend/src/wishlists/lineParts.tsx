import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import type { WishlistLine, WishlistLinePatchBody } from '@/api/types';
import { DebouncedInput } from '@/catalog';
import { Badge } from '@/components/ui/Badge';
import { pushToast } from '@/components/ui/toastStore';
import { formatDate, formatMoney } from '@/lib/format';
import { useWishlistError } from './errors';
import {
  lineBody,
  useAddWishlistLine,
  useDeleteWishlistLine,
  usePatchWishlistLine,
} from './queries';
import styles from './Lines.module.css';

export const QTY_MIN = 1;
export const QTY_MAX = 99;
export const NOTE_MAX = 200;

/** The note as the API stores it: trimmed, empty = none. */
export const cleanNote = (value: string): string | null => value.trim() || null;

/**
 * Saves changes of one line, one after another, so a quick second edit never overtakes the first.
 * A failure shows its message and reloads the list, so the screen shows what is stored.
 */
export function useLineSaver(line: WishlistLine) {
  const { t } = useTranslation('wishlists');
  const client = useQueryClient();
  const patch = usePatchWishlistLine();
  const message = useWishlistError();
  const queue = useRef<Promise<unknown>>(Promise.resolve());
  const { list_id: listId, id } = line;

  return useCallback(
    (body: WishlistLinePatchBody) => {
      const run = async () => {
        try {
          await patch.mutateAsync({ listId, lineId: id, body });
          pushToast({ kind: 'success', message: t('line.saved'), duration: 1500 });
        } catch (error) {
          pushToast({ kind: 'error', message: message(error) });
          await client.invalidateQueries({ queryKey: ['wishlists', listId] });
        }
      };
      queue.current = queue.current.then(run, run);
      return queue.current;
    },
    [patch, listId, id, client, message, t],
  );
}

/** Removes a line; the toast's Undo posts it back to its list. */
export function useRemoveLine() {
  const { t } = useTranslation('wishlists');
  const remove = useDeleteWishlistLine();
  const add = useAddWishlistLine();
  const message = useWishlistError();
  return (line: WishlistLine) =>
    remove
      .mutateAsync({ listId: line.list_id, lineId: line.id })
      .then(({ deleted }) =>
        pushToast({
          kind: 'success',
          message: t('line.removed', { name: deleted.name }),
          duration: 8000,
          action: {
            label: t('undo'),
            onAction: () =>
              void add
                .mutateAsync({ listId: deleted.list_id, body: lineBody(deleted) })
                .then(() =>
                  pushToast({
                    kind: 'success',
                    message: t('line.restored', { name: deleted.name }),
                  }),
                )
                .catch((error) => pushToast({ kind: 'error', message: message(error) })),
          },
        }),
      )
      .catch((error) => pushToast({ kind: 'error', message: message(error) }));
}

/** "OGN · #79", or "Any printing" for a by-name line. */
export function usePrintingLabel() {
  const { t } = useTranslation('wishlists');
  return (line: WishlistLine) =>
    line.set_id !== null && line.card_id !== null
      ? t('line.printing', { set: line.set_id, card: line.card_id })
      : t('line.anyPrinting');
}

/** The finish the line wants; text, never colour alone. */
export function FinishBadge({ line }: { line: WishlistLine }) {
  const { t } = useTranslation('wishlists');
  return (
    <Badge tone={line.foil === 'S' ? 'accent' : 'neutral'}>{t(`line.finish.${line.foil}`)}</Badge>
  );
}

/** The market price of the line ("—" when unpriced), with its date as a tooltip. */
export function MarketValue({ line }: { line: WishlistLine }) {
  const { t } = useTranslation('wishlists');
  if (!line.market) return <span className={styles.muted}>—</span>;
  const title = line.market.as_of
    ? t('line.asOf', { date: formatDate(line.market.as_of) })
    : undefined;
  return (
    <span className={styles.money} title={title}>
      {formatMoney(line.market.value)}
    </span>
  );
}

/** Reached / Not reached for a line with a max price; a muted hint without one (no alert). */
export function AlertState({ line }: { line: WishlistLine }) {
  const { t } = useTranslation('wishlists');
  if (line.max_price === null) {
    return (
      <span className={styles.muted} data-zero="">
        {t('line.noAlert')}
      </span>
    );
  }
  return line.reached ? (
    <Badge tone="success">{t('line.reached')}</Badge>
  ) : (
    <Badge tone="neutral">{t('line.notReached')}</Badge>
  );
}

const isByName = (line: WishlistLine) => line.set_id === null;

/** The copies owned of this version and of the other versions (A6, decision 4). */
export function useOwnedTexts() {
  const { t } = useTranslation('wishlists');
  return (line: WishlistLine) => {
    const { this_version: mine, other_versions: other } = line.owned;
    const foil = mine.foil > 0 ? ` (${t('line.foilPart', { count: mine.foil })})` : '';
    return {
      thisCount: `${mine.total}${foil}`,
      thisText: `${t(isByName(line) ? 'line.ownedAny' : 'line.ownedThis', { count: mine.total })}${foil}`,
      thisZero: mine.total === 0,
      otherCount:
        other.total > 0
          ? `${other.total} (${t('line.otherDetail', { alt: other.alt_art, foil: other.foil })})`
          : '0',
      otherText:
        other.total > 0
          ? `${t('line.other', { count: other.total })} (${t('line.otherDetail', {
              alt: other.alt_art,
              foil: other.foil,
            })})`
          : t('line.other', { count: 0 }),
      otherZero: other.total === 0,
      /** A by-name line counts every printing as this version: it has no other versions. */
      showOther: !isByName(line),
    };
  };
}

/** A note field that saves after a pause (at most 200 characters). */
export function NoteInput({
  line,
  label,
  id,
  disabled,
  onSave,
  className,
}: {
  line: WishlistLine;
  label?: string;
  id?: string;
  disabled: boolean;
  onSave: (note: string | null) => void;
  className?: string;
}) {
  return (
    <DebouncedInput
      id={id}
      className={className}
      aria-label={label}
      maxLength={NOTE_MAX}
      disabled={disabled}
      value={line.note ?? ''}
      delay={500}
      onCommit={(next) => {
        const note = cleanNote(next);
        if (note !== line.note) onSave(note);
      }}
    />
  );
}
