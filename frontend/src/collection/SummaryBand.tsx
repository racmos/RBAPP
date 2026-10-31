import { useTranslation } from 'react-i18next';
import type { CollectionTotals } from '@/api/types';
import { formatMoney, formatPct } from '@/lib/format';
import styles from './SummaryBand.module.css';

/** Money with its sign written out: colour is never the only signal (F3-h S2). */
function signed(value: number): string {
  const sign = value > 0 ? '+' : value < 0 ? '−' : '';
  return `${sign}${formatMoney(Math.abs(value))}`;
}

/** The totals of everything the filters match (F3-h S2). */
export function SummaryBand({ totals }: { totals: CollectionTotals }) {
  const { t } = useTranslation('collection');
  const pct = totals.pl !== null && totals.cost ? (totals.pl / totals.cost) * 100 : null;
  const tone =
    totals.pl === null ? '' : totals.pl > 0 ? styles.gain : totals.pl < 0 ? styles.loss : '';
  const items: Array<[string, string, string?]> = [
    [t('totals.value'), formatMoney(totals.value)],
    [t('totals.cost'), totals.cost === null ? '—' : formatMoney(totals.cost)],
    [
      t('totals.pl'),
      totals.pl === null
        ? '—'
        : `${signed(totals.pl)}${pct === null ? '' : ` (${formatPct(pct)})`}`,
      tone,
    ],
    [t('totals.lines'), String(totals.lines)],
    [t('totals.unique'), String(totals.unique)],
    [t('totals.selling'), formatMoney(totals.selling_value)],
    [t('totals.foil'), `${totals.foil_pct.toLocaleString('en-GB', { maximumFractionDigits: 1 })}%`],
  ];
  return (
    <dl className={styles.band}>
      {items.map(([label, value, extra]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd className={extra}>{value}</dd>
        </div>
      ))}
    </dl>
  );
}
