import type { TFunction } from 'i18next';
import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';
import { ApiError } from '@/api/errors';
import type { MissingToWishlistResult } from '@/api/types';
import { useOffline } from '@/auth';
import { Button } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import { Modal } from '@/components/ui/Modal';
import { Skeleton } from '@/components/ui/Skeleton';
import { pushToast } from '@/components/ui/toastStore';
import { translateError } from '@/i18n';
import { useWishlists } from '@/wishlists';
import { useMissingToWishlist } from './queries';
import styles from './DeckCollection.module.css';

type Props = {
  deckId: number;
  /** Missing card names: one wishlist line each. */
  names: number;
  open: boolean;
  onClose: () => void;
};

/** The toast sentence of a result: added, raised, left out because the list is full or
 *  capped at 99 copies. */
function resultMessage(t: TFunction<'decks'>, result: MissingToWishlistResult) {
  const name = result.wishlist.name;
  const full = result.skipped.filter((item) => item.reason === 'list_full').length;
  const capped = result.skipped.filter((item) => item.reason === 'qty_cap').length;
  const parts: string[] = [];
  if (result.added > 0) parts.push(t('vs.result.added', { count: result.added, name }));
  if (result.merged > 0)
    parts.push(
      result.added > 0
        ? t('vs.result.merged', { count: result.merged })
        : t('vs.result.updatedOnly', { count: result.merged, name }),
    );
  if (result.added === 0 && result.merged === 0 && full === 0)
    parts.push(t('vs.result.nothingNew', { name }));
  if (full > 0) parts.push(t('vs.result.listFull', { count: full }));
  if (capped > 0) parts.push(t('vs.result.capped', { count: capped }));
  return { message: parts.join(' '), partial: full > 0 || capped > 0 };
}

/**
 * "Add missing to wishlist" (F5-f, owner decision 5 of the wishlists design): the user picks a
 * list (the starred one first) and each missing card goes there with only the copies the deck
 * misses (`POST /decks/:id/missing-to-wishlist`). A list holds at most 100 cards: what does not
 * fit is reported in the result toast, which opens the list.
 */
export function MissingToWishlist({ deckId, names, open, onClose }: Props) {
  const { t, i18n } = useTranslation('decks');
  const { t: tCommon } = useTranslation('common');
  const navigate = useNavigate();
  const offline = useOffline();
  const lists = useWishlists();
  const send = useMissingToWishlist(deckId);
  const items = lists.data?.items ?? [];
  const starred = items.find((list) => list.is_default) ?? items[0] ?? null;
  const [chosen, setChosen] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const target = items.find((list) => list.id === chosen) ?? starred;

  const close = () => {
    setError(null);
    setChosen(null);
    onClose();
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!target) return;
    setError(null);
    send.mutate(target.id, {
      onSuccess: (result) => {
        const { message, partial } = resultMessage(t, result);
        close();
        pushToast({
          kind: partial ? 'info' : 'success',
          message,
          duration: partial ? 0 : 8000,
          action: {
            label: t('vs.openList'),
            onAction: () => void navigate(`/collection/wishlists?list=${result.wishlist.id}`),
          },
        });
      },
      onError: (failure) => {
        if (failure instanceof ApiError && failure.status === 404) {
          setError(t('vs.listGone'));
          setChosen(null);
          void lists.refetch();
        } else setError(translateError(failure, i18n));
      },
    });
  };

  return (
    <Modal open={open} onClose={close} title={t('vs.pickTitle')}>
      <form className={styles.form} onSubmit={submit} noValidate>
        <p>{t('vs.willAdd', { count: names })}</p>
        <p className={styles.muted}>{t('vs.limitNote')}</p>
        {lists.isPending ? (
          <Skeleton label={t('vs.loadingLists')} lines={2} />
        ) : lists.isError ? (
          <p role="alert">{t('vs.listsError')}</p>
        ) : (
          <fieldset className={styles.lists}>
            <legend className={styles.legend}>{t('vs.pickList')}</legend>
            {items.map((list) => (
              <label key={list.id} className={styles.option}>
                <input
                  type="radio"
                  name="missing-wishlist"
                  value={list.id}
                  checked={target?.id === list.id}
                  onChange={() => setChosen(list.id)}
                />
                <span className={styles.optionName}>{list.name}</span>
                {list.is_default && (
                  <Icon name="star" size={16} className={styles.star} title={t('vs.defaultList')} />
                )}
                <span className={styles.optionCount}>
                  {t('vs.listCount', { count: list.line_count })}
                </span>
              </label>
            ))}
          </fieldset>
        )}
        {error && (
          <p role="alert" className={styles.error}>
            {error}
          </p>
        )}
        <div className={styles.actions}>
          <Button variant="ghost" onClick={close}>
            {tCommon('actions.cancel')}
          </Button>
          <Button type="submit" pending={send.isPending} disabled={offline || !target}>
            {t('vs.add')}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
