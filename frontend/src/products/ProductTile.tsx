import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import type { ProductSummary } from '@/api/types';
import { PriceTag } from '@/components/card';
import { asCardPrice } from './format';
import { ProductThumb } from './ProductThumb';
import styles from './ProductTile.module.css';

/** A catalog tile: image or placeholder, name, kind, price with the 7-day change, owned badge. */
export function ProductTile({ product }: { product: ProductSummary }) {
  const { t } = useTranslation('products');
  return (
    <Link to={`/products/${product.id}`} className={styles.tile}>
      {/* Blocks, so the link's accessible name keeps its words apart. */}
      <div className={styles.art}>
        <ProductThumb product={product} size="tile" decorative />
        {product.owned_qty > 0 && (
          <span className={styles.owned}>
            <span aria-hidden="true">×{product.owned_qty}</span>
            <span className="sr-only">{t('owned', { count: product.owned_qty })}</span>
          </span>
        )}
      </div>
      <div className={styles.name}>{product.name}</div>
      <div className={styles.kind}>{product.kind ? t(`kind.${product.kind}`) : ''}</div>
      <div>
        {product.price ? (
          <PriceTag price={asCardPrice(product.price)} trend="7d" size="sm" />
        ) : (
          <span className={styles.unpriced}>{t('unpriced')}</span>
        )}
      </div>
    </Link>
  );
}
