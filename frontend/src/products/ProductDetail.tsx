import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';
import type { PriceRange } from '@/api/endpoints';
import { ApiError } from '@/api/errors';
import type { ProductDetail as Detail } from '@/api/types';
import { useOffline } from '@/auth';
import { PriceChart } from '@/components/charts';
import { Button } from '@/components/ui/Button';
import { ErrorState } from '@/components/ui/ErrorState';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { PageHeader } from '@/components/ui/PageHeader';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { Skeleton } from '@/components/ui/Skeleton';
import { pushToast } from '@/components/ui/toastStore';
import { translateError, useDocumentTitle } from '@/i18n';
import { formatMoney, formatPct, type Lang } from '@/lib/format';
import { NotFound } from '@/shell/NotFound';
import { asChartPoints, langOf } from './format';
import { ProductThumb } from './ProductThumb';
import { useAddProduct, useProduct, useProductPrices } from './queries';
import styles from './ProductDetail.module.css';

const RANGES: PriceRange[] = ['30d', '90d', '1y', 'all'];

function History({ product, lang }: { product: Detail; lang: Lang }) {
  const { t } = useTranslation('products');
  const { t: tCards } = useTranslation('cards');
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
        <PriceChart points={points} series={['market']} lang={lang} title={product.name} />
      </div>
    );
  }

  return (
    <section aria-labelledby="product-history" className={styles.section}>
      <div className={styles.sectionHead}>
        <h2 id="product-history">{t('detail.history')}</h2>
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

function AddForm({ product, offline }: { product: Detail; offline: boolean }) {
  const { t, i18n } = useTranslation('products');
  const { t: tCommon } = useTranslation('common');
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
    <form aria-labelledby="product-add" className={styles.section} onSubmit={submit}>
      <h2 id="product-add">{t('add.title')}</h2>
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

/** `/products/:id` (F14-e S3): a full page on a phone. */
export function ProductDetail() {
  const { t, i18n } = useTranslation('products');
  const { t: tCommon } = useTranslation('common');
  const lang = langOf(i18n.language);
  const offline = useOffline();
  const id = Number(useParams().id);
  const query = useProduct(id);
  const product = query.data;
  useDocumentTitle(product?.name ?? t('title'));

  const missing =
    !Number.isInteger(id) ||
    id < 1 ||
    (query.error instanceof ApiError && query.error.status === 404);
  if (missing) return <NotFound />;

  const back = (
    <Link to="/products" className={styles.back}>
      {tCommon('actions.back')}
    </Link>
  );
  if (query.isPending) {
    return (
      <div className={styles.page}>
        {back}
        <Skeleton label={t('loading')} lines={8} />
      </div>
    );
  }
  if (!product) {
    return (
      <div className={styles.page}>
        {back}
        <ErrorState message={t('error')} onRetry={() => void query.refetch()} />
      </div>
    );
  }

  const money = (value: number | null) =>
    value === null ? t('unpriced') : formatMoney(value, lang);
  const pct = (value: number | null | undefined) =>
    value === null || value === undefined ? '—' : formatPct(value, lang);

  return (
    <div className={styles.page}>
      {back}
      <PageHeader title={product.name} />
      <div className={styles.top}>
        <ProductThumb product={product} size="full" />
        <dl className={styles.facts}>
          <div>
            <dt>{t('filters.kind')}</dt>
            <dd>{product.kind ? t(`kind.${product.kind}`) : '—'}</dd>
          </div>
          <div>
            <dt>{t('filters.set')}</dt>
            <dd>{product.set_id ?? '—'}</dd>
          </div>
          <div>
            <dt>{t('detail.price')}</dt>
            <dd>{money(product.price?.value ?? null)}</dd>
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
        </dl>
      </div>
      {product.description && <p className={styles.muted}>{product.description}</p>}

      <History product={product} lang={lang} />

      {product.lines.length > 0 && (
        <section aria-labelledby="product-lines" className={styles.section}>
          <h2 id="product-lines">{t('detail.yourLines')}</h2>
          <ul className={styles.lines}>
            {product.lines.map((line) => (
              <li key={line.id}>
                <span>
                  {t('line.quantity')}: {line.quantity}
                </span>
                <span>
                  {t('line.purchasePrice')}:{' '}
                  {line.purchase_price === null ? '—' : formatMoney(line.purchase_price, lang)}
                </span>
                <span>
                  {t('line.value')}: {money(line.value)}
                </span>
                {line.note && <span className={styles.muted}>{line.note}</span>}
              </li>
            ))}
          </ul>
        </section>
      )}

      <AddForm product={product} offline={offline} />
    </div>
  );
}
