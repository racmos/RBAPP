import { useTranslation } from 'react-i18next';
import { ErrorState } from '@/components/ui/ErrorState';
import { Skeleton } from '@/components/ui/Skeleton';
import type { Lang } from '@/lib/format';
import { AddProductForm, PriceFacts, ProductHistory, ProductLines } from './ProductSections';
import { ProductThumb } from './ProductThumb';
import { useProduct } from './queries';
import styles from './ProductsDesktop.module.css';

function PanelBody({ id, lang, offline }: { id: number; lang: Lang; offline: boolean }) {
  const { t } = useTranslation('products');
  const query = useProduct(id);
  const product = query.data;
  if (query.isPending) return <Skeleton label={t('loading')} lines={8} />;
  if (!product) return <ErrorState message={t('error')} onRetry={() => void query.refetch()} />;
  return (
    <>
      <ProductThumb product={product} size="full" />
      <h2 className={styles.panelName}>{product.name}</h2>
      <dl className={styles.facts}>
        <PriceFacts product={product} lang={lang} />
      </dl>
      <ProductHistory product={product} lang={lang} level="h3" />
      <ProductLines product={product} lang={lang} level="h3" />
      <AddProductForm product={product} offline={offline} level="h3" />
    </>
  );
}

/** The wide-screen panel (F14-f S4): the selected product, its chart, the user's lines, add. */
export function ProductPanel({
  id,
  lang,
  offline,
}: {
  id: number | null;
  lang: Lang;
  offline: boolean;
}) {
  const { t } = useTranslation('products');
  return (
    <aside className={styles.panel} aria-label={t('panel.title')}>
      {id === null ? (
        <p className={styles.empty}>{t('panel.empty')}</p>
      ) : (
        <PanelBody key={id} id={id} lang={lang} offline={offline} />
      )}
    </aside>
  );
}
