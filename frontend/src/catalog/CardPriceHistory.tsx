import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { PriceRange } from '@/api/endpoints';
import { ErrorState } from '@/components/ui/ErrorState';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { Skeleton } from '@/components/ui/Skeleton';
import type { Lang } from '@/lib/format';
import { readStorage, writeStorage } from '@/lib/storage';
import { PriceChart } from '@/components/charts';
import { useCardPrices } from './queries';
import styles from './CardPriceHistory.module.css';

const STORAGE_KEY = 'rb_price_range';
const RANGES: PriceRange[] = ['30d', '90d', '1y', 'all'];

function storedRange(): PriceRange {
  const value = readStorage(STORAGE_KEY);
  if (value && (RANGES as string[]).includes(value)) return value as PriceRange;
  return '90d';
}

type CardPriceHistoryProps = {
  setId: string;
  cardId: string;
  foilable: boolean;
  name: string;
};

export function CardPriceHistory({ setId, cardId, foilable, name }: CardPriceHistoryProps) {
  const { t, i18n } = useTranslation('cards');
  const lang = (i18n.language.split('-')[0] === 'en' ? 'en' : 'es') as Lang;
  const [range, setRange] = useState<PriceRange>(() => storedRange());
  const { data, isPending, isError, error, refetch } = useCardPrices(setId, cardId, range);

  const options = useMemo(
    () => RANGES.map((value) => ({ value, label: t(`chart.range.${value}`) })),
    [t],
  );

  const series: ('market' | 'market_foil')[] = foilable ? ['market', 'market_foil'] : ['market'];

  function handleChange(next: PriceRange) {
    setRange(next);
    writeStorage(STORAGE_KEY, next);
  }

  return (
    <section aria-labelledby="price-history-title" className={styles.section}>
      <div className={styles.header}>
        <h2 id="price-history-title" className={styles.title}>
          {t('chart.title')}
        </h2>
        <SegmentedControl
          label={t('chart.range.label')}
          options={options}
          value={range}
          onChange={handleChange}
          disabled={isPending && !data}
        />
      </div>

      {isPending && !data && <Skeleton label={t('chart.loading')} lines={8} />}

      {isError && (
        <ErrorState message={error?.message ?? t('chart.loading')} onRetry={() => refetch()} />
      )}

      {data && (
        <div className={isPending ? styles.dimmed : undefined} aria-busy={isPending || undefined}>
          <PriceChart points={data.points} series={series} lang={lang} title={name} />
        </div>
      )}
    </section>
  );
}
