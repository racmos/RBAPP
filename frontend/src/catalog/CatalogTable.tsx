import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import type { CardListSort, CardSummary } from '@/api/types';
import { BanBadge, CardImage, DomainPips, PriceTag, RarityDot } from '@/components/card';
import { useEnumLabel } from '@/i18n';
import { formatMoney, type Lang } from '@/lib/format';
import { TableScroll } from '@/components/ui/TableScroll';
import styles from './CatalogTable.module.css';

const DESCENDING_SORTS = new Set<CardListSort>(['price', 'trend_7d', 'trend_30d']);

type ColumnDef = {
  key: string;
  labelKey: string;
  sortKey?: CardListSort;
  align?: 'left' | 'right';
};

const NARROW_COLUMNS: ColumnDef[] = [
  { key: 'image', labelKey: 'catalog.table.image' },
  { key: 'set', labelKey: 'catalog.table.set' },
  { key: 'number', labelKey: 'catalog.table.number', sortKey: 'number' },
  { key: 'name', labelKey: 'catalog.table.name', sortKey: 'name' },
  { key: 'type', labelKey: 'catalog.table.type' },
  { key: 'rarity', labelKey: 'catalog.table.rarity', sortKey: 'rarity' },
  { key: 'energy', labelKey: 'catalog.table.energy', sortKey: 'energy', align: 'right' },
  { key: 'power', labelKey: 'catalog.table.power', sortKey: 'power', align: 'right' },
  { key: 'might', labelKey: 'catalog.table.might', sortKey: 'might', align: 'right' },
  { key: 'price', labelKey: 'catalog.table.price', sortKey: 'price', align: 'right' },
  { key: 'trend7', labelKey: 'catalog.table.trend7', sortKey: 'trend_7d', align: 'right' },
  { key: 'owned', labelKey: 'catalog.table.owned', align: 'right' },
  { key: 'bans', labelKey: 'catalog.table.bans' },
];

const WIDE_COLUMNS: ColumnDef[] = [
  ...NARROW_COLUMNS,
  { key: 'tags', labelKey: 'catalog.table.tags' },
  { key: 'foil', labelKey: 'catalog.table.foil', align: 'right' },
  { key: 'trend30', labelKey: 'catalog.table.trend30', sortKey: 'trend_30d', align: 'right' },
];

export type CatalogTableProps = {
  items: CardSummary[];
  sort: CardListSort;
  dir: 'asc' | 'desc';
  onSort: (sort: CardListSort, dir: 'asc' | 'desc') => void;
  isWide: boolean;
};

export function CatalogTable({ items, sort, dir, onSort, isWide }: CatalogTableProps) {
  const { t, i18n } = useTranslation('cards');
  const { typeLabel } = useEnumLabel();
  const lang = (i18n.language.split('-')[0] === 'en' ? 'en' : 'es') as Lang;
  const columns = isWide ? WIDE_COLUMNS : NARROW_COLUMNS;

  const handleSort = (column: CardListSort) => {
    if (sort === column) {
      onSort(column, dir === 'asc' ? 'desc' : 'asc');
    } else {
      onSort(column, DESCENDING_SORTS.has(column) ? 'desc' : 'asc');
    }
  };

  const renderCell = (column: ColumnDef, card: CardSummary) => {
    switch (column.key) {
      case 'image':
        return <CardImage card={card} size="thumb" decorative />;
      case 'set':
        return card.set_id;
      case 'number':
        return card.number ?? '—';
      case 'name':
        return (
          <div className={styles.nameCell}>
            <Link className={styles.nameLink} to={`/cards/${card.set_id}/${card.card_id}`}>
              {card.name}
            </Link>
            <DomainPips domains={card.domains} size={14} />
          </div>
        );
      case 'type':
        return typeLabel(card.supertype, card.type);
      case 'rarity':
        return <RarityDot rarity={card.rarity} showLabel />;
      case 'energy':
      case 'power':
      case 'might':
        return card[column.key] ?? '—';
      case 'price':
        return <PriceTag price={card.price} trend={null} size="sm" />;
      case 'trend7':
        return <PriceTag price={card.price} trend="7d" size="sm" />;
      case 'trend30':
        return <PriceTag price={card.price} trend="30d" size="sm" />;
      case 'tags':
        if (card.tags.length === 0) return '—';
        return (
          <span className={styles.tags}>
            {card.tags.slice(0, 3).map((tag) => (
              <span key={tag} className={styles.tag}>
                {tag}
              </span>
            ))}
            {card.tags.length > 3 && (
              <span className={styles.moreTags}>
                {t('catalog.table.moreTags', { count: card.tags.length - 3 })}
              </span>
            )}
          </span>
        );
      case 'foil':
        if (!card.foilable || card.price?.market_foil == null) return '—';
        return formatMoney(card.price.market_foil, lang);
      case 'owned':
        return card.owned.total > 0 ? card.owned.total : '—';
      case 'bans':
        return <BanBadge bans={card.bans} variant="compact" />;
      default:
        return null;
    }
  };

  return (
    <TableScroll className={isWide ? undefined : styles.scrollWrap}>
      <table className={styles.table}>
        <caption className="sr-only">{t('catalog.table.caption')}</caption>
        <thead>
          <tr>
            {columns.map((column) => {
              const active = column.sortKey === sort;
              return (
                <th
                  key={column.key}
                  scope="col"
                  className={[styles.th, column.align === 'right' && styles.right]
                    .filter(Boolean)
                    .join(' ')}
                  aria-sort={active ? (dir === 'asc' ? 'ascending' : 'descending') : undefined}
                >
                  {column.sortKey ? (
                    <button
                      type="button"
                      className={styles.sortButton}
                      onClick={() => handleSort(column.sortKey!)}
                      aria-label={`${t('catalog.sort.label')} ${t(column.labelKey as never)}`}
                    >
                      {t(column.labelKey as never)}
                    </button>
                  ) : (
                    t(column.labelKey as never)
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {items.map((card) => (
            <tr key={card.key}>
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={[
                    styles.td,
                    column.align === 'right' && styles.right,
                    column.key === 'image' && styles.imageCell,
                  ]
                    .filter(Boolean)
                    .join(' ')}
                >
                  {renderCell(column, card)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </TableScroll>
  );
}
