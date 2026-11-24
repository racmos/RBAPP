import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { ApiError } from '@/api/errors';
import {
  createCardmarketPromoCards,
  type CardmarketPromoItem,
  type CardmarketPromoPlan,
  type CardmarketPromoSet,
} from '@/api/endpoints';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Checkbox } from '@/components/ui/Checkbox';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { EmptyState } from '@/components/ui/EmptyState';
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
import { FormAlert } from '@/admin/FormAlert';
import { cardmarketKeys } from '@/admin/cardmarket/queries';
import { cardRef } from './format';
import type { PanelProps } from './MatchingPage';
import { useSlotLabel } from './parts';
import { usePromoPlan, usePromoSets } from './queries';
import styles from './MatchingPage.module.css';

const STATUS_TONE = { create: 'accent', exists: 'neutral', manual: 'warning' } as const;

/** What the server says about a refused request (a 400 names the reason), else the code. */
function useErrorText() {
  const { i18n } = useTranslation('admin');
  return (error: unknown) =>
    error instanceof ApiError &&
    error.kind === 'http' &&
    error.status === 400 &&
    error.serverMessage
      ? error.serverMessage
      : translateError(error, i18n);
}

/**
 * "Missing cards" (CM-h): Riot's gallery has no promo sets, so their Cardmarket products have
 * no card to link to. A promo card has the id of its base card in the set whose id is the base
 * id followed by X. PLAT (CM-k) has no base set: a plated card copies the one card of its name
 * in another set, its origin (`PLAT-sfd189`). Choose a set (it goes to the URL), check the
 * cards to create (the ones the server can create start checked) and create them; Auto-match
 * links them later.
 */
export function MissingCardsPanel({ params, setParam, offline }: PanelProps) {
  const { t } = useTranslation('admin');
  const { t: common } = useTranslation('common');
  const sets = usePromoSets();
  const setId = params.get('set') ?? '';

  let chooser;
  if (sets.isPending) {
    chooser = <Skeleton label={t('matching.missing.set')} lines={1} />;
  } else if (sets.isError) {
    chooser = (
      <ErrorState message={common('errorState.title')} onRetry={() => void sets.refetch()} />
    );
  } else if (sets.data.sets.length === 0 && setId === '') {
    chooser = (
      <EmptyState
        title={t('matching.missing.emptySetsTitle')}
        body={t('matching.missing.emptySetsBody')}
      />
    );
  } else {
    chooser = (
      <div className={styles.filters}>
        <SetSelect sets={sets.data.sets} value={setId} onChange={(id) => setParam('set', id)} />
      </div>
    );
  }

  return (
    <>
      <p className={styles.help}>{t('matching.missing.help')}</p>
      <p className={styles.help}>{t('matching.missing.foilNote')}</p>
      {chooser}
      {setId === '' ? (
        sets.data &&
        sets.data.sets.length > 0 && (
          <p className={styles.muted}>{t('matching.missing.chooseHint')}</p>
        )
      ) : (
        <PromoPlan key={setId} setId={setId} offline={offline} />
      )}
    </>
  );
}

function SetSelect({
  sets,
  value,
  onChange,
}: {
  sets: CardmarketPromoSet[];
  value: string;
  onChange: (id: string | null) => void;
}) {
  const { t } = useTranslation('admin');
  const known = sets.some((one) => one.id === value);
  return (
    <Field label={t('matching.missing.set')}>
      {(control) => (
        <Select
          {...control}
          value={value}
          onChange={(event) => onChange(event.target.value || null)}
        >
          <option value="">{t('matching.missing.choose')}</option>
          {value !== '' && !known && <option value={value}>{value}</option>}
          {sets.map((one) => (
            <option key={one.id} value={one.id}>
              {one.cards_to_create === 0
                ? t('matching.missing.setOptionNone', { name: one.name, id: one.id })
                : t('matching.missing.setOption', {
                    name: one.name,
                    id: one.id,
                    count: one.cards_to_create,
                  })}
            </option>
          ))}
        </Select>
      )}
    </Field>
  );
}

/** The plan of one promo set: the summary, Create N cards and the list. */
function PromoPlan({ setId, offline }: { setId: string; offline: boolean }) {
  const { t } = useTranslation('admin');
  const { t: common } = useTranslation('common');
  const queryClient = useQueryClient();
  const errorText = useErrorText();
  const wide = useMediaQuery(up('md'));
  const query = usePromoPlan(setId);
  // the create items left unchecked (every create item starts checked)
  const [unchecked, setUnchecked] = useState<ReadonlySet<number>>(new Set());
  const [confirming, setConfirming] = useState(false);

  const create = useMutation({
    mutationFn: (productIds: number[]) => createCardmarketPromoCards(setId, productIds),
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
            : t('matching.missing.done', { count: created.length }),
      });
    },
    onError: (error: unknown) => pushToast({ kind: 'error', message: errorText(error) }),
  });

  if (query.isPending) {
    return offline ? (
      <p className={styles.help}>{t('matching.missing.offline')}</p>
    ) : (
      <Skeleton label={t('matching.missing.caption')} lines={5} />
    );
  }
  if (query.isError) {
    const refused = query.error instanceof ApiError && query.error.status === 400;
    return refused ? (
      <FormAlert message={errorText(query.error)} />
    ) : (
      <ErrorState message={common('errorState.title')} onRetry={() => void query.refetch()} />
    );
  }
  const plan = query.data;
  if (plan.items.length === 0) {
    return (
      <EmptyState
        title={t('matching.missing.emptyTitle', { set: plan.set.id })}
        body={t('matching.missing.emptyBody')}
      />
    );
  }

  const chosen = plan.items.filter(
    (item) => item.status === 'create' && !unchecked.has(item.product_id),
  );
  const count = chosen.length;
  const toggle = (item: CardmarketPromoItem, checked: boolean) =>
    setUnchecked((previous) => {
      const next = new Set(previous);
      if (checked) next.delete(item.product_id);
      else next.add(item.product_id);
      return next;
    });
  const others = [
    plan.summary.exists > 0
      ? t('matching.missing.existsCount', { count: plan.summary.exists })
      : '',
    plan.summary.manual > 0
      ? t('matching.missing.manualCount', { count: plan.summary.manual })
      : '',
  ].filter(Boolean);
  const list = { plan, unchecked, toggle, busy: create.isPending };

  return (
    <>
      <section className={styles.section} aria-label={t('matching.missing.summaryLabel')}>
        <p className={styles.rowTitle}>{t('matching.missing.toCreate', { count })}</p>
        {others.length > 0 && <p className={styles.muted}>{others.join(' ')}</p>}
        <div className={styles.rowActions}>
          <Button
            disabled={offline || count === 0 || create.isPending}
            pending={create.isPending}
            title={offline ? common('offline.editDisabled') : undefined}
            onClick={() => setConfirming(true)}
          >
            {t('matching.missing.create', { count })}
          </Button>
        </div>
      </section>
      {wide ? <PlanTable {...list} /> : <PlanCards {...list} />}
      <ConfirmDialog
        open={confirming}
        title={t('matching.missing.confirmTitle', { count, set: plan.set.id })}
        message={t(
          plan.set.base === null
            ? 'matching.missing.confirmBodyPlated'
            : 'matching.missing.confirmBody',
        )}
        confirmLabel={t('matching.missing.create', { count })}
        cancelLabel={common('actions.cancel')}
        onCancel={() => setConfirming(false)}
        onConfirm={() => {
          setConfirming(false);
          create.mutate(chosen.flatMap((item) => item.product_ids));
        }}
      />
    </>
  );
}

type ListProps = {
  plan: CardmarketPromoPlan;
  unchecked: ReadonlySet<number>;
  toggle: (item: CardmarketPromoItem, checked: boolean) => void;
  busy: boolean;
};

/**
 * The texts of one item, shared by the table and the cards; `baseSet` names the base set
 * (null for PLAT, CM-k: its reasons say "origin" and "any set" instead of the base set).
 */
function useItemText(baseSet: string | null) {
  const { t } = useTranslation('admin');
  const slot = useSlotLabel();
  const money = (value: number | null) => (value === null ? '—' : formatMoney(value));
  return {
    money,
    selectLabel: (item: CardmarketPromoItem) =>
      t('matching.missing.selectFor', { name: item.product_name, id: item.product_id }),
    productLine: (product: CardmarketPromoItem['products'][number]) =>
      t('matching.missing.productLine', {
        id: product.id,
        price: money(product.price),
        slot: slot(product.foil),
      }),
    base: (item: CardmarketPromoItem) =>
      item.base === null ? null : cardRef(item.base.set_id, item.base.card_id),
    baseName: (item: CardmarketPromoItem) =>
      item.base === null
        ? ''
        : item.base.rarity === null
          ? item.base.name
          : t('matching.missing.baseLine', { name: item.base.name, rarity: item.base.rarity }),
    proposed: (item: CardmarketPromoItem) =>
      item.proposed === null ? null : cardRef(item.proposed.set_id, item.proposed.card_id),
    status: (item: CardmarketPromoItem) => t(`matching.missing.status.${item.status}`),
    reason: (item: CardmarketPromoItem) => {
      const reason = item.reason;
      if (baseSet === null && (reason === 'no_base_card' || reason === 'invalid_base')) {
        return t(`matching.missing.platedReasons.${reason}`);
      }
      return t(`matching.missing.reasons.${reason}`, {
        ref: item.base === null ? '' : cardRef(item.base.set_id, item.base.card_id),
        base: baseSet ?? '',
        refs: (item.candidates ?? []).map((one) => cardRef(one.set_id, one.card_id)).join(', '),
      });
    },
  };
}

function SelectBox({
  item,
  unchecked,
  toggle,
  busy,
}: Omit<ListProps, 'plan'> & {
  item: CardmarketPromoItem;
}) {
  const { t } = useTranslation('admin');
  const text = useItemText('');
  const creatable = item.status === 'create';
  return (
    <Checkbox
      label={text.selectLabel(item)}
      hideLabel
      checked={creatable && !unchecked.has(item.product_id)}
      disabled={!creatable || busy}
      title={creatable ? undefined : t(`matching.missing.status.${item.status}`)}
      onChange={(event) => toggle(item, event.target.checked)}
    />
  );
}

function Products({ item }: { item: CardmarketPromoItem }) {
  const text = useItemText('');
  if (item.products.length === 1) {
    return (
      <span className={styles.cellStack}>
        <span>{item.product_name}</span>
        <span className={styles.muted}>#{item.product_id}</span>
      </span>
    );
  }
  return (
    <span className={styles.cellStack}>
      {item.products.map((product) => (
        <span key={product.id} className={styles.cellStack}>
          <span>{product.name}</span>
          <span className={styles.muted}>{text.productLine(product)}</span>
        </span>
      ))}
    </span>
  );
}

/** From 860 px: one row an item, the checkbox first. */
function PlanTable({ plan, ...rest }: ListProps) {
  const { t } = useTranslation('admin');
  const text = useItemText(plan.set.base);
  const plated = plan.set.base === null;
  return (
    <TableScroll>
      <table className={styles.table}>
        <caption className="sr-only">{t('matching.missing.caption')}</caption>
        <thead>
          <tr>
            <th scope="col">{t('matching.missing.columns.select')}</th>
            <th scope="col">{t('matching.missing.columns.product')}</th>
            <th scope="col">{t('matching.missing.columns.price')}</th>
            <th scope="col">
              {t(plated ? 'matching.missing.columns.origin' : 'matching.missing.columns.base')}
            </th>
            <th scope="col">
              {t(plated ? 'matching.missing.columns.plated' : 'matching.missing.columns.proposed')}
            </th>
            <th scope="col">{t('matching.missing.columns.status')}</th>
          </tr>
        </thead>
        <tbody>
          {plan.items.map((item) => (
            <tr key={item.product_id}>
              <td>
                <SelectBox item={item} {...rest} />
              </td>
              <td>
                <Products item={item} />
              </td>
              <td className={styles.nowrap}>{text.money(item.price)}</td>
              <td>
                {text.base(item) === null ? (
                  '—'
                ) : (
                  <span className={styles.cellStack}>
                    <span className={styles.nowrap}>{text.base(item)}</span>
                    <span className={styles.muted}>{text.baseName(item)}</span>
                  </span>
                )}
              </td>
              <td className={styles.nowrap}>{text.proposed(item) ?? '—'}</td>
              <td>
                <span className={styles.cellStack}>
                  <span>
                    <Badge tone={STATUS_TONE[item.status]}>{text.status(item)}</Badge>
                  </span>
                  <span className={styles.muted}>{text.reason(item)}</span>
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </TableScroll>
  );
}

/** Below 860 px: one card an item, the checkbox next to its product. */
function PlanCards({ plan, ...rest }: ListProps) {
  const { t } = useTranslation('admin');
  const text = useItemText(plan.set.base);
  return (
    <ul aria-label={t('matching.missing.caption')} className={styles.rows}>
      {plan.items.map((item) => {
        const base = text.base(item);
        const proposed = text.proposed(item);
        return (
          <li key={item.product_id} className={styles.row}>
            <div className={styles.rowHead}>
              <SelectBox item={item} {...rest} />
              <Products item={item} />
            </div>
            <p className={styles.current}>{text.money(item.price)}</p>
            {base !== null && (
              <p className={styles.kindLine}>
                <span>
                  {proposed === null
                    ? t('matching.missing.baseOnly', { ref: base })
                    : t('matching.missing.mapping', { base, promo: proposed })}
                </span>
                <span className={styles.muted}>{text.baseName(item)}</span>
              </p>
            )}
            <p className={styles.kindLine}>
              <Badge tone={STATUS_TONE[item.status]}>{text.status(item)}</Badge>
              <span className={styles.muted}>{text.reason(item)}</span>
            </p>
          </li>
        );
      })}
    </ul>
  );
}
