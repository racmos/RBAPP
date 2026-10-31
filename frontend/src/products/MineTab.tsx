import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { MyProducts, OwnedProductLine } from '@/api/types';
import { Stepper } from '@/collection/Stepper';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Skeleton } from '@/components/ui/Skeleton';
import { formatMoney } from '@/lib/format';
import { ProductLineSheet } from './ProductLineSheet';
import { ProductThumb } from './ProductThumb';
import { useMyProducts } from './queries';
import { useProductLineSaver } from './useProductLineSaver';
import styles from './ProductsPage.module.css';

function OwnedLine({
  line,
  offline,
  onOpen,
}: {
  line: OwnedProductLine;
  offline: boolean;
  onOpen: () => void;
}) {
  const { t } = useTranslation('products');
  const save = useProductLineSaver(line.id);
  const { product } = line;
  const money = (value: number | null | undefined) =>
    value === null || value === undefined ? t('unpriced') : formatMoney(value);
  return (
    <article className={styles.line} aria-label={product.name}>
      <button type="button" className={styles.lineOpen} aria-haspopup="dialog" onClick={onOpen}>
        <ProductThumb product={product} size="thumb" decorative />
        <span className={styles.lineBody}>
          <span className={styles.name}>{product.name}</span>{' '}
          <span className={styles.meta}>{product.kind ? t(`kind.${product.kind}`) : ''}</span>{' '}
          <span className={styles.meta}>
            {t('detail.price')}: <span>{money(product.price?.value)}</span>
          </span>
        </span>{' '}
        <span className={styles.lineValue}>{money(line.value)}</span>
      </button>
      <Stepper
        label={t('line.quantity')}
        value={line.quantity}
        min={1}
        max={9999}
        disabled={offline}
        onCommit={(quantity) => void save({ quantity })}
      />
    </article>
  );
}

/** The total band, the unpriced count, the hint that it is separate and the offline note. */
export function MineSummary({ total, offline }: { total: MyProducts['total']; offline: boolean }) {
  const { t } = useTranslation('products');
  const { t: tCommon } = useTranslation('common');
  return (
    <>
      <dl className={styles.band}>
        <div>
          <dt>{t('total.title')}</dt>
          <dd>{formatMoney(total.value)}</dd>
        </div>
        <div>
          <dt>{t('total.lines')}</dt>
          <dd>{total.lines}</dd>
        </div>
      </dl>
      {total.unpriced > 0 && (
        <p className={styles.note}>{t('total.unpriced', { count: total.unpriced })}</p>
      )}
      <p className={styles.note}>{t('total.separate')}</p>
      {offline && <p className={styles.note}>{tCommon('offline.editDisabled')}</p>}
    </>
  );
}

/** "My products": the total band, the hint that it is separate, the owned lines (F14-e S2). */
export function MineTab({ offline, onBrowse }: { offline: boolean; onBrowse: () => void }) {
  const { t } = useTranslation('products');
  const mine = useMyProducts();
  const [openId, setOpenId] = useState<number | null>(null);

  if (mine.isPending) return <Skeleton label={t('loading')} lines={5} />;
  if (mine.isError && !mine.data) {
    return <ErrorState message={t('error')} onRetry={() => void mine.refetch()} />;
  }
  const { items, total } = mine.data;
  if (items.length === 0) {
    return (
      <EmptyState
        icon="gift"
        title={t('empty.mine')}
        action={{ label: t('empty.goCatalog'), onAction: onBrowse }}
      />
    );
  }
  const open = openId === null ? undefined : items.find((line) => line.id === openId);

  return (
    <>
      <MineSummary total={total} offline={offline} />
      <ul className={styles.lines} aria-busy={mine.isFetching || undefined}>
        {items.map((line) => (
          <li key={line.id}>
            <OwnedLine line={line} offline={offline} onOpen={() => setOpenId(line.id)} />
          </li>
        ))}
      </ul>
      {open && <ProductLineSheet line={open} onClose={() => setOpenId(null)} offline={offline} />}
    </>
  );
}
