import { useId, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import {
  applyCardmarketAutoMatch,
  previewCardmarketAutoMatch,
  type CardmarketProposed,
} from '@/api/endpoints';
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
import { formatMoney, formatNumber } from '@/lib/format';
import { apiQuery, cardRef } from './format';
import type { PanelProps } from './MatchingPage';
import { useSlotLabel } from './parts';
import { useRefreshCardmarket, useReview } from './queries';
import styles from './MatchingPage.module.css';

const REASONS = ['ambiguous', 'no_candidates', 'conflict', 'ignored_pair'] as const;
type Reason = (typeof REASONS)[number];
const isReason = (value: string): value is Reason => (REASONS as readonly string[]).includes(value);

/** "Auto-match": preview and apply the clear cases, and the doubtful ones to review (CM-b). */
export function AutoMatchPanel(props: PanelProps) {
  const { t, i18n } = useTranslation('admin');
  const { t: common } = useTranslation('common');
  const refresh = useRefreshCardmarket();
  const previewId = useId();
  const [confirming, setConfirming] = useState(false);
  const fail = (error: unknown) =>
    pushToast({ kind: 'error', message: translateError(error, i18n) });

  const preview = useMutation({ mutationFn: previewCardmarketAutoMatch, onError: fail });
  const apply = useMutation({
    mutationFn: applyCardmarketAutoMatch,
    onSuccess: () => {
      // the preview is stale once its clear cases are linked
      preview.reset();
      refresh();
    },
    onError: fail,
  });
  const clear = preview.data?.clear ?? 0;

  return (
    <>
      <section className={styles.section} aria-labelledby="matching-auto">
        <h2 id="matching-auto" className={styles.sectionTitle}>
          {t('matching.auto.title')}
        </h2>
        <p className={styles.help}>{t('matching.auto.intro')}</p>
        <div className={styles.rowActions}>
          <Button
            variant="ghost"
            disabled={props.offline}
            pending={preview.isPending}
            onClick={() => {
              apply.reset();
              preview.mutate();
            }}
          >
            {t('matching.auto.preview')}
          </Button>
          <Button
            disabled={props.offline || clear === 0 || apply.isPending}
            pending={apply.isPending}
            title={props.offline ? common('offline.editDisabled') : undefined}
            onClick={() => setConfirming(true)}
          >
            {t('matching.auto.apply')}
          </Button>
        </div>
        {apply.data && (
          <p role="status" className={styles.result}>
            {t('matching.auto.applied', {
              linked: formatNumber(apply.data.linked),
              remaining: formatNumber(apply.data.remaining_clear),
              doubtful: formatNumber(apply.data.doubtful),
            })}
          </p>
        )}
        {preview.data && (
          <section aria-labelledby={previewId} className={styles.preview}>
            <h3 id={previewId} className={styles.rowTitle}>
              {t('matching.auto.previewTitle')}
            </h3>
            <dl className={styles.pairs}>
              <div>
                <dt>{t('matching.auto.proposed')}</dt>
                <dd>{formatNumber(preview.data.proposed)}</dd>
              </div>
              <div>
                <dt>{t('matching.auto.clear')}</dt>
                <dd>{formatNumber(preview.data.clear)}</dd>
              </div>
              <div>
                <dt>{t('matching.auto.doubtful')}</dt>
                <dd>{formatNumber(preview.data.doubtful)}</dd>
              </div>
            </dl>
            {preview.data.links.length === 0 ? (
              <p className={styles.muted}>{t('matching.auto.noClear')}</p>
            ) : (
              <ProposedTable links={preview.data.links} />
            )}
          </section>
        )}
      </section>
      <ReviewSection {...props} />
      <ConfirmDialog
        open={confirming}
        title={t('matching.auto.confirmTitle', { count: clear })}
        message={t('matching.auto.confirmBody')}
        confirmLabel={t('matching.auto.apply')}
        cancelLabel={common('actions.cancel')}
        onCancel={() => setConfirming(false)}
        onConfirm={() => {
          setConfirming(false);
          apply.mutate();
        }}
      />
    </>
  );
}

function ProposedTable({ links }: { links: CardmarketProposed[] }) {
  const { t } = useTranslation('admin');
  const slotLabel = useSlotLabel();
  return (
    <TableScroll>
      <table className={styles.table}>
        <caption className="sr-only">{t('matching.auto.proposedCaption')}</caption>
        <thead>
          <tr>
            <th scope="col">{t('matching.auto.columns.product')}</th>
            <th scope="col">{t('matching.auto.columns.card')}</th>
            <th scope="col">{t('matching.auto.columns.slot')}</th>
            <th scope="col">{t('matching.auto.columns.price')}</th>
          </tr>
        </thead>
        <tbody>
          {links.map((link) => (
            <tr key={link.id_product}>
              <td>
                <span className={styles.cellStack}>
                  <span>{link.product_name}</span>
                  <span className={styles.muted}>#{link.id_product}</span>
                </span>
              </td>
              <td>
                <span className={styles.cellStack}>
                  <span className={styles.nowrap}>{cardRef(link.set_id, link.card_id)}</span>
                  <span className={styles.muted}>{link.card_name}</span>
                </span>
              </td>
              <td>{slotLabel(link.foil)}</td>
              <td className={styles.nowrap}>
                {link.low_price === null ? '—' : formatMoney(link.low_price)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </TableScroll>
  );
}

/** The doubtful cases of the latest load, by reason; each opens the link dialog. */
function ReviewSection({ params, setParam, setPage, offline, openDialog }: PanelProps) {
  const { t } = useTranslation('admin');
  const { t: common } = useTranslation('common');
  const query = useReview(apiQuery('review', params));
  const reasonLabel = (reason: string) =>
    isReason(reason) ? t(`matching.review.reasons.${reason}`) : reason;
  const counts = query.data?.meta.reasons ?? {};

  let body;
  if (query.isPending) {
    body = <Skeleton label={t('matching.review.caption')} lines={4} />;
  } else if (query.isError) {
    body = <ErrorState message={common('errorState.title')} onRetry={() => void query.refetch()} />;
  } else if (query.data.items.length === 0) {
    body = (
      <EmptyState title={t('matching.review.emptyTitle')} body={t('matching.review.emptyBody')} />
    );
  } else {
    const { items, meta } = query.data;
    body = (
      <>
        <ul aria-label={t('matching.review.caption')} className={styles.rows}>
          {items.map((item) => (
            <li key={`${item.product_id}-${item.reason}`} className={styles.row}>
              <div className={styles.rowHead}>
                <h3 className={styles.rowTitle}>{item.name}</h3>
                <span className={styles.muted}>#{item.product_id}</span>
                <Badge tone="warning">{reasonLabel(item.reason)}</Badge>
              </div>
              <span className={styles.muted}>
                {item.candidates.length === 0
                  ? t('matching.review.noCandidates')
                  : t('matching.review.candidates', {
                      list: item.candidates
                        .map((one) => `${cardRef(one.set, one.id)} ${one.name}`)
                        .join('; '),
                    })}
              </span>
              <span className={styles.rowActions}>
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={offline}
                  aria-label={t('matching.toLink.chooseFor', { name: item.name })}
                  onClick={() => openDialog({ id_product: item.product_id, name: item.name })}
                >
                  {t('matching.toLink.choose')}
                </Button>
                {item.reason === 'no_candidates' && (
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={offline}
                    aria-label={t('matching.toLink.createFor', { name: item.name })}
                    onClick={() =>
                      openDialog({ id_product: item.product_id, name: item.name, mode: 'create' })
                    }
                  >
                    {t('matching.toLink.create')}
                  </Button>
                )}
              </span>
            </li>
          ))}
        </ul>
        {meta.pages > 1 && <Pagination page={meta.page} pages={meta.pages} onChange={setPage} />}
      </>
    );
  }

  return (
    <section className={styles.section} aria-labelledby="matching-review">
      <h2 id="matching-review" className={styles.sectionTitle}>
        {t('matching.review.title')}
      </h2>
      <div className={styles.filters}>
        <label className={styles.filterField}>
          {t('matching.review.reason')}
          <Select
            aria-label={t('matching.review.reason')}
            value={params.get('reason') ?? ''}
            onChange={(event) => setParam('reason', event.target.value || null)}
          >
            <option value="">{t('matching.review.all')}</option>
            {REASONS.map((reason) => (
              <option key={reason} value={reason}>
                {t('matching.review.withCount', {
                  label: reasonLabel(reason),
                  n: counts[reason] ?? 0,
                })}
              </option>
            ))}
          </Select>
        </label>
      </div>
      {body}
    </section>
  );
}
