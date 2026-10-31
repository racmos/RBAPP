import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import type { CardPrice } from '@/api/types';
import { formatMoney, formatPct } from '@/lib/format';
import { Icon } from '@/components/ui/Icon';
import styles from './PriceTag.module.css';

type PriceTagProps = {
  price: CardPrice | null;
  foil?: boolean;
  trend?: '7d' | '30d' | null;
  size?: 'sm' | 'md' | 'lg';
};

function trendDirection(value: number): 'up' | 'down' | 'flat' {
  if (value > 0) return 'up';
  if (value < 0) return 'down';
  return 'flat';
}

export function PriceTag({ price, foil, trend = '7d', size = 'md' }: PriceTagProps) {
  const { t } = useTranslation('cards');

  const amount = price ? (foil ? price.market_foil : price.market) : null;
  const trendValue = price ? (trend === '30d' ? price.trend_30d_pct : price.trend_7d_pct) : null;

  const days = trend === '30d' ? 30 : 7;
  const direction = trendValue !== null ? trendDirection(trendValue) : null;

  const srText = useMemo(() => {
    if (trendValue === null || direction === null) return null;
    return t(`trend.${direction}`, {
      value: formatPct(Math.abs(trendValue)).replace(/[+-]/g, ''),
      days,
    });
  }, [trendValue, direction, t, days]);

  return (
    <span className={[styles.tag, styles[size]].filter(Boolean).join(' ')}>
      <span className={amount === null ? styles.muted : styles.amount}>
        {amount !== null ? formatMoney(amount) : t('price.none')}
      </span>
      {trendValue !== null && direction !== null && (
        <span
          className={[styles.chip, styles[direction]].filter(Boolean).join(' ')}
          aria-label={srText ?? undefined}
        >
          <span
            className={[
              styles.icon,
              direction === 'up' && styles.upIcon,
              direction === 'down' && styles.downIcon,
            ]
              .filter(Boolean)
              .join(' ')}
            aria-hidden="true"
          >
            <Icon name={direction === 'flat' ? 'minus' : 'arrow'} size={12} />
          </span>
          <span aria-hidden="true">{formatPct(trendValue)}</span>
          {srText && <span className={styles.srOnly}>{srText}</span>}
        </span>
      )}
    </span>
  );
}
