import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import type { Wishlist, WishlistLine, WishlistMoveMode } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { Select } from '@/components/ui/Select';
import { Sheet } from '@/components/ui/Sheet';
import { pushToast } from '@/components/ui/toastStore';
import { useWishlistError } from './errors';
import { useMoveWishlistLines } from './queries';
import styles from './Wishlists.module.css';

/**
 * Moves or copies a line to another list (F3-j); the toast says how many lines were created,
 * merged into a line the list already had, or skipped because that line was at 99.
 */
export function MoveSheet({
  line,
  lists,
  offline,
  onClose,
}: {
  line: WishlistLine;
  /** Every list of the user; the line's own list is left out of the choice. */
  lists: Wishlist[];
  offline: boolean;
  onClose: () => void;
}) {
  const { t } = useTranslation('wishlists');
  const message = useWishlistError();
  const move = useMoveWishlistLines();
  const others = lists.filter((list) => list.id !== line.list_id);
  const [target, setTarget] = useState<number | null>(others[0]?.id ?? null);
  const [mode, setMode] = useState<WishlistMoveMode>('move');
  const [error, setError] = useState<string | null>(null);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (target === null || offline) return;
    setError(null);
    move
      .mutateAsync({
        listId: line.list_id,
        body: { line_ids: [line.id], to_list_id: target, mode },
      })
      .then((result) => {
        pushToast({ kind: 'success', message: t('move.result', result) });
        onClose();
      })
      .catch((failure) => setError(message(failure)));
  };

  return (
    <Sheet open onClose={onClose} title={t('move.title', { name: line.name })}>
      <form className={styles.form} onSubmit={submit} noValidate>
        {others.length === 0 ? (
          <p className={styles.note}>{t('move.noOther')}</p>
        ) : (
          <Field label={t('move.to')}>
            {(control) => (
              <Select
                {...control}
                value={target ?? ''}
                disabled={offline}
                onChange={(event) => setTarget(Number(event.target.value))}
              >
                {others.map((list) => (
                  <option key={list.id} value={list.id}>
                    {`${list.name} (${t('count', { count: list.line_count })})`}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        )}
        <SegmentedControl
          label={t('move.mode')}
          showLabel
          options={[
            { value: 'move', label: t('move.move') },
            { value: 'copy', label: t('move.copy') },
          ]}
          value={mode}
          disabled={offline}
          onChange={setMode}
        />
        <p className={styles.note}>{t('move.mergeHint')}</p>
        {error && (
          <p role="alert" className={styles.alert}>
            {error}
          </p>
        )}
        <Button type="submit" block disabled={offline || target === null} pending={move.isPending}>
          {t(mode === 'move' ? 'move.move' : 'move.copy')}
        </Button>
      </form>
    </Sheet>
  );
}
