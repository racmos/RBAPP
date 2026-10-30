import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import type { CollectionGroup } from '@/api/types';
import { useCardDetail, useCardPrices } from '@/catalog';
import { CardImage } from '@/components/card';
import { PriceChart } from '@/components/charts';
import { SidePanel } from '@/components/ui/SidePanel';
import { Skeleton } from '@/components/ui/Skeleton';
import { formatMoney, type Lang } from '@/lib/format';
import styles from './CollectionPanel.module.css';

/** The wide-screen panel of the selected card: price chart, its lines and the decks using it (F3-h S6). */
export function CollectionPanel({ group, lang }: { group: CollectionGroup | null; lang: Lang }) {
  const { t } = useTranslation('collection');
  const card = group?.card;
  const prices = useCardPrices(card?.set_id, card?.card_id, '30d');
  const detail = useCardDetail(card?.set_id, card?.card_id);

  if (!group || !card) {
    return (
      <DetailPanel label={t('panel.title')}>
        <p className={styles.empty}>{t('panel.empty')}</p>
      </DetailPanel>
    );
  }

  const series: ('market' | 'market_foil')[] = group.foil ? ['market_foil'] : ['market'];
  const decks = detail.data?.in_decks ?? [];

  return (
    <DetailPanel label={t('panel.title')}>
      <div className={styles.art}>
        <CardImage card={card} size="full" decorative />
      </div>
      <h2 className={styles.name}>{card.name}</h2>
      <p className={styles.meta}>
        {card.set_id} · #{card.card_id}
        {group.foil ? ` · ${t('foil')}` : ''}
      </p>
      <p className={styles.totals}>
        {t('qtyBadge', { count: group.qty })} ·{' '}
        {group.value === null ? '—' : formatMoney(group.value, lang)}
      </p>

      <section aria-label={t('panel.chart')}>
        <h3 className={styles.heading}>{t('panel.chart')}</h3>
        {prices.isPending && <Skeleton label={t('loading')} lines={5} />}
        {prices.data && (
          <PriceChart points={prices.data.points} series={series} lang={lang} title={card.name} />
        )}
      </section>

      <section aria-label={t('panel.lines')}>
        <h3 className={styles.heading}>{t('panel.lines')}</h3>
        <ul className={styles.lines}>
          {group.lines.map((line, index) => (
            <li key={line.id}>
              {t('line.legend', { index: index + 1 })}: {t('qtyBadge', { count: line.qty })}
              {line.condition ? ` · ${line.condition}` : ''}
              {line.language ? ` · ${line.language}` : ''}
              {line.selling ? ` · ${t('selling.tag', { count: line.sell_qty })}` : ''}
            </li>
          ))}
        </ul>
      </section>

      <section aria-label={t('panel.decks')}>
        <h3 className={styles.heading}>{t('panel.decks')}</h3>
        {decks.length === 0 ? (
          <p className={styles.muted}>{t('panel.noDecks')}</p>
        ) : (
          <ul className={styles.lines}>
            {decks.map((deck) => (
              <li key={deck.deck_id}>
                {t('panel.decksCount', { name: deck.name, qty: deck.qty })}
              </li>
            ))}
          </ul>
        )}
      </section>

      <Link className={styles.open} to={`/cards/${card.set_id}/${card.card_id}`}>
        {t('panel.openDetail')}
      </Link>
    </DetailPanel>
  );
}

/** The third column folds away like the filters (owner feedback S23). */
function DetailPanel({ label, children }: { label: string; children: ReactNode }) {
  return (
    <SidePanel
      id="collection-detail"
      kind="detail"
      side="end"
      label={label}
      className={styles.panel}
      contentClassName={styles.body}
    >
      {children}
    </SidePanel>
  );
}
