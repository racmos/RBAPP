import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { OwnedProductLine } from '@/api/types';
import { DebouncedInput } from '@/catalog';
import { Stepper } from '@/collection/Stepper';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Skeleton } from '@/components/ui/Skeleton';
import { TableScroll } from '@/components/ui/TableScroll';
import { formatMoney, type Lang } from '@/lib/format';
import { MineSummary } from './MineTab';
import { ProductLineSheet } from './ProductLineSheet';
import { ProductThumb } from './ProductThumb';
import { useMyProducts } from './queries';
import { Signed } from './tableParts';
import { useProductLineSaver } from './useProductLineSaver';
import styles from './ProductTable.module.css';

const NOTE_MAX = 200;
const COLUMNS = [
  'name',
  'kind',
  'quantity',
  'purchase',
  'price',
  'value',
  'plAbs',
  'plPct',
  'note',
] as const;

type MineTableProps = {
  lang: Lang;
  offline: boolean;
  onBrowse: () => void;
  selected: number | null;
  /** A row click: the product id (the panel from 1600 px, else the product page). */
  onActivate: (id: number) => void;
};

/** The inline editors keep their clicks: they never select or open the row. */
const keep = (event: { stopPropagation: () => void }) => event.stopPropagation();

function Row({
  line,
  lang,
  offline,
  selected,
  onActivate,
  onOpen,
}: {
  line: OwnedProductLine;
  lang: Lang;
  offline: boolean;
  selected: boolean;
  onActivate: (id: number) => void;
  onOpen: () => void;
}) {
  const { t } = useTranslation('products');
  const save = useProductLineSaver(line.id);
  const { product } = line;
  const label = (key: string) =>
    `${t(`table.columns.${key}` as 'table.columns.name')}: ${product.name}`;
  const money = (value: number | null | undefined) =>
    value === null || value === undefined ? t('unpriced') : formatMoney(value, lang);

  return (
    <tr data-active={selected || undefined} onClick={() => onActivate(product.id)}>
      <td>
        <span className={styles.thumb}>
          <ProductThumb product={product} size="thumb" decorative />
        </span>
      </td>
      <td onClick={keep}>
        <button type="button" className={styles.nameButton} aria-haspopup="dialog" onClick={onOpen}>
          {product.name}
        </button>
      </td>
      <td>{product.kind ? t(`kind.${product.kind}`) : '—'}</td>
      <td onClick={keep} className={styles.stepper}>
        <Stepper
          label={label('quantity')}
          value={line.quantity}
          min={1}
          max={9999}
          disabled={offline}
          onCommit={(quantity) => void save({ quantity })}
        />
      </td>
      <td onClick={keep} className={styles.numeric}>
        <DebouncedInput
          type="number"
          inputMode="decimal"
          className={styles.money}
          aria-label={label('purchase')}
          min={0}
          step="0.01"
          disabled={offline}
          value={line.purchase_price === null ? '' : String(line.purchase_price)}
          delay={500}
          onCommit={(next) => {
            if (next === '') return void save({ purchase_price: null });
            const parsed = Number(next);
            if (Number.isFinite(parsed) && parsed >= 0) void save({ purchase_price: parsed });
          }}
        />
      </td>
      <td className={styles.numeric}>{money(product.price?.value)}</td>
      <td className={styles.numeric}>{money(line.value)}</td>
      <td className={styles.numeric}>
        <Signed value={line.pl_abs} lang={lang} kind="money" />
      </td>
      <td className={styles.numeric}>
        <Signed value={line.pl_pct} lang={lang} kind="pct" />
      </td>
      <td onClick={keep}>
        <DebouncedInput
          className={styles.note}
          aria-label={label('note')}
          maxLength={NOTE_MAX}
          disabled={offline}
          value={line.note ?? ''}
          delay={500}
          onCommit={(next) => void save({ note: next.trim() || null })}
        />
      </td>
    </tr>
  );
}

/** "Mis productos" from 1240 px (F14-f S3): the total band and the lines with inline editors. */
export function MineTable({ lang, offline, onBrowse, selected, onActivate }: MineTableProps) {
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
      <MineSummary total={total} lang={lang} offline={offline} />
      <TableScroll>
        <table className={styles.table} aria-busy={mine.isFetching || undefined}>
          <caption className="sr-only">{t('table.mineCaption')}</caption>
          <thead>
            <tr>
              <th scope="col">
                <span className="sr-only">{t('table.columns.image')}</span>
              </th>
              {COLUMNS.map((key) => (
                <th key={key} scope="col">
                  {t(`table.columns.${key}`)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map((line) => (
              <Row
                key={line.id}
                line={line}
                lang={lang}
                offline={offline}
                selected={selected === line.product.id}
                onActivate={onActivate}
                onOpen={() => setOpenId(line.id)}
              />
            ))}
          </tbody>
        </table>
      </TableScroll>
      {open && <ProductLineSheet line={open} onClose={() => setOpenId(null)} offline={offline} />}
    </>
  );
}
