import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import { ApiError } from '@/api/errors';
import {
  getAdminJob,
  getAdminOverview,
  listAdminJobs,
  listAdminSets,
  startRiotSync,
  type AdminJob,
} from '@/api/endpoints';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Checkbox } from '@/components/ui/Checkbox';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Modal } from '@/components/ui/Modal';
import { PageHeader } from '@/components/ui/PageHeader';
import { Skeleton } from '@/components/ui/Skeleton';
import { useDocumentTitle, translateError } from '@/i18n';
import { useOnline } from '@/lib/useOnline';
import { sortSetsNewestFirst } from '@/lib/sets';
import styles from './RiotPage.module.css';

type RiotSet = {
  set_id: string;
  inserted: number;
  applied: number;
  proposed: number;
  unchanged: number;
};
type WindowKey = 'pre_release' | 'post_release' | 'monthly' | 'none';
type JobStatusKey = 'queued' | 'running' | 'success' | 'error';

/** One riot_sync job with live refresh while it runs (F13-f S9). */
export function JobStatus({ jobId, onDone }: { jobId: number; onDone?: () => void }) {
  const { t } = useTranslation('admin');
  const { t: common } = useTranslation('common');
  const query = useQuery({
    queryKey: ['admin', 'jobs', jobId],
    queryFn: ({ signal }) => getAdminJob(jobId, signal),
    refetchInterval: (current) => {
      const status = current.state.data?.status;
      if (status === 'queued' || status === 'running') return 3000;
      if (status && onDone) onDone();
      return false;
    },
  });

  if (query.isPending) return <Skeleton label={t('riot.title')} />;
  if (query.isError) {
    return <ErrorState message={common('errorState.title')} onRetry={() => void query.refetch()} />;
  }
  const job = query.data;
  const sets: RiotSet[] = Array.isArray((job as { result?: { sets?: unknown } }).result?.sets)
    ? (job as unknown as { result: { sets: RiotSet[] } }).result.sets
    : [];
  return (
    <div>
      <p>
        <Badge>{t(`job.status.${job.status as JobStatusKey}` as 'job.status.queued')}</Badge> #
        {job.id}
      </p>
      <ul className={styles.list}>
        {sets.map((set) => (
          <li key={set.set_id}>
            {t('riot.summary', {
              set: set.set_id,
              inserted: set.inserted,
              applied: set.applied,
              proposed: set.proposed,
              unchanged: set.unchanged,
            })}{' '}
            {set.proposed > 0 && (
              <Link to={`/admin/riot/changes?set=${set.set_id}`}>{t('riot.reviewChanges')}</Link>
            )}
          </li>
        ))}
      </ul>
      {job.status === 'error' && job.message && <p role="alert">{job.message}</p>}
    </div>
  );
}

/** Riot sync panel (F13-f S9): active sets, manual sync, recent runs. */
export function RiotPage() {
  const { t } = useTranslation('admin');
  useDocumentTitle(t('riot.title'));

  return (
    <>
      <PageHeader title={t('riot.title')} subtitle={t('riot.subtitle')} />
      <ActiveSets />
      <SyncNow />
      <RecentRuns />
    </>
  );
}

function ActiveSets() {
  const { t } = useTranslation('admin');
  const { t: common } = useTranslation('common');
  const query = useQuery({
    queryKey: ['admin', 'overview'],
    queryFn: ({ signal }) => getAdminOverview(signal),
  });
  if (query.isPending) return <Skeleton label={t('riot.activeTitle')} />;
  if (query.isError || !query.data) {
    return <ErrorState message={common('errorState.title')} onRetry={() => void query.refetch()} />;
  }
  const active = query.data.riot.active_sets;
  return (
    <section className={styles.section} aria-labelledby="riot-active">
      <h2 id="riot-active" className={styles.sectionTitle}>
        {t('riot.activeTitle')}
      </h2>
      {active.length === 0 ? (
        <EmptyState title={t('riot.title')} body={t('riot.noActive')} />
      ) : (
        <ul className={styles.list}>
          {active.map((set) => (
            <li key={set.id} className={styles.row}>
              <strong>{set.id}</strong>
              <Badge>{t(`window.${set.window as WindowKey}` as 'window.monthly')}</Badge>
              <span>{set.next_run_at}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function SyncNow() {
  const { t, i18n } = useTranslation('admin');
  const { t: common } = useTranslation('common');
  const offline = !useOnline();
  const queryClient = useQueryClient();
  const setsQuery = useQuery({
    queryKey: ['admin', 'sets'],
    queryFn: ({ signal }) => listAdminSets(signal),
  });
  const [selected, setSelected] = useState<string[]>([]);
  const [jobId, setJobId] = useState<number | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  return (
    <section className={styles.section} aria-labelledby="riot-sync-now">
      <h2 id="riot-sync-now" className={styles.sectionTitle}>
        {t('riot.syncNow')}
      </h2>
      <p className={styles.hint}>{t('riot.allSetsHint')}</p>
      <fieldset className={styles.checks}>
        <legend className="sr-only">{t('riot.pickSets')}</legend>
        {setsQuery.isPending && <Skeleton label={t('riot.pickSets')} />}
        {sortSetsNewestFirst(setsQuery.data ?? [], (set) => set.release_date).map((set) => (
          <Checkbox
            key={set.id}
            label={set.id}
            checked={selected.includes(set.id)}
            disabled={offline}
            onChange={(event) =>
              setSelected(
                event.target.checked
                  ? [...selected, set.id]
                  : selected.filter((id) => id !== set.id),
              )
            }
          />
        ))}
      </fieldset>
      {formError && (
        <p role="alert" className={styles.formError}>
          {formError}
        </p>
      )}
      <Button
        disabled={offline}
        title={offline ? common('offline.editDisabled') : undefined}
        onClick={() => {
          setFormError(null);
          startRiotSync(selected)
            .then((job) => {
              setJobId(job.job_id);
              void queryClient.invalidateQueries({ queryKey: ['admin', 'jobs'] });
            })
            .catch((error: unknown) => {
              setFormError(error instanceof ApiError ? translateError(error, i18n) : String(error));
            });
        }}
      >
        {t('riot.syncNow')}
      </Button>
      {jobId !== null && <JobStatus jobId={jobId} />}
    </section>
  );
}

function RecentRuns() {
  const { t } = useTranslation('admin');
  const { t: common } = useTranslation('common');
  const query = useQuery({
    queryKey: ['admin', 'jobs', { kind: 'riot_sync' }],
    queryFn: ({ signal }) => listAdminJobs({ kind: 'riot_sync', limit: 10 }, signal),
  });
  const [openId, setOpenId] = useState<number | null>(null);
  if (query.isPending) return <Skeleton label={t('riot.recentTitle')} />;
  if (query.isError || !query.data) {
    return <ErrorState message={common('errorState.title')} onRetry={() => void query.refetch()} />;
  }
  return (
    <section className={styles.section} aria-labelledby="riot-recent">
      <h2 id="riot-recent" className={styles.sectionTitle}>
        {t('riot.recentTitle')}
      </h2>
      <ul className={styles.list}>
        {query.data.items.map((job) => (
          <RecentRunRow key={job.id} job={job} onOpen={() => setOpenId(job.id)} />
        ))}
      </ul>
      <Modal open={openId !== null} title={t('riot.recentTitle')} onClose={() => setOpenId(null)}>
        {openId !== null && <JobStatus jobId={openId} />}
      </Modal>
    </section>
  );
}

/** One recent run: detail is fetched once and shared with the modal (same query key). */
function RecentRunRow({ job, onOpen }: { job: AdminJob; onOpen: () => void }) {
  const { t } = useTranslation('admin');
  const detail = useQuery({
    queryKey: ['admin', 'jobs', job.id],
    queryFn: ({ signal }) => getAdminJob(job.id, signal),
  });
  const trigger =
    detail.data?.params &&
    typeof detail.data.params === 'object' &&
    (detail.data.params as { trigger?: unknown }).trigger === 'schedule'
      ? 'schedule'
      : 'manual';
  const sets: RiotSet[] = Array.isArray(
    (detail.data as { result?: { sets?: unknown } } | undefined)?.result?.sets,
  )
    ? (detail.data as unknown as { result: { sets: RiotSet[] } }).result.sets
    : [];
  const inserted = sets.reduce((sum, set) => sum + (set.inserted ?? 0), 0);
  const proposed = sets.reduce((sum, set) => sum + (set.proposed ?? 0), 0);
  return (
    <li>
      <button type="button" className={styles.row} onClick={onOpen}>
        <span>{job.finished_at ?? job.requested_at}</span>
        <Badge>{t(`job.status.${job.status as JobStatusKey}` as 'job.status.queued')}</Badge>
        <span>
          {trigger === 'schedule' ? t('riot.trigger.schedule') : t('riot.trigger.manual')}
        </span>
        <span>{t('riot.recentSummary', { sets: sets.length, inserted, proposed })}</span>
      </button>
    </li>
  );
}
