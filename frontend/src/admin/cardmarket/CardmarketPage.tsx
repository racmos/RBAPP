import { useEffect, useRef, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { ApiError } from '@/api/errors';
import {
  startCardmarketLoad,
  type CardmarketLoadDay,
  type CardmarketStatus,
} from '@/api/endpoints';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Modal } from '@/components/ui/Modal';
import { PageHeader } from '@/components/ui/PageHeader';
import { Sheet } from '@/components/ui/Sheet';
import { Skeleton } from '@/components/ui/Skeleton';
import { TableScroll } from '@/components/ui/TableScroll';
import { pushToast } from '@/components/ui/toastStore';
import { translateError, useDocumentTitle } from '@/i18n';
import { down } from '@/lib/breakpoints';
import { formatDate, formatNumber } from '@/lib/format';
import { useMediaQuery } from '@/lib/useMediaQuery';
import { useOnline } from '@/lib/useOnline';
import { DayDetail } from './DayDetail';
import { isActiveJob, secondsBetween } from './format';
import {
  DayStatusBadge,
  FileChips,
  JobStatusBadge,
  NewProducts,
  formatStamp,
  useDurationText,
} from './parts';
import {
  cardmarketKeys,
  useCardmarketJobs,
  useCardmarketLoads,
  useCardmarketStatus,
} from './queries';
import styles from './CardmarketPage.module.css';

const FIRST_DAYS = 30;
const MAX_DAYS = 120;

/** Cardmarket admin (CM-a): the log of the daily price load, its status and "Load now". */
export function CardmarketPage() {
  const { t } = useTranslation('admin');
  const queryClient = useQueryClient();
  const phone = useMediaQuery(down('md'));
  const [openDate, setOpenDate] = useState<string | null>(null);
  useDocumentTitle(t('cardmarket.title'));

  // When the running load ends, the list, the open day and the recent jobs change.
  const status = useCardmarketStatus();
  const active = isActiveJob(status.data?.job?.status);
  const wasActive = useRef(active);
  useEffect(() => {
    if (wasActive.current && !active) {
      void queryClient.invalidateQueries({ queryKey: [...cardmarketKeys.all, 'loads'] });
      void queryClient.invalidateQueries({ queryKey: [...cardmarketKeys.all, 'day'] });
      void queryClient.invalidateQueries({ queryKey: cardmarketKeys.jobs });
    }
    wasActive.current = active;
  }, [active, queryClient]);

  const title = openDate
    ? t('cardmarket.detail.title', { date: formatDate(openDate) })
    : t('cardmarket.details');
  const close = () => setOpenDate(null);

  return (
    <>
      <PageHeader title={t('cardmarket.title')} subtitle={t('cardmarket.subtitle')} />
      <StatusHeader />
      <LoadDays phone={phone} onOpen={setOpenDate} />
      <RecentJobs />
      {phone ? (
        <Sheet open={openDate !== null} title={title} onClose={close}>
          {openDate && <DayDetail date={openDate} />}
        </Sheet>
      ) : (
        <Modal open={openDate !== null} title={title} onClose={close} variant="side">
          {openDate && <DayDetail date={openDate} />}
        </Modal>
      )}
    </>
  );
}

function StatusHeader() {
  const { t, i18n } = useTranslation('admin');
  const { t: common } = useTranslation('common');
  const queryClient = useQueryClient();
  const offline = !useOnline();
  const query = useCardmarketStatus();
  const [confirming, setConfirming] = useState(false);

  const load = useMutation({
    mutationFn: startCardmarketLoad,
    onSuccess: ({ job }) => {
      pushToast({ kind: 'success', message: t('cardmarket.queued') });
      // The queued job starts the status polling at once.
      queryClient.setQueryData<CardmarketStatus>(cardmarketKeys.status, (previous) =>
        previous ? { ...previous, job } : previous,
      );
      void queryClient.invalidateQueries({ queryKey: cardmarketKeys.jobs });
    },
    onError: (error: unknown) => {
      const running =
        error instanceof ApiError && error.status === 409 && error.code === 'job_running';
      pushToast({
        kind: 'error',
        message: running ? t('cardmarket.loadRunning') : translateError(error, i18n),
      });
      void queryClient.invalidateQueries({ queryKey: cardmarketKeys.status });
    },
  });

  const heading = (
    <h2 id="cardmarket-status" className={styles.sectionTitle}>
      {t('cardmarket.statusTitle')}
    </h2>
  );

  if (query.isPending) {
    return (
      <section className={styles.section} aria-labelledby="cardmarket-status">
        {heading}
        <Skeleton label={t('cardmarket.statusTitle')} />
      </section>
    );
  }
  if (query.isError) {
    return (
      <section className={styles.section} aria-labelledby="cardmarket-status">
        {heading}
        <ErrorState message={common('errorState.title')} onRetry={() => void query.refetch()} />
      </section>
    );
  }

  const { last_load: last, job } = query.data;
  const busy = isActiveJob(job?.status) || load.isPending;
  return (
    <section className={styles.section} aria-labelledby="cardmarket-status">
      {heading}
      <div className={styles.status}>
        <dl className={styles.facts}>
          <div className={styles.fact}>
            <dt>{t('cardmarket.lastLoad')}</dt>
            <dd className={styles.factValue}>
              {last ? (
                <>
                  <span>{formatDate(last.date)}</span>
                  <DayStatusBadge status={last.status} />
                </>
              ) : (
                <span>{t('cardmarket.noLoad')}</span>
              )}
              {query.data.loaded_today ? (
                <Badge tone="success">{t('cardmarket.loadedToday')}</Badge>
              ) : (
                <Badge tone="warning">{t('cardmarket.notToday')}</Badge>
              )}
            </dd>
          </div>
          <div className={styles.fact}>
            <dt>{t('cardmarket.pricesAsOf')}</dt>
            <dd>{query.data.prices_as_of ? formatDate(query.data.prices_as_of) : '—'}</dd>
          </div>
          <div className={styles.fact}>
            <dt>{t('cardmarket.latestJob')}</dt>
            <dd className={styles.factValue}>
              {job ? (
                <>
                  <JobStatusBadge status={job.status} />
                  <span>#{job.id}</span>
                  <JobTimes
                    queued={job.queued_at}
                    started={job.started_at}
                    finished={job.finished_at}
                  />
                  {job.status === 'error' && job.message && (
                    <span className={styles.error}>{job.message}</span>
                  )}
                </>
              ) : (
                <span>{t('cardmarket.noJob')}</span>
              )}
            </dd>
          </div>
        </dl>
        <p className={styles.counters}>
          <span>{t('cardmarket.unmatched', { count: query.data.unmatched })}</span>
          <span>
            {t('cardmarket.unmappedExpansions', { count: query.data.unmapped_expansions })}
          </span>
        </p>
        <div>
          <Button
            disabled={offline || busy}
            pending={load.isPending}
            title={offline ? common('offline.editDisabled') : undefined}
            onClick={() => setConfirming(true)}
          >
            {t('cardmarket.loadNow')}
          </Button>
        </div>
      </div>
      <ConfirmDialog
        open={confirming}
        title={t('cardmarket.confirm.title')}
        message={t('cardmarket.confirm.body')}
        confirmLabel={t('cardmarket.loadNow')}
        cancelLabel={common('actions.cancel')}
        onCancel={() => setConfirming(false)}
        onConfirm={() => {
          setConfirming(false);
          load.mutate();
        }}
      />
    </section>
  );
}

/** "Queued … · Started … · Finished … · Took 10 s", only the parts that exist. */
function JobTimes({
  queued,
  started,
  finished,
}: {
  queued: string | null;
  started: string | null;
  finished: string | null;
}) {
  const { t } = useTranslation('admin');
  const duration = useDurationText();
  const seconds = secondsBetween(started, finished);
  const parts = [
    queued && t('cardmarket.times.queued', { time: formatStamp(queued) }),
    started && t('cardmarket.times.started', { time: formatStamp(started) }),
    finished && t('cardmarket.times.finished', { time: formatStamp(finished) }),
    seconds !== null && t('cardmarket.times.took', { duration: duration(seconds) }),
  ].filter(Boolean);
  if (parts.length === 0) return null;
  return <span className={styles.muted}>{parts.join(' · ')}</span>;
}

function LoadDays({ phone, onOpen }: { phone: boolean; onOpen: (date: string) => void }) {
  const { t } = useTranslation('admin');
  const { t: common } = useTranslation('common');
  const duration = useDurationText();
  const [limit, setLimit] = useState(FIRST_DAYS);
  const query = useCardmarketLoads(limit);

  const heading = (
    <h2 id="cardmarket-days" className={styles.sectionTitle}>
      {t('cardmarket.daysTitle')}
    </h2>
  );
  let body;
  if (query.isPending) {
    body = <Skeleton label={t('cardmarket.daysTitle')} lines={5} />;
  } else if (query.isError) {
    body = <ErrorState message={common('errorState.title')} onRetry={() => void query.refetch()} />;
  } else if (query.data.items.length === 0) {
    body = <EmptyState title={t('cardmarket.emptyTitle')} body={t('cardmarket.emptyBody')} />;
  } else {
    const items = query.data.items;
    const detailsButton = (day: CardmarketLoadDay) => (
      <Button
        size="sm"
        variant="ghost"
        aria-label={t('cardmarket.detailsOf', { date: formatDate(day.date) })}
        onClick={() => onOpen(day.date)}
      >
        {t('cardmarket.details')}
      </Button>
    );
    body = (
      <>
        {phone ? (
          <ul aria-label={t('cardmarket.caption')} className={styles.cards}>
            {items.map((day) => (
              <li key={day.date} className={styles.card}>
                <span className={styles.cardHead}>
                  <strong>{formatDate(day.date)}</strong>
                  <DayStatusBadge status={day.status} />
                </span>
                <FileChips files={day.files} />
                <dl className={styles.cardFacts}>
                  <div>
                    <dt>{t('cardmarket.columns.products')}</dt>
                    <dd>{formatNumber(day.products_total)}</dd>
                  </div>
                  <div>
                    <dt>{t('cardmarket.columns.newProducts')}</dt>
                    <dd>
                      <NewProducts value={day.new_products} />
                    </dd>
                  </div>
                  {day.unmatched_singles !== null && (
                    <div>
                      <dt>{t('cardmarket.columns.unmatched')}</dt>
                      <dd>{formatNumber(day.unmatched_singles)}</dd>
                    </div>
                  )}
                  <div>
                    <dt>{t('cardmarket.columns.duration')}</dt>
                    <dd>{duration(day.duration_seconds)}</dd>
                  </div>
                </dl>
                {detailsButton(day)}
              </li>
            ))}
          </ul>
        ) : (
          <TableScroll>
            <table className={styles.table}>
              <caption className="sr-only">{t('cardmarket.caption')}</caption>
              <thead>
                <tr>
                  <th scope="col">{t('cardmarket.columns.date')}</th>
                  <th scope="col">{t('cardmarket.columns.status')}</th>
                  <th scope="col">{t('cardmarket.columns.files')}</th>
                  <th scope="col">{t('cardmarket.columns.products')}</th>
                  <th scope="col">{t('cardmarket.columns.newProducts')}</th>
                  <th scope="col">{t('cardmarket.columns.unmatched')}</th>
                  <th scope="col">{t('cardmarket.columns.duration')}</th>
                  <th scope="col">{t('cardmarket.columns.actions')}</th>
                </tr>
              </thead>
              <tbody>
                {items.map((day) => (
                  <tr key={day.date}>
                    <td className={styles.nowrap}>{formatDate(day.date)}</td>
                    <td>
                      <DayStatusBadge status={day.status} />
                    </td>
                    <td>
                      <FileChips files={day.files} />
                    </td>
                    <td>{formatNumber(day.products_total)}</td>
                    <td>
                      <NewProducts value={day.new_products} />
                    </td>
                    <td>
                      {day.unmatched_singles === null ? '—' : formatNumber(day.unmatched_singles)}
                    </td>
                    <td className={styles.nowrap}>{duration(day.duration_seconds)}</td>
                    <td>{detailsButton(day)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableScroll>
        )}
        {items.length >= limit && limit < MAX_DAYS && (
          <Button
            variant="ghost"
            className={styles.more}
            pending={query.isFetching}
            onClick={() => setLimit(MAX_DAYS)}
          >
            {t('cardmarket.showMore')}
          </Button>
        )}
      </>
    );
  }

  return (
    <section className={styles.section} aria-labelledby="cardmarket-days">
      {heading}
      {body}
    </section>
  );
}

/** The last `daily_prices` runs: a failed load shows here even without a history row. */
function RecentJobs() {
  const { t } = useTranslation('admin');
  const { t: common } = useTranslation('common');
  const duration = useDurationText();
  const query = useCardmarketJobs();

  let body;
  if (query.isPending) {
    body = <Skeleton label={t('cardmarket.recentTitle')} />;
  } else if (query.isError) {
    body = <ErrorState message={common('errorState.title')} onRetry={() => void query.refetch()} />;
  } else if (query.data.items.length === 0) {
    body = <p className={styles.muted}>{t('cardmarket.recentEmpty')}</p>;
  } else {
    body = (
      <ul className={styles.jobs}>
        {query.data.items.map((job) => {
          const seconds = secondsBetween(job.started_at, job.finished_at);
          return (
            <li key={job.id} className={styles.job}>
              <span className={styles.jobHead}>
                <JobStatusBadge status={job.status} />
                <span>#{job.id}</span>
                <span>{formatStamp(job.requested_at)}</span>
                {seconds !== null && <span>{duration(seconds)}</span>}
                <span className={styles.muted}>
                  {job.requested_by
                    ? t('cardmarket.requestedBy', { user: job.requested_by })
                    : t('cardmarket.scheduled')}
                </span>
              </span>
              {job.status === 'error' && job.message && (
                <span className={styles.error}>{job.message}</span>
              )}
            </li>
          );
        })}
      </ul>
    );
  }

  return (
    <section className={styles.section} aria-labelledby="cardmarket-jobs">
      <h2 id="cardmarket-jobs" className={styles.sectionTitle}>
        {t('cardmarket.recentTitle')}
      </h2>
      {body}
    </section>
  );
}
