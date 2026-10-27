import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import type { CardSummary } from '@/api/types';
import { BanBadge, CardImage, DomainPips, PriceTag, RarityDot } from '@/components/card';
import { Sparkline } from '@/components/charts/Sparkline';
import { useEnumLabel } from '@/i18n';
import { useCardPrices } from './queries';
import styles from './CatalogPreview.module.css';

export type CatalogPreviewProps = {
  card: CardSummary | null;
  items: CardSummary[];
  search: string;
};

export function CatalogPreview({ card, items, search }: CatalogPreviewProps) {
  const { t } = useTranslation('cards');
  const { typeLabel } = useEnumLabel();

  const prices = useCardPrices(card?.set_id, card?.card_id, '30d');
  const points = prices.data?.points ?? [];
  const sparklineValues = points.map((point) => point.market ?? null);

  if (items.length === 0) {
    return (
      <aside aria-label={t('catalog.preview.title')} className={styles.preview}>
        <p className={styles.empty}>{t('catalog.preview.empty')}</p>
      </aside>
    );
  }

  if (!card) {
    return null;
  }

  const price = card.price;
  const hasPrice = price != null;
  const showFoil = card.foilable && price?.market_foil != null;

  return (
    <aside
      data-testid="catalog-preview"
      aria-label={t('catalog.preview.title')}
      className={styles.preview}
    >
      <div className={styles.image}>
        <CardImage card={card} size="full" decorative />
      </div>

      <h3 className={styles.name}>{card.name}</h3>

      <div className={styles.meta}>
        <RarityDot rarity={card.rarity} showLabel />
        <DomainPips domains={card.domains} size={16} />
        <BanBadge bans={card.bans} variant="compact" />
      </div>

      <p className={styles.eyebrow}>
        {card.set_id} · #{card.card_id} · {typeLabel(card.supertype, card.type)}
      </p>

      {hasPrice && (
        <div className={styles.prices}>
          <div>
            <span className={styles.typeLine}>{t('detail.prices.market')}</span>
            <PriceTag price={price} size="lg" trend={null} />
          </div>
          {showFoil && (
            <div>
              <span className={styles.typeLine}>{t('detail.prices.marketFoil')}</span>
              <PriceTag price={price} foil size="lg" trend={null} />
            </div>
          )}
        </div>
      )}

      {sparklineValues.length > 0 && (
        <div className={styles.trend}>
          <Sparkline values={sparklineValues} label={t('catalog.preview.trend')} />
        </div>
      )}

      {card.owned.total > 0 && (
        <p className={styles.owned}>{t('catalog.owned', { count: card.owned.total })}</p>
      )}

      <Link
        className={styles.open}
        to={{ pathname: `/cards/${card.set_id}/${card.card_id}`, search }}
      >
        {t('catalog.preview.open')}
      </Link>
    </aside>
  );
}
