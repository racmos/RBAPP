import { useTranslation } from 'react-i18next';
import type { ProductSummary } from '@/api/types';
import { Icon } from '@/components/ui/Icon';
import styles from './ProductThumb.module.css';

type ProductThumbProps = {
  product: Pick<ProductSummary, 'name' | 'kind' | 'image_src'>;
  size: 'thumb' | 'tile' | 'full';
  /** A decorative image (the name is next to it) has no alternative text. */
  decorative?: boolean;
};

/** The product image, or a tile with the `gift` icon and the kind label (F14-e S4). */
export function ProductThumb({ product, size, decorative = false }: ProductThumbProps) {
  const { t } = useTranslation('products');
  const className = `${styles.frame} ${styles[size]}`;
  if (product.image_src) {
    return (
      <img
        src={product.image_src}
        alt={decorative ? '' : product.name}
        className={className}
        loading="lazy"
      />
    );
  }
  return (
    <span
      className={`${className} ${styles.placeholder}`}
      data-slot="product-placeholder"
      aria-hidden={decorative || undefined}
    >
      <Icon name="gift" size={size === 'thumb' ? 18 : 32} />
      {product.kind && (
        <span className={size === 'thumb' ? 'sr-only' : styles.kind}>
          {t(`kind.${product.kind}`)}
        </span>
      )}
    </span>
  );
}
