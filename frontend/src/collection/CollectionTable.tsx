import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { CollectionGroup, CollectionLine, CollectionSort } from '@/api/types';
import { CardImage } from '@/components/card';
import { Checkbox } from '@/components/ui/Checkbox';
import { Icon } from '@/components/ui/Icon';
import { formatDate, formatMoney, formatPct, type Lang } from '@/lib/format';
import { LineCells } from './LineCells';
import { TableScroll } from '@/components/ui/TableScroll';
import styles from './CollectionTable.module.css';

type Selection = {
  has: (id: number) => boolean;
  toggle: (ids: number[], on: boolean) => void;
};

type CollectionTableProps = {
  groups: CollectionGroup[];
  playsetSize: number;
  lang: Lang;
  sort: CollectionSort;
  dir: 'asc' | 'desc';
  onSort: (sort: CollectionSort) => void;
  selection: Selection;
  activeKey: string | null;
  onActivate: (group: CollectionGroup) => void;
  conditions: string[];
  languages: string[];
  offline: boolean;
};

const SORTABLE: Array<[string, CollectionSort]> = [
  ['number', 'number'],
  ['name', 'name'],
  ['qty', 'qty'],
  ['market', 'price'],
  ['plAbs', 'pl'],
  ['trend7d', 'trend_7d'],
  ['updated', 'updated'],
];

/** Profit of a group in euros and in percent of what was paid (lines without a price excluded). */
function groupProfit(lines: CollectionLine[]): { abs: number | null; pct: number | null } {
  const priced = lines.filter((line) => line.pl_abs !== null);
  if (priced.length === 0) return { abs: null, pct: null };
  const abs = priced.reduce((sum, line) => sum + (line.pl_abs ?? 0), 0);
  const paid = priced.reduce((sum, line) => sum + (line.purchase_price ?? 0) * line.qty, 0);
  return { abs, pct: paid > 0 ? (abs / paid) * 100 : null };
}

function Signed({
  value,
  lang,
  kind,
}: {
  value: number | null;
  lang: Lang;
  kind: 'money' | 'pct';
}) {
  if (value === null) return <span>—</span>;
  const text =
    kind === 'money'
      ? `${value > 0 ? '+' : value < 0 ? '−' : ''}${formatMoney(Math.abs(value), lang)}`
      : formatPct(value, lang);
  const sign = value > 0 ? styles.gain : value < 0 ? styles.loss : '';
  return <span className={sign}>{text}</span>;
}

function HeaderCell({
  id,
  label,
  sort,
  dir,
  onSort,
}: {
  id: string;
  label: string;
  sort: CollectionSort;
  dir: 'asc' | 'desc';
  onSort: (sort: CollectionSort) => void;
}) {
  const key = SORTABLE.find(([column]) => column === id)?.[1];
  if (!key) return <th scope="col">{label}</th>;
  const active = sort === key;
  return (
    <th scope="col" aria-sort={active ? (dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
      <button type="button" className={styles.sortButton} onClick={() => onSort(key)}>
        {label}
        {active && <span aria-hidden="true">{dir === 'asc' ? ' ↑' : ' ↓'}</span>}
      </button>
    </th>
  );
}

function SelectBox({
  label,
  checked,
  partial,
  onChange,
}: {
  label: string;
  checked: boolean;
  partial?: boolean;
  onChange: (on: boolean) => void;
}) {
  return (
    <Checkbox
      label={label}
      hideLabel
      indeterminate={Boolean(partial) && !checked}
      checked={checked}
      onChange={(event) => onChange(event.target.checked)}
    />
  );
}

/** The collection as a table: one row per card and foil, its lines folded below (F3-h S3). */
export function CollectionTable({
  groups,
  playsetSize,
  lang,
  sort,
  dir,
  onSort,
  selection,
  activeKey,
  onActivate,
  conditions,
  languages,
  offline,
}: CollectionTableProps) {
  const { t } = useTranslation('collection');
  const [expanded, setExpanded] = useState<ReadonlySet<string>>(new Set());
  const column = (key: string) => t(`table.columns.${key}` as 'table.columns.qty');

  const toggleExpanded = (key: string) =>
    setExpanded((current) => {
      const next = new Set(current);
      if (!next.delete(key)) next.add(key);
      return next;
    });

  const pageIds = groups.flatMap((group) => group.lines.map((line) => line.id));
  const selectedOnPage = pageIds.filter(selection.has).length;

  return (
    <TableScroll>
      <table className={styles.table}>
        <caption className="sr-only">{t('table.caption')}</caption>
        <thead>
          <tr>
            <th scope="col">
              <SelectBox
                label={t('table.selectPage')}
                checked={pageIds.length > 0 && selectedOnPage === pageIds.length}
                partial={selectedOnPage > 0}
                onChange={(on) => selection.toggle(pageIds, on)}
              />
            </th>
            {[
              'image',
              'set',
              'number',
              'name',
              'foil',
              'qty',
              'sellQty',
              'selling',
              'sellPrice',
            ].map((id) => (
              <HeaderCell
                key={id}
                id={id}
                label={column(id)}
                sort={sort}
                dir={dir}
                onSort={onSort}
              />
            ))}
            {[
              'condition',
              'language',
              'purchase',
              'market',
              'plAbs',
              'plPct',
              'trend7d',
              'updated',
            ].map((id) => (
              <HeaderCell
                key={id}
                id={id}
                label={column(id)}
                sort={sort}
                dir={dir}
                onSort={onSort}
              />
            ))}
          </tr>
        </thead>
        <tbody>
          {groups.map((group) => {
            const { card, lines } = group;
            const single = lines.length === 1;
            const open = expanded.has(group.key);
            const ids = lines.map((line) => line.id);
            const selected = ids.filter(selection.has).length;
            const profit = groupProfit(lines);
            const market = lines[0]?.market ?? null;
            const trend = card.price?.trend_7d_pct ?? null;
            const updated = lines.reduce(
              (max, line) => (line.updated_at > max ? line.updated_at : max),
              '',
            );
            return [
              <tr
                key={group.key}
                data-active={activeKey === group.key || undefined}
                className={group.playset_short ? styles.short : undefined}
                onClick={() => onActivate(group)}
              >
                <td onClick={(event) => event.stopPropagation()}>
                  <SelectBox
                    label={t('table.selectLine', { name: card.name })}
                    checked={ids.length > 0 && selected === ids.length}
                    partial={selected > 0}
                    onChange={(on) => selection.toggle(ids, on)}
                  />
                </td>
                <td>
                  <span className={styles.thumb}>
                    <CardImage card={card} size="thumb" decorative />
                  </span>
                </td>
                <td>{card.set_id}</td>
                <td>{card.card_id}</td>
                <td>
                  <span className={styles.nameCell}>
                    {!single && (
                      <button
                        type="button"
                        className={styles.expand}
                        aria-expanded={open}
                        aria-label={t('table.expand', { name: card.name })}
                        onClick={(event) => {
                          event.stopPropagation();
                          toggleExpanded(group.key);
                        }}
                      >
                        <span aria-hidden="true">{open ? '▾' : '▸'}</span>
                      </button>
                    )}
                    <span className={styles.name}>{card.name}</span>
                    {group.playset_short && (
                      <span className={styles.warn}>
                        <Icon name="info" size={14} />{' '}
                        {t('playset.short', { kept: group.kept, size: playsetSize })}
                      </span>
                    )}
                  </span>
                </td>
                <td>{group.foil ? t('foil') : ''}</td>
                {single ? (
                  <LineCells
                    line={lines[0]}
                    who={card.name}
                    conditions={conditions}
                    languages={languages}
                    disabled={offline}
                  />
                ) : (
                  <>
                    <td className={styles.numeric}>{group.qty}</td>
                    <td className={styles.numeric}>{group.sell_qty}</td>
                    <td />
                    <td />
                    <td />
                    <td />
                    <td />
                  </>
                )}
                <td className={styles.numeric}>
                  {market === null ? '—' : formatMoney(market, lang)}
                </td>
                <td className={styles.numeric}>
                  <Signed value={profit.abs} lang={lang} kind="money" />
                </td>
                <td className={styles.numeric}>
                  <Signed value={profit.pct} lang={lang} kind="pct" />
                </td>
                <td className={styles.numeric}>
                  <Signed value={trend} lang={lang} kind="pct" />
                </td>
                <td>{updated ? formatDate(updated, lang) : ''}</td>
              </tr>,
              ...(!single && open
                ? lines.map((line, index) => (
                    <tr key={line.id} className={styles.subline}>
                      <td>
                        <SelectBox
                          label={t('table.selectLine', {
                            name: t('table.lineOf', { name: card.name, index: index + 1 }),
                          })}
                          checked={selection.has(line.id)}
                          onChange={(on) => selection.toggle([line.id], on)}
                        />
                      </td>
                      <td />
                      <td />
                      <td />
                      <td>
                        <span className={styles.name}>
                          {t('line.legend', { index: index + 1 })}
                        </span>
                      </td>
                      <td>{line.foil ? t('foil') : ''}</td>
                      <LineCells
                        line={line}
                        who={t('table.lineOf', { name: card.name, index: index + 1 })}
                        conditions={conditions}
                        languages={languages}
                        disabled={offline}
                      />
                      <td className={styles.numeric}>
                        {line.market === null ? '—' : formatMoney(line.market, lang)}
                      </td>
                      <td className={styles.numeric}>
                        <Signed value={line.pl_abs} lang={lang} kind="money" />
                      </td>
                      <td className={styles.numeric}>
                        <Signed value={line.pl_pct} lang={lang} kind="pct" />
                      </td>
                      <td />
                      <td>{formatDate(line.updated_at, lang)}</td>
                    </tr>
                  ))
                : []),
            ];
          })}
        </tbody>
      </table>
    </TableScroll>
  );
}
