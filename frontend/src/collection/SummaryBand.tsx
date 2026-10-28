import { useTranslation } from 'react-i18next';
import type { CollectionTotals } from '@/api/types';
import { formatMoney, formatPct, type Lang } from '@/lib/format';
import styles from './SummaryBand.module.css';

/** Money with its sign written out: colour is never the only signal (F3-h S2). */
function signed(value: number, lang: Lang): string {
  const sign = value > 0 ? '+' : value < 0 ? '−' : '';
  return `${sign}${formatMoney(Math.abs(value), lang)}`;
}

/** The totals of everything the filters match (F3-h S2). */
export function SummaryBand({ totals, lang }: { totals: CollectionTotals; lang: Lang }) {
  const { t } = useTranslation('collection');
  const pct = totals.pl !== null && totals.cost ? (totals.pl / totals.cost) * 100 : null;
  const tone =
    totals.pl === null ? '' : totals.pl > 0 ? styles.gain : totals.pl < 0 ? styles.loss : '';
  const items: Array<[string, string, string?]> = [
    [t('totals.value'), formatMoney(totals.value, lang)],
    [t('totals.cost'), totals.cost === null ? '—' : formatMoney(totals.cost, lang)],
    [
      t('totals.pl'),
      totals.pl === null
        ? '—'
        : `${signed(totals.pl, lang)}${pct === null ? '' : ` (${formatPct(pct, lang)})`}`,
      tone,
    ],
    [t('totals.lines'), String(totals.lines)],
    [t('totals.unique'), String(totals.unique)],
    [t('totals.selling'), formatMoney(totals.selling_value, lang)],
    [
      t('totals.foil'),
      `${totals.foil_pct.toLocaleString(lang === 'en' ? 'en-GB' : 'es-ES', { maximumFractionDigits: 1 })} %`,
    ],
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
