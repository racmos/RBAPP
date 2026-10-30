import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router';
import { useSearchNavigation } from '@/catalog';
import { listAdminSets } from '@/api/endpoints';
import { Button } from '@/components/ui/Button';
import { Checkbox } from '@/components/ui/Checkbox';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Input } from '@/components/ui/Input';
import { PageHeader } from '@/components/ui/PageHeader';
import { Pagination } from '@/components/ui/Pagination';
import { SegmentedControl, type SegmentedOption } from '@/components/ui/SegmentedControl';
import { Select } from '@/components/ui/Select';
import { Skeleton } from '@/components/ui/Skeleton';
import { pushToast } from '@/components/ui/toastStore';
import { useDocumentTitle, translateError } from '@/i18n';

import { formatDate, type Lang } from '@/lib/format';
import { down, up } from '@/lib/breakpoints';
import { sortSetsNewestFirst } from '@/lib/sets';
import { useMediaQuery } from '@/lib/useMediaQuery';
import { useOnline } from '@/lib/useOnline';
import { ValueDiff } from './ValueDiff';
import { SidePanel } from '@/components/ui/SidePanel';
import { TableScroll } from '@/components/ui/TableScroll';
import styles from './ChangesPage.module.css';

export type AdminChange = {
  id: number;
  set_id: string;
  card_id: string;
  card_name: string | null;
  image_src: string | null;
  field: string;
  old_value: string | null;
  new_value: string | null;
  status: 'pending' | 'approved' | 'rejected' | 'obsolete';
  detected_at: string | null;
  job_id: number | null;
  decided_at: string | null;
  decided_by: string | null;
};

type ChangesResponse = {
  items: AdminChange[];
  meta: {
    page: number;
    per_page: number;
    total: number;
    pages: number;
    counts: Record<string, number>;
  };
};

type FieldName =
  | 'rbcar_name'
  | 'rbcar_domain'
  | 'rbcar_type'
  | 'rbcar_tags'
  | 'rbcar_energy'
  | 'rbcar_power'
  | 'rbcar_might'
  | 'rbcar_ability'
  | 'rbcar_rarity'
  | 'rbcar_artist'
  | 'image_url'
  | 'image';

const FIELDS: readonly FieldName[] = [
  'rbcar_name',
  'rbcar_domain',
  'rbcar_type',
  'rbcar_tags',
  'rbcar_energy',
  'rbcar_power',
  'rbcar_might',
  'rbcar_ability',
  'rbcar_rarity',
  'rbcar_artist',
  'image_url',
  'image',
];
const LONG_FIELDS: readonly string[] = ['rbcar_ability', 'rbcar_tags'];
const STATUSES = ['pending', 'approved', 'rejected', 'obsolete', 'all'] as const;
const PAGE_SIZES = ['50', '100', '200'] as const;
const DEFAULT_PAGE_SIZE = '50';

async function fetchChanges(
  params: URLSearchParams,
  signal?: AbortSignal,
): Promise<ChangesResponse> {
  const query = new URLSearchParams();
  for (const key of ['status', 'set', 'field', 'q', 'page', 'per_page']) {
    const value = params.get(key);
    if (value) query.set(key, value);
  }
  if (!query.get('status')) query.set('status', 'pending');
  if (!query.get('per_page')) query.set('per_page', DEFAULT_PAGE_SIZE);
  const { request } = await import('@/api/client');
  return request<ChangesResponse>(`/admin/riot/changes?${query.toString()}`, { signal });
}

async function decideChange(id: number, action: 'approve' | 'reject', signal?: AbortSignal) {
  const { request } = await import('@/api/client');
  return request<{ warnings?: string[] }>(`/admin/riot/changes/${id}/${action}`, {
    method: 'POST',
    signal,
  });
}

async function decideBulk(ids: number[], action: 'approve' | 'reject') {
  const { request } = await import('@/api/client');
  return request<{ results: { id: number; outcome: string }[]; counts: Record<string, number> }>(
    '/admin/riot/changes/bulk',
    { method: 'POST', body: { ids, action } },
  );
}

function langOf(i18n: { language: string }): Lang {
  return i18n.language.split('-')[0] === 'en' ? 'en' : 'es';
}

/** Riot change review (F13-g S1-S7): filter, review one by one or in bulk. */
export function ChangesPage() {
  const { t, i18n } = useTranslation('admin');
  const { t: common } = useTranslation('common');
  const lang = langOf(i18n);
  const offline = !useOnline();
  const phone = useMediaQuery(down('md'));
  const desktop = useMediaQuery(up('lg'));
  const wide = useMediaQuery(up('2xl'));
  const queryClient = useQueryClient();
  const [params] = useSearchParams();
  // latest search asked for, not the rendered one: quick changes in a row must all stay (L6)
  const { setSearchParams: setParams } = useSearchNavigation();
  const [search, setSearch] = useState(params.get('q') ?? '');
  const [selected, setSelected] = useState<number[]>([]);
  const [detail, setDetail] = useState<AdminChange | null>(null);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [bulkAction, setBulkAction] = useState<'approve' | 'reject'>('approve');
  useDocumentTitle(t('changes.title'));

  useEffect(() => {
    const timer = setTimeout(() => {
      setParams(
        (previous) => {
          const next = new URLSearchParams(previous);
          if (search) next.set('q', search);
          else next.delete('q');
          next.delete('page');
          // Skip no-op navigations: they remount and drop element handles.
          if (next.toString() === previous.toString()) return previous;
          return next;
        },
        { replace: true },
      );
    }, 300);
    return () => clearTimeout(timer);
  }, [search, setParams]);

  const query = useQuery({
    queryKey: ['admin', 'changes', params.toString()],
    queryFn: ({ signal }) => fetchChanges(params, signal),
  });
  const setsQuery = useQuery({
    queryKey: ['admin', 'sets'],
    queryFn: ({ signal }) => listAdminSets(signal),
  });
  const refresh = () => {
    setSelected([]);
    void queryClient.invalidateQueries({ queryKey: ['admin', 'changes'] });
    void queryClient.invalidateQueries({ queryKey: ['admin', 'overview'] });
  };

  const decide = useMutation({
    mutationFn: ({ id, action }: { id: number; action: 'approve' | 'reject' }) =>
      decideChange(id, action),
    onSuccess: (body, { action }) => {
      if (action === 'approve' && body.warnings?.includes('image_download_failed')) {
        pushToast({ kind: 'info', message: t('changes.imageWarning') });
      }
      void refresh();
    },
    onError: (error: unknown) => {
      pushToast({ kind: 'error', message: translateError(error, i18n) });
      void refresh();
    },
  });

  const decideMany = useMutation({
    mutationFn: ({ ids, action }: { ids: number[]; action: 'approve' | 'reject' }) =>
      decideBulk(ids, action),
    onSuccess: (body) => {
      const c = body.counts;
      pushToast({
        kind: 'success',
        message: t('changes.bulkResult', {
          approved: c.approved ?? 0,
          rejected: c.rejected ?? 0,
          stale: c.stale ?? 0,
          decided: c.decided ?? 0,
        }),
      });
      setBulkOpen(false);
      void refresh();
    },
    onError: (error: unknown) => {
      setBulkOpen(false);
      pushToast({ kind: 'error', message: translateError(error, i18n) });
    },
  });

  const setParam = (key: string, value: string | null) =>
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        next.delete('page');
        if (value === null || value === '') next.delete(key);
        else next.set(key, value);
        return next;
      },
      { replace: true },
    );

  if (query.isPending) {
    return (
      <>
        <PageHeader title={t('changes.title')} subtitle={t('changes.subtitle')} />
        <Skeleton label={t('changes.title')} lines={4} />
      </>
    );
  }

  if (query.isError || !query.data) {
    return (
      <>
        <PageHeader title={t('changes.title')} subtitle={t('changes.subtitle')} />
        <ErrorState message={common('errorState.title')} onRetry={() => void query.refetch()} />
      </>
    );
  }

  const { items, meta } = query.data;
  const pendingOnPage = items.filter((item) => item.status === 'pending').map((item) => item.id);
  const allChecked = pendingOnPage.length > 0 && pendingOnPage.every((id) => selected.includes(id));
  const toggle = (id: number, checked: boolean) => {
    setSelected((current) =>
      checked ? [...current, id] : current.filter((other) => other !== id),
    );
    if (checked) {
      const row = items.find((item) => item.id === id);
      if (row) setDetail(row);
    } else if (detail?.id === id) {
      setDetail(null);
    }
  };
  const togglePage = (checked: boolean) => {
    if (checked) {
      setSelected((current) => [...new Set([...current, ...pendingOnPage])]);
      const first = items.find((item) => pendingOnPage.includes(item.id));
      if (first) setDetail(first);
    } else {
      setSelected((current) => current.filter((id) => !pendingOnPage.includes(id)));
      if (detail && pendingOnPage.includes(detail.id)) setDetail(null);
    }
  };
  const statusOptions: SegmentedOption<string>[] = STATUSES.map((status) => ({
    value: status,
    label: t(`changes.status.${status}` as 'changes.status.pending'),
  }));

  return (
    <>
      <PageHeader title={t('changes.title')} subtitle={t('changes.subtitle')} />
      <div className={styles.toolbar}>
        <SegmentedControl
          label={t('changes.statusLabel')}
          showLabel
          options={statusOptions}
          value={params.get('status') ?? 'pending'}
          onChange={(status) => setParam('status', status)}
        />
        <label className={styles.filterField}>
          {t('cards.columns.set')}
          <Select
            aria-label={t('cards.columns.set')}
            value={params.get('set') ?? ''}
            disabled={offline}
            onChange={(event) => setParam('set', event.target.value || null)}
          >
            <option value="">{t('cards.filters.allSets')}</option>
            {sortSetsNewestFirst(setsQuery.data ?? [], (set) => set.release_date).map((set) => (
              <option key={set.id} value={set.id}>
                {set.id}
              </option>
            ))}
          </Select>
        </label>
        <label className={styles.filterField}>
          {t('changes.columns.field')}
          <Select
            aria-label={t('changes.columns.field')}
            value={params.get('field') ?? ''}
            disabled={offline}
            onChange={(event) => setParam('field', event.target.value || null)}
          >
            <option value="">{t('changes.allFields')}</option>
            {FIELDS.map((field) => (
              <option key={field} value={field}>
                {t(`changes.field.${field}` as 'changes.field.rbcar_name')}
              </option>
            ))}
          </Select>
        </label>
        <label className={styles.filterField}>
          {t('changes.perPage')}
          <Select
            aria-label={t('changes.perPage')}
            value={params.get('per_page') ?? DEFAULT_PAGE_SIZE}
            disabled={offline}
            onChange={(event) =>
              setParam(
                'per_page',
                event.target.value === DEFAULT_PAGE_SIZE ? null : event.target.value,
              )
            }
          >
            {PAGE_SIZES.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </Select>
        </label>
        <label className={styles.filterField}>
          {t('changes.search')}
          <Input
            aria-label={t('changes.search')}
            value={search}
            disabled={offline}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
      </div>
      {items.length === 0 ? (
        <EmptyState
          title={t('changes.title')}
          body={
            (params.get('status') ?? 'pending') === 'pending'
              ? t('changes.emptyPending')
              : t('changes.emptyOther')
          }
        />
      ) : desktop ? (
        <div className={wide ? styles.layout : undefined}>
          <div className={styles.main}>
            {/* Long values wrap to the width, so the table scrolls with the page (one scroll). */}
            <TableScroll fit role="region" aria-label={t('changes.caption')}>
              <table className={styles.table}>
                <caption className="sr-only">{t('changes.caption')}</caption>
                <thead>
                  <tr>
                    {!phone && (
                      <th scope="col">
                        <Checkbox
                          label={t('changes.selectPage')}
                          hideLabel
                          checked={allChecked}
                          disabled={offline || pendingOnPage.length === 0}
                          onChange={(event) => togglePage(event.target.checked)}
                        />
                      </th>
                    )}
                    <th scope="col">{t('changes.columns.card')}</th>
                    <th scope="col">{t('changes.columns.field')}</th>
                    <th scope="col">{t('changes.columns.change')}</th>
                    <th scope="col">{t('changes.columns.detected')}</th>
                    <th scope="col">{t('changes.columns.actions')}</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={item.id}>
                      {!phone && (
                        <td>
                          {item.status === 'pending' && (
                            <Checkbox
                              label={t('changes.approveOne', {
                                name: item.card_name ?? item.card_id,
                              })}
                              hideLabel
                              checked={selected.includes(item.id)}
                              disabled={offline}
                              onChange={(event) => toggle(item.id, event.target.checked)}
                            />
                          )}
                        </td>
                      )}
                      <td className={styles.cardCell}>
                        {item.image_src && (
                          <img src={item.image_src} alt="" className={styles.thumb} />
                        )}
                        <div>{item.card_name}</div>
                        <div>
                          {item.set_id} · #{item.card_id}
                        </div>
                      </td>
                      <td>
                        {t(
                          `changes.field.${item.field as FieldName}` as 'changes.field.rbcar_name',
                        )}
                      </td>
                      <td className={styles.valueCell}>
                        <ValueDiff
                          oldValue={item.old_value}
                          newValue={item.new_value}
                          layout="inline"
                        />
                      </td>
                      <td>{item.detected_at ? formatDate(item.detected_at, lang) : '—'}</td>
                      <td>
                        <span className={styles.actions}>
                          <RowActions
                            item={item}
                            disabled={offline}
                            onDecide={(id, action) => decide.mutate({ id, action })}
                          />
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableScroll>
            <Pagination
              page={meta.page}
              pages={meta.pages}
              onChange={(page) => setParam('page', String(page))}
            />
          </div>
          {wide && (
            <SidePanel
              id="admin-changes-detail"
              kind="detail"
              side="end"
              label={t('panels.detail')}
              className={styles.editorPanel}
            >
              {detail ? <ChangeDetail item={detail} /> : <p>{t('sets.pickOne')}</p>}
            </SidePanel>
          )}
        </div>
      ) : (
        <div className={styles.cards}>
          {items.map((item) => (
            <article key={item.id} className={styles.card}>
              <div className={styles.cardHead}>
                {item.image_src && <img src={item.image_src} alt="" className={styles.thumb} />}
                <h2 className={styles.rowTitle}>{item.card_name}</h2>
              </div>
              <p className={styles.cardMeta}>
                {item.set_id} · #{item.card_id} ·{' '}
                {t(`changes.field.${item.field as FieldName}` as 'changes.field.rbcar_name')}
              </p>
              <ValueDiff oldValue={item.old_value} newValue={item.new_value} layout="stacked" />
              <div className={styles.cardActions}>
                <RowActions
                  item={item}
                  disabled={offline}
                  onDecide={(id, action) => decide.mutate({ id, action })}
                />
              </div>
            </article>
          ))}
          <Pagination
            page={meta.page}
            pages={meta.pages}
            onChange={(page) => setParam('page', String(page))}
          />
        </div>
      )}
      {selected.length > 0 && !phone && (
        <div
          className={styles.bulkBar}
          role="region"
          aria-label={t('changes.selected_other', { count: selected.length })}
        >
          <span>{t('changes.selected', { count: selected.length })}</span>
          <Button
            disabled={offline}
            onClick={() => {
              setBulkAction('approve');
              setBulkOpen(true);
            }}
          >
            {t('changes.approveSelected')}
          </Button>
          <Button
            variant="danger"
            disabled={offline}
            onClick={() => {
              setBulkAction('reject');
              setBulkOpen(true);
            }}
          >
            {t('changes.rejectSelected')}
          </Button>
        </div>
      )}
      <BulkConfirm
        open={bulkOpen}
        action={bulkAction}
        count={selected.length}
        onClose={() => {
          setBulkOpen(false);
          setBulkAction('approve');
        }}
        onConfirm={(action) =>
          decideMany.mutate({ ids: [...selected].sort((a, b) => a - b), action })
        }
      />
    </>
  );

  function RowActions({
    item,
    disabled,
    onDecide,
  }: {
    item: AdminChange;
    disabled: boolean;
    onDecide: (id: number, action: 'approve' | 'reject') => void;
  }) {
    if (item.status !== 'pending') return null;
    return (
      <>
        <Button
          disabled={disabled}
          onClick={() => onDecide(item.id, 'approve')}
          aria-label={t('changes.approveOne', { name: item.card_name ?? item.card_id })}
        >
          {t('changes.approve')}
        </Button>
        <Button
          disabled={disabled}
          variant="danger"
          onClick={() => onDecide(item.id, 'reject')}
          aria-label={t('changes.rejectOne', { name: item.card_name ?? item.card_id })}
        >
          {t('changes.reject')}
        </Button>
      </>
    );
  }

  function ChangeDetail({ item }: { item: AdminChange }) {
    return (
      <div>
        {item.image_src && <img src={item.image_src} alt="" className={styles.detailImage} />}
        <h2 className={styles.editorTitle}>{item.card_name}</h2>
        <p className={styles.cardMeta}>
          {item.set_id} · #{item.card_id}
        </p>
        <ValueDiff
          oldValue={item.old_value}
          newValue={item.new_value}
          layout={LONG_FIELDS.includes(item.field) ? 'side' : 'stacked'}
        />
      </div>
    );
  }

  function BulkConfirm({
    open,
    action,
    count,
    onClose,
    onConfirm,
  }: {
    open: boolean;
    action: 'approve' | 'reject';
    count: number;
    onClose: () => void;
    onConfirm: (action: 'approve' | 'reject') => void;
  }) {
    const title =
      action === 'approve'
        ? count === 1
          ? t('changes.confirm.approve_one', { count })
          : t('changes.confirm.approve_other', { count })
        : count === 1
          ? t('changes.confirm.reject_one', { count })
          : t('changes.confirm.reject_other', { count });
    return (
      <ConfirmDialog
        open={open}
        title={title}
        message={t('changes.confirm.body')}
        confirmLabel={
          action === 'approve' ? t('changes.approveSelected') : t('changes.rejectSelected')
        }
        cancelLabel={common('actions.cancel')}
        danger={action === 'reject'}
        onConfirm={() => onConfirm(action)}
        onCancel={onClose}
      />
    );
  }
}
