import { useId, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { DeckMissingCard, DeckSectionZone, DeckVsCollection } from '@/api/types';
import { CardImage } from '@/components/card';
import { Button } from '@/components/ui/Button';
import { ErrorState } from '@/components/ui/ErrorState';
import { Icon } from '@/components/ui/Icon';
import { Skeleton } from '@/components/ui/Skeleton';
import { formatMoney, formatNumber } from '@/lib/format';
import { MissingToWishlist } from './MissingToWishlist';
import { useDeckVsCollection } from './queries';
import type { DeckEditor } from './useDeckEditor';
import styles from './DeckCollection.module.css';

/** Summary tiles: copies missing, the cost to complete the deck and the value already owned. */
function Tiles({ data }: { data: DeckVsCollection }) {
  const { t } = useTranslation('decks');
  const copies = data.missing.reduce((sum, item) => sum + item.missing, 0);
  return (
    <dl className={styles.tiles}>
      <div className={styles.tile}>
        <dt>{t('vs.cardsMissing')}</dt>
        <dd>{formatNumber(copies)}</dd>
      </div>
      <div className={styles.tile}>
        <dt>{t('vs.cost')}</dt>
        <dd>{formatMoney(data.cost_eur)}</dd>
        {data.unpriced > 0 && (
          <dd className={styles.tileHint}>{t('vs.unpriced', { count: data.unpriced })}</dd>
        )}
      </div>
      <div className={styles.tile}>
        <dt>{t('vs.owned')}</dt>
        <dd>{formatMoney(data.owned_value)}</dd>
      </div>
    </dl>
  );
}

function MissingRow({ item }: { item: DeckMissingCard }) {
  const { t } = useTranslation('decks');
  const { card } = item;
  return (
    <li className={styles.row} data-key={card.key}>
      <CardImage
        card={{ ...card, energy: null, might: null }}
        size="thumb"
        decorative
        className={styles.thumb}
      />
      <span className={styles.main}>
        <span className={styles.name} data-slot="name">
          {card.name}
        </span>
        <span className={styles.counts} data-slot="counts">
          {t('vs.counts', { need: item.need, have: item.have, missing: item.missing })}
        </span>
      </span>
      <span className={styles.price} data-slot="price">
        {card.market === null ? t('vs.noPrice') : formatMoney(card.market * item.missing)}
      </span>
    </li>
  );
}

/** The missing names grouped by the deck section that first uses them, in the API order. */
function MissingList({ items }: { items: DeckMissingCard[] }) {
  const { t } = useTranslation('decks');
  const groups: { zone: DeckSectionZone; items: DeckMissingCard[] }[] = [];
  for (const item of items) {
    const last = groups[groups.length - 1];
    if (last && last.zone === item.zone) last.items.push(item);
    else groups.push({ zone: item.zone, items: [item] });
  }
  return (
    <div className={styles.groups}>
      {groups.map((group) => (
        <section key={group.zone} aria-label={t(`section.${group.zone}`)}>
          <h3 className={styles.groupTitle}>{t(`section.${group.zone}`)}</h3>
          <ul
            className={styles.rows}
            aria-label={t('vs.missingIn', { section: t(`section.${group.zone}`) })}
          >
            {group.items.map((item) => (
              <MissingRow key={item.card.key} item={item} />
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

/**
 * The Collection view of the deck (F5-f): the current version against the user's collection
 * (`GET /decks/:id/vs-collection`), copies counted per card name across printings, without the
 * workbench. It reads what the server has saved: every autosave invalidates it, so it follows
 * the edits once they are saved. "Add missing to wishlist" puts the missing copies in a list.
 */
export function DeckCollection({ editor }: { editor: DeckEditor }) {
  const { t } = useTranslation('decks');
  const id = useId();
  const { deck, offline, dirty } = editor;
  const query = useDeckVsCollection(deck.id);
  const [picking, setPicking] = useState(false);
  const data = query.data;
  const missingNames = data?.missing.length ?? 0;
  const reason = offline
    ? t('vs.offline')
    : !data
      ? query.isError
        ? t('vs.error')
        : t('vs.loading')
      : missingNames === 0
        ? t('vs.nothingMissing')
        : null;

  let body;
  if (data) {
    body = (
      <>
        <Tiles data={data} />
        {data.missing.length === 0 ? (
          <p className={styles.empty}>
            <Icon name="check" size={18} />
            {t('vs.empty')}
          </p>
        ) : (
          <MissingList items={data.missing} />
        )}
      </>
    );
  } else if (offline) {
    body = <p className={styles.muted}>{t('vs.offlineNoData')}</p>;
  } else if (query.isError) {
    body = <ErrorState message={t('vs.error')} onRetry={() => void query.refetch()} />;
  } else {
    body = <Skeleton label={t('vs.loading')} lines={5} />;
  }

  return (
    <section className={styles.panel} aria-labelledby={id}>
      <div className={styles.header}>
        <h2 id={id}>{t('vs.title')}</h2>
        <Button
          size="sm"
          disabled={reason !== null}
          title={reason ?? undefined}
          aria-describedby={reason ? `${id}-reason` : undefined}
          aria-haspopup="dialog"
          onClick={() => setPicking(true)}
        >
          <Icon name="bookmark" size={16} />
          {t('vs.toWishlist')}
        </Button>
        {reason && (
          <span id={`${id}-reason`} className="sr-only">
            {reason}
          </span>
        )}
      </div>
      <p className={styles.muted}>{t('vs.hint')}</p>
      {dirty && <p className={styles.muted}>{t('vs.stale')}</p>}
      {body}
      {data && (
        <MissingToWishlist
          deckId={deck.id}
          names={missingNames}
          open={picking}
          onClose={() => setPicking(false)}
        />
      )}
    </section>
  );
}
