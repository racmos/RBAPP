import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { ApiError } from '@/api/errors';
import {
  createCardmarketMissingPrintings,
  type CardmarketMissingPrintings,
  type CardmarketPrintingGroup,
} from '@/api/endpoints';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Checkbox } from '@/components/ui/Checkbox';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { ErrorState } from '@/components/ui/ErrorState';
import { Field } from '@/components/ui/Field';
import { Select } from '@/components/ui/Select';
import { Skeleton } from '@/components/ui/Skeleton';
import { TableScroll } from '@/components/ui/TableScroll';
import { pushToast } from '@/components/ui/toastStore';
import { translateError } from '@/i18n';
import { up } from '@/lib/breakpoints';
import { formatMoney } from '@/lib/format';
import { useMediaQuery } from '@/lib/useMediaQuery';
import { cardmarketKeys } from '@/admin/cardmarket/queries';
import { cardRef } from './format';
import type { PanelProps } from './MatchingPage';
import { useMissingPrintings } from './queries';
import styles from './MatchingPage.module.css';

const STATUS_TONE = { create: 'accent', exists: 'neutral', manual: 'warning' } as const;
/** The URL key of the set filter of the list. */
const FILTER = 'printings';

/** A group with its set: the API nests the groups under their set. */
type Row = CardmarketPrintingGroup & { set_id: string };

const keyOf = (row: Row) => `${row.set_id}-${row.proposed?.card_id ?? row.metacard}`;

/**
 * "Extra printings" (CM-m), under the promo list of the Missing cards tab: Cardmarket lists
 * more printings of some cards than the catalog has (the Radiance legends: Rare, Showcase and
 * the signed card, while Riot's gallery has two). Owner answer 2026-11-24: the extra one is
 * the signed card, `<id>s`, a copy of the highest printing with the rarity Showcase. The groups
 * the server can create start checked; the set filter is in the URL (`printings`).
 */
export function ExtraPrintings({
  params,
  setParam,
  offline,
}: Pick<PanelProps, 'params' | 'setParam' | 'offline'>) {
  const { t } = useTranslation('admin');
  const { t: common } = useTranslation('common');
  const query = useMissingPrintings();

  let body;
  if (query.isPending) {
    body = offline ? (
      <p className={styles.help}>{t('matching.printings.offline')}</p>
    ) : (
      <Skeleton label={t('matching.printings.caption')} lines={4} />
    );
  } else if (query.isError) {
    body = <ErrorState message={common('errorState.title')} onRetry={() => void query.refetch()} />;
  } else if (query.data.sets.length === 0) {
    body = <p className={styles.muted}>{t('matching.printings.empty')}</p>;
  } else {
    body = (
      <PrintingsList
        data={query.data}
        filter={params.get(FILTER) ?? ''}
        onFilter={(value) => setParam(FILTER, value)}
        offline={offline}
      />
    );
  }

  return (
    <section className={styles.section} aria-labelledby="matching-printings">
      <h3 id="matching-printings" className={styles.sectionTitle}>
        {t('matching.printings.title')}
      </h3>
      <p className={styles.help}>{t('matching.printings.help')}</p>
      {body}
    </section>
  );
}

function PrintingsList({
  data,
  filter,
  onFilter,
  offline,
}: {
  data: CardmarketMissingPrintings;
  filter: string;
  onFilter: (value: string | null) => void;
  offline: boolean;
}) {
  const { t, i18n } = useTranslation('admin');
  const { t: common } = useTranslation('common');
  const queryClient = useQueryClient();
  const wide = useMediaQuery(up('md'));
  // the create groups left unchecked (every create group starts checked)
  const [unchecked, setUnchecked] = useState<ReadonlySet<string>>(new Set());
  const [confirming, setConfirming] = useState(false);

  const create = useMutation({
    mutationFn: createCardmarketMissingPrintings,
    onSuccess: ({ created }) => {
      setUnchecked(new Set());
      void queryClient.invalidateQueries({ queryKey: cardmarketKeys.all });
      void queryClient.invalidateQueries({ queryKey: ['admin', 'sets'] });
      void queryClient.invalidateQueries({ queryKey: ['admin', 'cards'] });
      pushToast({
        kind: 'success',
        message:
          created.length === 0
            ? t('matching.missing.noneCreated')
            : t('matching.printings.done', { count: created.length }),
      });
    },
    onError: (error: unknown) =>
      pushToast({
        kind: 'error',
        message:
          error instanceof ApiError &&
          error.kind === 'http' &&
          error.status === 400 &&
          error.serverMessage
            ? error.serverMessage
            : translateError(error, i18n),
      }),
  });

  const rows: Row[] = data.sets
    .filter((one) => filter === '' || one.set_id === filter)
    .flatMap((one) => one.groups.map((group) => ({ ...group, set_id: one.set_id })));
  const chosen = rows.filter((row) => row.status === 'create' && !unchecked.has(keyOf(row)));
  const count = chosen.length;
  const toggle = (row: Row, checked: boolean) =>
    setUnchecked((previous) => {
      const next = new Set(previous);
      if (checked) next.delete(keyOf(row));
      else next.add(keyOf(row));
      return next;
    });
  const exists = rows.filter((row) => row.status === 'exists').length;
  const manual = rows.filter((row) => row.status === 'manual').length;
  const others = [
    exists > 0 ? t('matching.printings.existsCount', { count: exists }) : '',
    manual > 0 ? t('matching.printings.manualCount', { count: manual }) : '',
  ].filter(Boolean);
  const list = { rows, unchecked, toggle, busy: create.isPending };
  const known = data.sets.some((one) => one.set_id === filter);

  return (
    <>
      <div className={styles.filters}>
        <Field label={t('matching.printings.set')}>
          {(control) => (
            <Select
              {...control}
              value={filter}
              onChange={(event) => onFilter(event.target.value || null)}
            >
              <option value="">{t('matching.printings.allSets')}</option>
              {filter !== '' && !known && <option value={filter}>{filter}</option>}
              {data.sets.map((one) => {
                const n = one.groups.filter((group) => group.status === 'create').length;
                return (
                  <option key={one.set_id} value={one.set_id}>
                    {n === 0
                      ? t('matching.printings.setOptionNone', {
                          name: one.set_name,
                          id: one.set_id,
                        })
                      : t('matching.printings.setOption', {
                          name: one.set_name,
                          id: one.set_id,
                          count: n,
                        })}
                  </option>
                );
              })}
            </Select>
          )}
        </Field>
      </div>
      <section className={styles.section} aria-label={t('matching.printings.summaryLabel')}>
        <p className={styles.rowTitle}>{t('matching.printings.toCreate', { count })}</p>
        {others.length > 0 && <p className={styles.muted}>{others.join(' ')}</p>}
        <div className={styles.rowActions}>
          <Button
            disabled={offline || count === 0 || create.isPending}
            pending={create.isPending}
            title={offline ? common('offline.editDisabled') : undefined}
            onClick={() => setConfirming(true)}
          >
            {t('matching.printings.create', { count })}
          </Button>
        </div>
      </section>
      {rows.length === 0 ? (
        <p className={styles.muted}>{t('matching.printings.empty')}</p>
      ) : wide ? (
        <PrintingsTable {...list} />
      ) : (
        <PrintingsCards {...list} />
      )}
      <ConfirmDialog
        open={confirming}
        title={t('matching.printings.confirmTitle', { count })}
        message={t('matching.printings.confirmBody')}
        confirmLabel={t('matching.printings.create', { count })}
        cancelLabel={common('actions.cancel')}
        onCancel={() => setConfirming(false)}
        onConfirm={() => {
          setConfirming(false);
          create.mutate(
            chosen.map((row) => ({ set_id: row.set_id, card_id: row.proposed!.card_id })),
          );
        }}
      />
    </>
  );
}

type ListProps = {
  rows: Row[];
  unchecked: ReadonlySet<string>;
  toggle: (row: Row, checked: boolean) => void;
  busy: boolean;
};

/** The texts of one group, shared by the table and the cards. */
function useGroupText() {
  const { t } = useTranslation('admin');
  const ref = (card: { set_id: string; card_id: string } | null) =>
    card === null ? '' : cardRef(card.set_id, card.card_id);
  return {
    product: (product: Row['products'][number]) => {
      const price =
        product.price === null ? t('matching.printings.noPrice') : formatMoney(product.price);
      return product.linked === null
        ? t('matching.printings.productLine', { id: product.id, price })
        : t('matching.printings.productLinked', {
            id: product.id,
            price,
            ref: ref(product.linked),
          });
    },
    card: (card: Row['cards'][number]) =>
      card.rarity === null
        ? ref(card)
        : t('matching.printings.cardLine', { ref: ref(card), rarity: card.rarity }),
    newCard: (row: Row) =>
      row.proposed === null
        ? null
        : t('matching.printings.newCard', {
            ref: ref(row.proposed),
            rarity: row.proposed.rarity ?? '',
          }),
    selectLabel: (row: Row) =>
      row.proposed === null
        ? t('matching.printings.selectForNone', { name: row.name })
        : t('matching.printings.selectFor', { name: row.name, ref: ref(row.proposed) }),
    status: (row: Row) => t(`matching.missing.status.${row.status}`),
    reason: (row: Row) =>
      t(`matching.printings.reasons.${row.reason}`, {
        ref: ref(row.base),
        signed: row.base === null ? '' : `${ref(row.base)}s`,
      }),
  };
}

function SelectBox({ row, unchecked, toggle, busy }: Omit<ListProps, 'rows'> & { row: Row }) {
  const text = useGroupText();
  const creatable = row.status === 'create';
  return (
    <Checkbox
      label={text.selectLabel(row)}
      hideLabel
      checked={creatable && !unchecked.has(keyOf(row))}
      disabled={!creatable || busy}
      title={creatable ? undefined : text.status(row)}
      onChange={(event) => toggle(row, event.target.checked)}
    />
  );
}

function Products({ row }: { row: Row }) {
  const text = useGroupText();
  return (
    <span className={styles.cellStack}>
      <span>{row.name}</span>
      {row.products.map((product) => (
        <span key={product.id} className={styles.muted}>
          {text.product(product)}
        </span>
      ))}
    </span>
  );
}

/** From 860 px: one row a group, the checkbox first. */
function PrintingsTable({ rows, ...rest }: ListProps) {
  const { t } = useTranslation('admin');
  const text = useGroupText();
  return (
    <TableScroll>
      <table className={styles.table}>
        <caption className="sr-only">{t('matching.printings.caption')}</caption>
        <thead>
          <tr>
            <th scope="col">{t('matching.printings.columns.select')}</th>
            <th scope="col">{t('matching.printings.columns.set')}</th>
            <th scope="col">{t('matching.printings.columns.products')}</th>
            <th scope="col">{t('matching.printings.columns.cards')}</th>
            <th scope="col">{t('matching.printings.columns.newCard')}</th>
            <th scope="col">{t('matching.printings.columns.status')}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={keyOf(row)}>
              <td>
                <SelectBox row={row} {...rest} />
              </td>
              <td className={styles.nowrap}>{row.set_id}</td>
              <td>
                <Products row={row} />
              </td>
              <td>
                <span className={styles.cellStack}>
                  {row.cards.map((card) => (
                    <span key={card.card_id} className={styles.nowrap}>
                      {text.card(card)}
                    </span>
                  ))}
                </span>
              </td>
              <td className={styles.nowrap}>{text.newCard(row) ?? '—'}</td>
              <td>
                <span className={styles.cellStack}>
                  <span>
                    <Badge tone={STATUS_TONE[row.status]}>{text.status(row)}</Badge>
                  </span>
                  <span className={styles.muted}>{text.reason(row)}</span>
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </TableScroll>
  );
}

/** Below 860 px: one card a group, the checkbox next to its products. */
function PrintingsCards({ rows, ...rest }: ListProps) {
  const { t } = useTranslation('admin');
  const text = useGroupText();
  return (
    <ul aria-label={t('matching.printings.caption')} className={styles.rows}>
      {rows.map((row) => {
        const newCard = text.newCard(row);
        return (
          <li key={keyOf(row)} className={styles.row}>
            <div className={styles.rowHead}>
              <SelectBox row={row} {...rest} />
              <Products row={row} />
            </div>
            <p className={styles.kindLine}>
              {t('matching.printings.cardsHere', {
                list: row.cards.map((card) => text.card(card)).join(', '),
              })}
            </p>
            {newCard !== null && row.status === 'create' && (
              <p className={styles.kindLine}>
                {t('matching.printings.willCreate', { card: newCard })}
              </p>
            )}
            <p className={styles.kindLine}>
              <Badge tone={STATUS_TONE[row.status]}>{text.status(row)}</Badge>
              <span className={styles.muted}>{text.reason(row)}</span>
            </p>
          </li>
        );
      })}
    </ul>
  );
}
