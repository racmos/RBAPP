import { formatMoney, formatPct, type Lang } from '@/lib/format';
import styles from './ProductTable.module.css';

/** A change or a profit with its sign in the text (`+`, `−`), coloured as well; `—` when unknown. */
export function Signed({
  value,
  lang,
  kind,
}: {
  value: number | null | undefined;
  lang: Lang;
  kind: 'money' | 'pct';
}) {
  if (value === null || value === undefined) return <span>—</span>;
  const text =
    kind === 'money'
      ? `${value > 0 ? '+' : value < 0 ? '−' : ''}${formatMoney(Math.abs(value), lang)}`
      : formatPct(value, lang);
  const tone = value > 0 ? styles.gain : value < 0 ? styles.loss : undefined;
  return <span className={tone}>{text}</span>;
}

/** A sortable column header: `aria-sort` and a button that asks for that sort. */
export function SortHeader<K extends string>({
  label,
  sortKey,
  sort,
  dir,
  onSort,
}: {
  label: string;
  sortKey: K;
  sort: K | undefined;
  dir: 'asc' | 'desc';
  onSort: (key: K) => void;
}) {
  const active = sort === sortKey;
  return (
    <th scope="col" aria-sort={active ? (dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
      <button type="button" className={styles.sortButton} onClick={() => onSort(sortKey)}>
        {label}
        {active && <span aria-hidden="true">{dir === 'asc' ? ' ↑' : ' ↓'}</span>}
      </button>
    </th>
  );
}
