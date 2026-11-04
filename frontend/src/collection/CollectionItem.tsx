import { useTranslation } from 'react-i18next';
import type { CollectionGroup } from '@/api/types';
import { CardImage } from '@/components/card';
import { Icon } from '@/components/ui/Icon';
import { formatMoney } from '@/lib/format';
import { whereSummary } from './where';
import styles from './CollectionItem.module.css';

type CollectionItemProps = {
  group: CollectionGroup;
  variant: 'tile' | 'row';
  playsetSize: number;
  onOpen: (key: string) => void;
};

/**
 * One printing and foil of the collection, as a grid tile or a list row (F3-g S5). A group whose
 * playset is short gets an outline and a line of text: colour is never the only signal.
 */
export function CollectionItem({ group, variant, playsetSize, onOpen }: CollectionItemProps) {
  const { t } = useTranslation('collection');
  const { card } = group;
  const forSale = group.sell_qty > 0 && group.lines.some((line) => line.selling);
  const className = [styles[variant], group.playset_short ? styles.short : ''].filter(Boolean);
  const where = whereSummary(group.lines);

  const qty = (
    <span className={styles.qty} data-slot="qty">
      {t('qtyBadge', { count: group.qty })}
    </span>
  );

  return (
    <button
      type="button"
      className={className.join(' ')}
      aria-haspopup="dialog"
      onClick={() => onOpen(group.key)}
    >
      <span className={styles.art} data-slot="art">
        <CardImage card={card} size={variant === 'tile' ? 'tile' : 'thumb'} decorative />
        {variant === 'tile' && qty}
        {group.foil && <span className={styles.foil}>{t('foil')}</span>}
      </span>
      <span className={styles.body}>
        <span className={styles.name}>{card.name}</span>
        <span className={styles.meta}>
          {card.set_id} · #{card.card_id}
        </span>
        <span className={styles.status} data-slot="status">
          {forSale && (
            <span className={styles.selling}>{t('selling.tag', { count: group.sell_qty })}</span>
          )}
          {group.playset_short && (
            <span className={styles.shortText}>
              {t('playset.short', { kept: group.kept, size: playsetSize })}
            </span>
          )}
        </span>
        {/* One line, kept even when empty, so every item has the same height (F16-R5). */}
        <span className={styles.where} data-slot="where">
          {where && (
            <>
              <Icon name="pin" size={12} className={styles.pin} />
              <span className="sr-only">{`${t('where.label')}: `}</span>
              {where}
            </>
          )}
        </span>
      </span>
      {variant === 'row' && qty}
      <span className={styles.value}>{group.value === null ? '—' : formatMoney(group.value)}</span>
    </button>
  );
}
