import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { deleteCardmarketLink, type CardmarketLink } from '@/api/endpoints';
import { DebouncedInput } from '@/catalog';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Pagination } from '@/components/ui/Pagination';
import { Select } from '@/components/ui/Select';
import { Skeleton } from '@/components/ui/Skeleton';
import { TableScroll } from '@/components/ui/TableScroll';
import { pushToast } from '@/components/ui/toastStore';
import { translateError } from '@/i18n';
import { formatMoney } from '@/lib/format';
import { apiQuery, cardRef, groupConflicts } from './format';
import type { PanelProps } from './MatchingPage';
import { useSlotLabel, useSlotRef } from './parts';
import { useLinks, useUndoToasts } from './queries';
import styles from './MatchingPage.module.css';

const productName = (link: CardmarketLink) => link.product_name ?? `#${link.id_product}`;

/** Unlink with a confirmation and an Undo toast; shared by Linked and Conflicts. */
function useUnlink() {
  const { i18n } = useTranslation('admin');
  const toasts = useUndoToasts();
  const [asking, setAsking] = useState<CardmarketLink | null>(null);
  const unlink = useMutation({
    mutationFn: (link: CardmarketLink) => deleteCardmarketLink(link.id_product),
    onSuccess: ({ link }, asked) => toasts.unlinked(productName(asked), link),
    onError: (error: unknown) => pushToast({ kind: 'error', message: translateError(error, i18n) }),
  });
  return { asking, setAsking, unlink };
}

function UnlinkConfirm({ unlinker }: { unlinker: ReturnType<typeof useUnlink> }) {
  const { t } = useTranslation('admin');
  const { t: common } = useTranslation('common');
  const slotRef = useSlotRef();
  const { asking, setAsking, unlink } = unlinker;
  return (
    <ConfirmDialog
      open={asking !== null}
      danger
      title={asking ? t('matching.linked.confirmTitle', { name: productName(asking) }) : ''}
      message={
        asking
          ? t('matching.linked.confirmBody', {
              target: `${slotRef(asking)} ${asking.card_name ?? ''}`.trim(),
            })
          : ''
      }
      confirmLabel={t('matching.linked.unlink')}
      cancelLabel={common('actions.cancel')}
      onCancel={() => setAsking(null)}
      onConfirm={() => {
        if (asking) unlink.mutate(asking);
        setAsking(null);
      }}
    />
  );
}

type RowActions = {
  busy: boolean;
  onRelink: (link: CardmarketLink) => void;
  onUnlink: (link: CardmarketLink) => void;
};

function LinksTable({
  links,
  caption,
  actions,
}: {
  links: CardmarketLink[];
  caption: string;
  actions: RowActions;
}) {
  const { t } = useTranslation('admin');
  const slotLabel = useSlotLabel();
  return (
    <TableScroll>
      <table className={styles.table}>
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            <th scope="col">{t('matching.linked.columns.product')}</th>
            <th scope="col">{t('matching.linked.columns.card')}</th>
            <th scope="col">{t('matching.linked.columns.slot')}</th>
            <th scope="col">{t('matching.linked.columns.price')}</th>
            <th scope="col">{t('matching.linked.columns.match')}</th>
            <th scope="col">{t('matching.linked.columns.actions')}</th>
          </tr>
        </thead>
        <tbody>
          {links.map((link) => {
            const name = productName(link);
            return (
              <tr key={link.id_product}>
                <td>
                  <span className={styles.cellStack}>
                    <span>{name}</span>
                    <span className={styles.muted}>#{link.id_product}</span>
                    {!link.in_latest_load && (
                      <Badge tone="warning">{t('matching.linked.notLatest')}</Badge>
                    )}
                  </span>
                </td>
                <td>
                  <span className={styles.cellStack}>
                    <span className={styles.nowrap}>{cardRef(link.set_id, link.card_id)}</span>
                    {link.card_name && <span className={styles.muted}>{link.card_name}</span>}
                  </span>
                </td>
                <td>{slotLabel(link.foil)}</td>
                <td className={styles.nowrap}>
                  {link.low_price === null ? '—' : formatMoney(link.low_price)}
                </td>
                <td>
                  <Badge tone={link.match_type === 'manual' ? 'accent' : 'neutral'}>
                    {link.match_type === 'manual'
                      ? t('matching.linked.manual')
                      : link.match_type === 'auto'
                        ? t('matching.linked.auto')
                        : link.match_type}
                  </Badge>
                </td>
                <td>
                  <span className={styles.rowActions}>
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={actions.busy}
                      aria-label={t('matching.linked.relinkFor', { name })}
                      onClick={() => actions.onRelink(link)}
                    >
                      {t('matching.linked.relink')}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={actions.busy}
                      aria-label={t('matching.linked.unlinkFor', { name })}
                      onClick={() => actions.onUnlink(link)}
                    >
                      {t('matching.linked.unlink')}
                    </Button>
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </TableScroll>
  );
}

const relinkSubject = (link: CardmarketLink) => ({
  id_product: link.id_product,
  name: productName(link),
  current: link,
});

/** "Linked": every link with filters; Relink and Unlink per row (CM-b). */
export function LinkedPanel({ params, setParam, setPage, offline, openDialog }: PanelProps) {
  const { t } = useTranslation('admin');
  const { t: common } = useTranslation('common');
  const query = useLinks(apiQuery('linked', params));
  const unlinker = useUnlink();
  const actions: RowActions = {
    busy: offline || unlinker.unlink.isPending,
    onRelink: (link) => openDialog(relinkSubject(link)),
    onUnlink: unlinker.setAsking,
  };

  const filters = (
    <div className={styles.filters}>
      <label className={styles.filterField}>
        {t('matching.linked.search')}
        <DebouncedInput
          aria-label={t('matching.linked.search')}
          value={params.get('q') ?? ''}
          onCommit={(next) => setParam('q', next.trim() || null)}
        />
      </label>
      <label className={styles.filterField}>
        {t('matching.linked.set')}
        <DebouncedInput
          aria-label={t('matching.linked.set')}
          className={styles.short}
          value={params.get('set') ?? ''}
          onCommit={(next) => setParam('set', next.trim() || null)}
        />
      </label>
      <label className={styles.filterField}>
        {t('matching.linked.slot')}
        <Select
          aria-label={t('matching.linked.slot')}
          value={params.get('foil') ?? ''}
          onChange={(event) => setParam('foil', event.target.value || null)}
        >
          <option value="">{t('matching.linked.any')}</option>
          <option value="N">{t('matching.slotOption.N')}</option>
          <option value="S">{t('matching.slotOption.S')}</option>
          <option value="none">{t('matching.slotOption.none')}</option>
        </Select>
      </label>
      <label className={styles.filterField}>
        {t('matching.linked.match')}
        <Select
          aria-label={t('matching.linked.match')}
          value={params.get('match_type') ?? ''}
          onChange={(event) => setParam('match_type', event.target.value || null)}
        >
          <option value="">{t('matching.linked.any')}</option>
          <option value="auto">{t('matching.linked.auto')}</option>
          <option value="manual">{t('matching.linked.manual')}</option>
        </Select>
      </label>
    </div>
  );

  let body;
  if (query.isPending) {
    body = <Skeleton label={t('matching.linked.caption')} lines={6} />;
  } else if (query.isError) {
    body = <ErrorState message={common('errorState.title')} onRetry={() => void query.refetch()} />;
  } else if (query.data.items.length === 0) {
    body = (
      <EmptyState title={t('matching.linked.emptyTitle')} body={t('matching.linked.emptyBody')} />
    );
  } else {
    const { items, meta } = query.data;
    body = (
      <>
        <p className={styles.meta}>
          <span>{t('matching.linked.count', { count: meta.total })}</span>
          <span>{t('matching.linked.conflictSlots', { count: meta.conflict_slots })}</span>
        </p>
        <LinksTable links={items} caption={t('matching.linked.caption')} actions={actions} />
        {meta.pages > 1 && <Pagination page={meta.page} pages={meta.pages} onChange={setPage} />}
      </>
    );
  }

  return (
    <>
      {filters}
      {body}
      <UnlinkConfirm unlinker={unlinker} />
    </>
  );
}

/** "Conflicts": the slots held by several Cardmarket products, one group per slot (CM-b). */
export function ConflictsPanel({ params, setPage, offline, openDialog }: PanelProps) {
  const { t } = useTranslation('admin');
  const { t: common } = useTranslation('common');
  const slotLabel = useSlotLabel();
  const query = useLinks(apiQuery('conflicts', params));
  const unlinker = useUnlink();
  const actions: RowActions = {
    busy: offline || unlinker.unlink.isPending,
    onRelink: (link) => openDialog(relinkSubject(link)),
    onUnlink: unlinker.setAsking,
  };

  let body;
  if (query.isPending) {
    body = <Skeleton label={t('matching.conflicts.caption')} lines={6} />;
  } else if (query.isError) {
    body = <ErrorState message={common('errorState.title')} onRetry={() => void query.refetch()} />;
  } else if (query.data.items.length === 0) {
    body = (
      <EmptyState
        title={t('matching.conflicts.emptyTitle')}
        body={t('matching.conflicts.emptyBody')}
      />
    );
  } else {
    const { items, meta } = query.data;
    body = (
      <>
        <p className={styles.muted}>
          {t('matching.linked.conflictSlots', { count: meta.conflict_slots })}
        </p>
        <ul aria-label={t('matching.conflicts.caption')} className={styles.rows}>
          {groupConflicts(items).map((group) => {
            const heading = t('matching.conflicts.slot', {
              ref: cardRef(group.set_id, group.card_id),
              name: group.card_name ?? '',
              slot: slotLabel(group.foil),
            });
            return (
              <li key={group.key} className={styles.row}>
                <div className={styles.rowHead}>
                  <h3 className={styles.rowTitle}>{heading}</h3>
                  <span className={styles.muted}>
                    {t('matching.conflicts.products', { count: group.links.length })}
                  </span>
                </div>
                <LinksTable links={group.links} caption={heading} actions={actions} />
              </li>
            );
          })}
        </ul>
        {meta.pages > 1 && <Pagination page={meta.page} pages={meta.pages} onChange={setPage} />}
      </>
    );
  }

  return (
    <>
      <p className={styles.help}>{t('matching.conflicts.intro')}</p>
      {body}
      <UnlinkConfirm unlinker={unlinker} />
    </>
  );
}
