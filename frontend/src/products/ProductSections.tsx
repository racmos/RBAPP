import { useId, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import type { PriceRange } from '@/api/endpoints';
import type { ProductDetail } from '@/api/types';
import { PriceChart } from '@/components/charts';
import { Button } from '@/components/ui/Button';
import { ErrorState } from '@/components/ui/ErrorState';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { Skeleton } from '@/components/ui/Skeleton';
import { pushToast } from '@/components/ui/toastStore';
import { translateError } from '@/i18n';
import { formatMoney, formatPct } from '@/lib/format';
import { asChartPoints } from './format';
import { useAddProduct, useProductPrices } from './queries';
import styles from './ProductDetail.module.css';

const RANGES: PriceRange[] = ['30d', '90d', '1y', 'all'];

/** Section headings: `h2` on the product page, `h3` under the product name of the wide panel. */
type Level = 'h2' | 'h3';

/** The price and its 7 and 30-day changes, as the product page and the wide panel show them. */
export function PriceFacts({ product }: { product: ProductDetail }) {
  const { t } = useTranslation('products');
  const pct = (value: number | null | undefined) =>
    value === null || value === undefined ? '—' : formatPct(value);
  return (
    <>
      <div>
        <dt>{t('detail.price')}</dt>
        <dd>{product.price ? formatMoney(product.price.value) : t('unpriced')}</dd>
      </div>
      {product.price && (
        <>
          <div>
            <dt>{t('detail.change7d')}</dt>
            <dd>{pct(product.price.change_7d_pct)}</dd>
          </div>
          <div>
            <dt>{t('detail.change30d')}</dt>
            <dd>{pct(product.price.change_30d_pct)}</dd>
          </div>
        </>
      )}
    </>
  );
}

/** The price history (90 days first) with its range control (F14-e S3). */
export function ProductHistory({
  product,
  level: Heading = 'h2',
}: {
  product: ProductDetail;
  level?: Level;
}) {
  const { t } = useTranslation('products');
  const { t: tCards } = useTranslation('cards');
  const headingId = useId();
  const [range, setRange] = useState<PriceRange>('90d');
  const prices = useProductPrices(product.id, range);
  const points = prices.data ? asChartPoints(prices.data.points) : [];

  let body;
  if (prices.isPending) body = <Skeleton label={tCards('chart.loading')} lines={6} />;
  else if (prices.isError) {
    body = <ErrorState message={t('error')} onRetry={() => void prices.refetch()} />;
  } else if (points.length === 0) body = <p className={styles.muted}>{tCards('chart.empty')}</p>;
  else {
    body = (
      <div aria-busy={prices.isFetching || undefined}>
        <PriceChart points={points} series={['market']} title={product.name} />
      </div>
    );
  }

  return (
    <section aria-labelledby={headingId} className={styles.section}>
      <div className={styles.sectionHead}>
        <Heading id={headingId}>{t('detail.history')}</Heading>
        <SegmentedControl
          label={tCards('chart.range.label')}
          options={RANGES.map((value) => ({ value, label: tCards(`chart.range.${value}`) }))}
          value={range}
          onChange={setRange}
        />
      </div>
      {body}
    </section>
  );
}

/** The caller's lines of the product, when there are any. */
export function ProductLines({
  product,
  level: Heading = 'h2',
}: {
  product: ProductDetail;
  level?: Level;
}) {
  const { t } = useTranslation('products');
  const headingId = useId();
  if (product.lines.length === 0) return null;
  return (
    <section aria-labelledby={headingId} className={styles.section}>
      <Heading id={headingId}>{t('detail.yourLines')}</Heading>
      <ul className={styles.lines}>
        {product.lines.map((line) => (
          <li key={line.id}>
            <span>
              {t('line.quantity')}: {line.quantity}
            </span>
            <span>
              {t('line.purchasePrice')}:{' '}
              {line.purchase_price === null ? '—' : formatMoney(line.purchase_price)}
            </span>
            <span>
              {t('line.value')}: {line.value === null ? t('unpriced') : formatMoney(line.value)}
            </span>
            {line.note && <span className={styles.muted}>{line.note}</span>}
          </li>
        ))}
      </ul>
    </section>
  );
}

/** "Add to my products": quantity, purchase price and note (F14-e S3). */
export function AddProductForm({
  product,
  offline,
  level: Heading = 'h2',
}: {
  product: ProductDetail;
  offline: boolean;
  level?: Level;
}) {
  const { t, i18n } = useTranslation('products');
  const { t: tCommon } = useTranslation('common');
  const headingId = useId();
  const add = useAddProduct();
  const [quantity, setQuantity] = useState('1');
  const [price, setPrice] = useState('');
  const [note, setNote] = useState('');
  const qty = Number(quantity);
  const valid = Number.isInteger(qty) && qty >= 1 && qty <= 9999;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!valid) return;
    add.mutate(
      {
        product_id: product.id,
        quantity: qty,
        purchase_price: price === '' ? null : Number(price),
        note: note.trim() || null,
      },
      {
        onSuccess: ({ merged }) => {
          pushToast({ kind: 'success', message: t(merged ? 'add.merged' : 'add.added') });
          setQuantity('1');
          setPrice('');
          setNote('');
        },
        onError: (error) => pushToast({ kind: 'error', message: translateError(error, i18n) }),
      },
    );
  };

  return (
    <form aria-labelledby={headingId} className={styles.section} onSubmit={submit}>
      <Heading id={headingId}>{t('add.title')}</Heading>
      {offline && <p className={styles.muted}>{tCommon('offline.editDisabled')}</p>}
      <Field label={t('line.quantity')}>
        {(control) => (
          <Input
            {...control}
            type="number"
            inputMode="numeric"
            min={1}
            max={9999}
            required
            disabled={offline}
            value={quantity}
            onChange={(event) => setQuantity(event.target.value)}
          />
        )}
      </Field>
      <Field label={t('line.purchasePrice')}>
        {(control) => (
          <Input
            {...control}
            type="number"
            inputMode="decimal"
            min={0}
            step="0.01"
            disabled={offline}
            value={price}
            onChange={(event) => setPrice(event.target.value)}
          />
        )}
      </Field>
      <Field label={t('line.note')}>
        {(control) => (
          <Input
            {...control}
            maxLength={200}
            disabled={offline}
            value={note}
            onChange={(event) => setNote(event.target.value)}
          />
        )}
      </Field>
      <Button type="submit" disabled={offline || !valid} pending={add.isPending}>
        {t('add.submit')}
      </Button>
    </form>
  );
}
