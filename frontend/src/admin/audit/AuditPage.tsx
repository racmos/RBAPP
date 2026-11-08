import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Link, useSearchParams } from 'react-router';
import { DebouncedInput, useSearchNavigation } from '@/catalog';
import {
  getAdminAuditFacets,
  listAdminAudit,
  type AdminAuditFacets,
  type AdminAuditItem,
} from '@/api/endpoints';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Input } from '@/components/ui/Input';
import { PageHeader } from '@/components/ui/PageHeader';
import { Pagination } from '@/components/ui/Pagination';
import { Select } from '@/components/ui/Select';
import { Skeleton } from '@/components/ui/Skeleton';
import { TableScroll } from '@/components/ui/TableScroll';
import { useDocumentTitle } from '@/i18n';
import { down } from '@/lib/breakpoints';
import { useMediaQuery } from '@/lib/useMediaQuery';
import { formatStamp } from '../cardmarket/parts';
import {
  DEFAULT_PAGE_SIZE,
  PAGE_SIZES,
  actionLabelKey,
  auditApiQuery,
  targetLabelKey,
  targetLink,
} from './format';
import styles from './AuditPage.module.css';

/**
 * Admin audit (CM-e): every admin write (`rbadminaudit`), newest first. Read-only; the filters
 * (action, actor, target type, dates, page size) live in the URL, as do `target_id` and `page`.
 */
export function AuditPage() {
  const { t } = useTranslation('admin');
  const { t: common } = useTranslation('common');
  const phone = useMediaQuery(down('md'));
  const [params] = useSearchParams();
  const { setSearchParams } = useSearchNavigation();
  useDocumentTitle(t('audit.title'));

  const apiQuery = auditApiQuery(params);
  const query = useQuery({
    queryKey: ['admin', 'audit', apiQuery],
    queryFn: ({ signal }) => listAdminAudit(apiQuery, signal),
    // the table stays while the next filter or page loads (the filters keep their focus)
    placeholderData: keepPreviousData,
  });
  const facets = useQuery({
    queryKey: ['admin', 'audit', 'facets'],
    queryFn: ({ signal }) => getAdminAuditFacets(signal),
  });

  const setParam = (key: string, value: string | null) =>
    setSearchParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        next.delete('page');
        if (value === null || value === '') next.delete(key);
        else next.set(key, value);
        return next;
      },
      { replace: true },
    );
  const setPage = (page: number) =>
    setSearchParams((previous) => {
      const next = new URLSearchParams(previous);
      if (page > 1) next.set('page', String(page));
      else next.delete('page');
      return next;
    });

  let body;
  if (query.isPending) {
    body = <Skeleton label={t('audit.title')} lines={4} />;
  } else if (query.isError) {
    body = <ErrorState message={common('errorState.title')} onRetry={() => void query.refetch()} />;
  } else if (query.data.items.length === 0) {
    body = <EmptyState title={t('audit.emptyTitle')} body={t('audit.emptyBody')} />;
  } else {
    const { items, meta } = query.data;
    body = (
      <>
        {phone ? (
          <div className={styles.cards}>
            {items.map((item) => (
              <article key={item.id} className={styles.card} aria-labelledby={`audit-${item.id}`}>
                <h2 id={`audit-${item.id}`} className={styles.cardTitle}>
                  <ActionLabel action={item.action} />
                </h2>
                <p className={styles.cardMeta}>
                  {formatStamp(item.created_at)} · <Actor item={item} />
                </p>
                <p className={styles.cardMeta}>
                  <Target item={item} />
                </p>
                <Details detail={item.detail} />
              </article>
            ))}
          </div>
        ) : (
          <TableScroll fit role="region" aria-label={t('audit.caption')}>
            <table className={styles.table}>
              <caption className="sr-only">{t('audit.caption')}</caption>
              <thead>
                <tr>
                  <th scope="col">{t('audit.columns.time')}</th>
                  <th scope="col">{t('audit.columns.actor')}</th>
                  <th scope="col">{t('audit.columns.action')}</th>
                  <th scope="col">{t('audit.columns.target')}</th>
                  <th scope="col">{t('audit.columns.details')}</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td className={styles.time}>{formatStamp(item.created_at)}</td>
                    <td>
                      <Actor item={item} />
                    </td>
                    <td>
                      <ActionLabel action={item.action} />
                    </td>
                    <td>
                      <Target item={item} />
                    </td>
                    <td className={styles.detailCell}>
                      <Details detail={item.detail} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableScroll>
        )}
        <Pagination page={meta.page} pages={meta.pages} onChange={setPage} />
      </>
    );
  }

  return (
    <>
      <PageHeader title={t('audit.title')} subtitle={t('audit.subtitle')} />
      <Filters
        params={params}
        facets={facets.data}
        setParam={setParam}
        onActor={(next) => setParam('actor', next.trim() || null)}
      />
      {body}
    </>
  );
}

// Components live at module level: one declared inside AuditPage would be a new type on every
// render, so React would remount it (and the actor input would lose its focus).
function Filters({
  params,
  facets,
  setParam,
  onActor,
}: {
  params: URLSearchParams;
  facets: AdminAuditFacets | undefined;
  setParam: (key: string, value: string | null) => void;
  onActor: (next: string) => void;
}) {
  const { t } = useTranslation('admin');
  const action = params.get('action') ?? '';
  const targetType = params.get('target_type') ?? '';
  const actions = facets?.actions ?? [];
  const targets = facets?.target_types ?? [];
  return (
    <div className={styles.toolbar}>
      <label className={styles.filterField}>
        {t('audit.filters.action')}
        <Select
          aria-label={t('audit.filters.action')}
          value={action}
          onChange={(event) => setParam('action', event.target.value || null)}
        >
          <option value="">{t('audit.filters.allActions')}</option>
          {/* the URL may name an action the facets do not list (yet): keep it selectable */}
          {action && !actions.some((item) => item.action === action) && (
            <option value={action}>{action}</option>
          )}
          {actions.map((item) => {
            const key = actionLabelKey(item.action);
            return (
              <option key={item.action} value={item.action}>
                {t('audit.filters.actionOption', {
                  label: key ? t(key) : item.action,
                  count: item.count,
                })}
              </option>
            );
          })}
        </Select>
      </label>
      <label className={styles.filterField}>
        {t('audit.filters.actor')}
        <DebouncedInput
          aria-label={t('audit.filters.actor')}
          value={params.get('actor') ?? ''}
          onCommit={onActor}
        />
      </label>
      <label className={styles.filterField}>
        {t('audit.filters.targetType')}
        <Select
          aria-label={t('audit.filters.targetType')}
          value={targetType}
          onChange={(event) => setParam('target_type', event.target.value || null)}
        >
          <option value="">{t('audit.filters.allTargets')}</option>
          {targetType && !targets.some((item) => item.target_type === targetType) && (
            <option value={targetType}>{targetType}</option>
          )}
          {targets.map((item) => {
            const key = targetLabelKey(item.target_type);
            return (
              <option key={item.target_type} value={item.target_type}>
                {t('audit.filters.actionOption', {
                  label: key ? t(key) : item.target_type,
                  count: item.count,
                })}
              </option>
            );
          })}
        </Select>
      </label>
      <label className={styles.filterField}>
        {t('audit.filters.from')}
        <Input
          type="date"
          value={params.get('from') ?? ''}
          max={params.get('to') ?? undefined}
          onChange={(event) => setParam('from', event.target.value || null)}
        />
      </label>
      <label className={styles.filterField}>
        {t('audit.filters.to')}
        <Input
          type="date"
          value={params.get('to') ?? ''}
          min={params.get('from') ?? undefined}
          onChange={(event) => setParam('to', event.target.value || null)}
        />
      </label>
      <label className={styles.filterField}>
        {t('audit.filters.perPage')}
        <Select
          aria-label={t('audit.filters.perPage')}
          value={params.get('per_page') ?? DEFAULT_PAGE_SIZE}
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
    </div>
  );
}

function ActionLabel({ action }: { action: string }) {
  const { t } = useTranslation('admin');
  const key = actionLabelKey(action);
  if (!key) return <code className={styles.code}>{action}</code>;
  return <span title={action}>{t(key)}</span>;
}

function Actor({ item }: { item: AdminAuditItem }) {
  const { t } = useTranslation('admin');
  if (!item.actor) return <span className={styles.system}>{t('audit.system')}</span>;
  return <span>{item.actor.username}</span>;
}

function Target({ item }: { item: AdminAuditItem }) {
  const { t } = useTranslation('admin');
  const key = targetLabelKey(item.target_type);
  const label = key ? t(key) : item.target_type;
  const text = item.target_id ? `${label} ${item.target_id}` : label;
  const to = targetLink(item);
  return to ? <Link to={to}>{text}</Link> : <span>{text}</span>;
}

function Details({ detail }: { detail: unknown }) {
  const { t } = useTranslation('admin');
  if (detail === null || detail === undefined) return <span aria-hidden="true">—</span>;
  return (
    <details className={styles.details}>
      <summary>{t('audit.details')}</summary>
      <pre className={styles.json}>{JSON.stringify(detail, null, 2)}</pre>
    </details>
  );
}
