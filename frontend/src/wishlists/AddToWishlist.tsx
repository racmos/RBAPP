import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router';
import type { InWishlist, Wishlist } from '@/api/types';
import { useOffline } from '@/auth';
import { Button } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import { Sheet } from '@/components/ui/Sheet';
import { pushToast } from '@/components/ui/toastStore';
import { useWishlistError } from './errors';
import { useAddWishlistLine, useWishlists } from './queries';
import styles from './AddToWishlist.module.css';

type Props = {
  card: { set_id: string; card_id: string; name: string };
  /** The user's lists that hold this printing now (`CardDetail.in_wishlists`), named with links. */
  inWishlists?: InWishlist[];
  /** The panel and heading look of the page that hosts it. */
  className?: string;
  titleClassName?: string;
};

/**
 * "Add to wishlist" of the card detail (F3-j): one tap adds one copy of this printing, any
 * finish, to the default (starred) list, named on the button; "Choose list…" picks another.
 * Reading the lists creates the default list of a user who has none yet (`GET /wishlists`).
 * Above the buttons, "In wishlists:" names the lists that hold the card now, each a link to it
 * (F3-j follow-ups); every wishlist write refreshes the card detail, so a new list shows at once.
 */
export function AddToWishlist({ card, inWishlists = [], className, titleClassName }: Props) {
  const { t } = useTranslation('wishlists');
  const navigate = useNavigate();
  const offline = useOffline();
  const message = useWishlistError();
  const lists = useWishlists();
  const add = useAddWishlistLine();
  const [choosing, setChoosing] = useState(false);
  const items = lists.data?.items ?? [];
  const target = items.find((list) => list.is_default) ?? items[0] ?? null;

  const addTo = (list: Wishlist) =>
    add
      .mutateAsync({
        listId: list.id,
        body: { set_id: card.set_id, card_id: card.card_id, foil: 'any', qty: 1 },
      })
      .then(({ merged }) => {
        setChoosing(false);
        pushToast({
          kind: 'success',
          message: t(merged ? 'detail.merged' : 'detail.added', { name: list.name }),
          duration: 8000,
          action: {
            label: t('detail.open'),
            onAction: () => void navigate(`/collection/wishlists?list=${list.id}`),
          },
        });
      })
      .catch((error) => pushToast({ kind: 'error', message: message(error) }));

  const busy = offline || !target || add.isPending;
  return (
    <section aria-labelledby="wishlist-add-title" className={className}>
      <h2 id="wishlist-add-title" className={titleClassName}>
        {t('detail.title')}
      </h2>
      {inWishlists.length > 0 && (
        <p className={styles.inLists}>
          {t('detail.inWishlists')}{' '}
          {inWishlists.map((list, index) => (
            <span key={list.id}>
              {index > 0 && ', '}
              <Link to={`/collection/wishlists?list=${list.id}`} className={styles.inListLink}>
                {t('detail.inWishlist', { name: list.name, qty: list.qty })}
              </Link>
            </span>
          ))}
        </p>
      )}
      <div className={styles.actions}>
        <Button
          size="sm"
          disabled={busy}
          pending={add.isPending && !choosing}
          onClick={() => target && void addTo(target)}
        >
          <Icon name="bookmark" size={16} />
          {target ? t('detail.add', { name: target.name }) : t('detail.addFallback')}
        </Button>
        <Button
          variant="ghost"
          size="sm"
          aria-haspopup="dialog"
          disabled={offline || items.length === 0}
          onClick={() => setChoosing(true)}
        >
          {t('detail.choose')}
        </Button>
      </div>
      <p className={styles.hint}>{t('detail.hint')}</p>
      <Sheet
        open={choosing}
        onClose={() => setChoosing(false)}
        title={t('detail.chooseTitle', { name: card.name })}
      >
        <ul className={styles.lists}>
          {items.map((list) => (
            <li key={list.id}>
              <button
                type="button"
                className={styles.list}
                disabled={offline || add.isPending}
                onClick={() => void addTo(list)}
              >
                <span className={styles.name}>{list.name}</span>
                {list.is_default && (
                  <Icon name="star" size={16} className={styles.star} title={t('menu.default')} />
                )}
                <span className={styles.count}>{t('count', { count: list.line_count })}</span>
              </button>
            </li>
          ))}
        </ul>
      </Sheet>
    </section>
  );
}
