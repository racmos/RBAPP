import { useId, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import type { CardmarketLoadDetail } from '@/api/endpoints';
import { ErrorState } from '@/components/ui/ErrorState';
import { Skeleton } from '@/components/ui/Skeleton';
import { formatMoney, formatNumber } from '@/lib/format';
import { resultRows, secondsBetween } from './format';
import {
  DayStatusBadge,
  JobStatusBadge,
  formatStamp,
  useDurationText,
  useFileTypeLabel,
} from './parts';
import { useCardmarketDay } from './queries';
import styles from './CardmarketPage.module.css';

/** One load day (CM-a): every file run, the new products, the job and its result. */
export function DayDetail({ date }: { date: string }) {
  const { t } = useTranslation('admin');
  const { t: common } = useTranslation('common');
  const query = useCardmarketDay(date);

  if (query.isPending) return <Skeleton label={t('cardmarket.details')} lines={6} />;
  if (query.isError) {
    return <ErrorState message={common('errorState.title')} onRetry={() => void query.refetch()} />;
  }
  const day = query.data;
  return (
    <div className={styles.detail}>
      <Files day={day} />
      <NewProductsList day={day} />
      <JobBlock day={day} />
    </div>
  );
}

function Files({ day }: { day: CardmarketLoadDetail }) {
  const { t } = useTranslation('admin');
  const typeLabel = useFileTypeLabel();
  const id = useId();
  return (
    <section>
      <h3 id={id} className={styles.detailTitle}>
        {t('cardmarket.detail.files')}
      </h3>
      <ul aria-labelledby={id} className={styles.detailList}>
        {day.files.map((file, index) => (
          <li key={`${file.type}-${index}`} className={styles.detailItem}>
            <span className={styles.detailHead}>
              <strong>{typeLabel(file.type)}</strong>
              <DayStatusBadge status={file.status} />
              <span>
                {t('cardmarket.fileRows', {
                  rows: file.rows === null ? '—' : formatNumber(file.rows),
                })}
              </span>
              <span className={styles.muted}>{formatStamp(file.loaded_at)}</span>
            </span>
            {file.message && <span className={styles.muted}>{file.message}</span>}
          </li>
        ))}
      </ul>
    </section>
  );
}

function NewProductsList({ day }: { day: CardmarketLoadDetail }) {
  const { t } = useTranslation('admin');
  const id = useId();
  const list = Array.isArray(day.new_products_list) ? day.new_products_list : [];
  const rest = day.truncated ? Math.max((day.new_products ?? 0) - list.length, 0) : 0;
  return (
    <section>
      <h3 id={id} className={styles.detailTitle}>
        {t('cardmarket.detail.newProducts')}
      </h3>
      {list.length === 0 ? (
        <p className={styles.muted}>{t('cardmarket.detail.noNewProducts')}</p>
      ) : (
        <ul aria-labelledby={id} className={styles.detailList}>
          {list.map((product) => (
            <li key={product.id_product} className={styles.detailItem}>
              <span>{product.name}</span>
              <span className={styles.muted}>
                {[
                  product.category,
                  product.type,
                  product.low_price === null ? null : formatMoney(product.low_price),
                ]
                  .filter(Boolean)
                  .join(' · ')}
              </span>
            </li>
          ))}
        </ul>
      )}
      {rest > 0 && <p className={styles.muted}>{t('cardmarket.detail.more', { count: rest })}</p>}
    </section>
  );
}

function JobBlock({ day }: { day: CardmarketLoadDetail }) {
  const { t } = useTranslation('admin');
  const duration = useDurationText();
  const job = day.job;
  if (!job) {
    return (
      <section>
        <h3 className={styles.detailTitle}>{t('cardmarket.detail.job')}</h3>
        <p className={styles.muted}>{t('cardmarket.detail.noJob')}</p>
      </section>
    );
  }
  const rows = resultRows(job.result);
  const seconds = secondsBetween(job.started_at, job.finished_at) ?? day.duration_seconds;
  return (
    <section>
      <h3 className={styles.detailTitle}>{t('cardmarket.detail.job')}</h3>
      <dl className={styles.pairs}>
        <Pair label={t('cardmarket.jobFields.status')}>
          <JobStatusBadge status={job.status} /> #{job.id}
        </Pair>
        <Pair label={t('cardmarket.jobFields.queued')}>{formatStamp(job.queued_at)}</Pair>
        <Pair label={t('cardmarket.jobFields.started')}>{formatStamp(job.started_at)}</Pair>
        <Pair label={t('cardmarket.jobFields.finished')}>{formatStamp(job.finished_at)}</Pair>
        <Pair label={t('cardmarket.columns.duration')}>{duration(seconds)}</Pair>
        {job.message && <Pair label={t('cardmarket.jobFields.message')}>{job.message}</Pair>}
      </dl>
      {rows.length > 0 && (
        <>
          <h4 className={styles.detailSubtitle}>{t('cardmarket.detail.result')}</h4>
          <dl className={styles.pairs}>
            {rows.map((row) => (
              <Pair key={row.key} label={t(row.key)}>
                {typeof row.value === 'number' ? formatNumber(row.value) : row.value}
              </Pair>
            ))}
          </dl>
        </>
      )}
      {job.result !== null && job.result !== undefined && (
        <details className={styles.raw}>
          <summary>{t('cardmarket.detail.rawResult')}</summary>
          <pre>{JSON.stringify(job.result, null, 2)}</pre>
        </details>
      )}
    </section>
  );
}

function Pair({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className={styles.pair}>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}
