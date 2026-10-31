import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';
import { ApiError } from '@/api/errors';
import { useOffline } from '@/auth';
import { ErrorState } from '@/components/ui/ErrorState';
import { PageHeader } from '@/components/ui/PageHeader';
import { Skeleton } from '@/components/ui/Skeleton';
import { useDocumentTitle } from '@/i18n';
import { NotFound } from '@/shell/NotFound';

import { AddProductForm, PriceFacts, ProductHistory, ProductLines } from './ProductSections';
import { ProductThumb } from './ProductThumb';
import { useProduct } from './queries';
import styles from './ProductDetail.module.css';

/** `/products/:id` (F14-e S3): a full page on a phone. */
export function ProductDetail() {
  const { t } = useTranslation('products');
  const { t: tCommon } = useTranslation('common');
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
          <PriceFacts product={product} />
        </dl>
      </div>
      {product.description && <p className={styles.muted}>{product.description}</p>}

      <ProductHistory product={product} />

      <ProductLines product={product} />

      <AddProductForm product={product} offline={offline} />
    </div>
  );
}
