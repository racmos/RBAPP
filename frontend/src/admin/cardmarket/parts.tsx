import { useTranslation } from 'react-i18next';
import type { CardmarketFile } from '@/api/endpoints';
import { Badge } from '@/components/ui/Badge';
import { formatDateTime, formatNumber } from '@/lib/format';
import { asUtc, durationLabel } from './format';
import styles from './CardmarketPage.module.css';

type Tone = 'neutral' | 'accent' | 'success' | 'warning' | 'danger';

const DAY_STATUS = {
  success: { key: 'cardmarket.dayStatus.success', tone: 'success' },
  partial: { key: 'cardmarket.dayStatus.partial', tone: 'warning' },
  error: { key: 'cardmarket.dayStatus.error', tone: 'danger' },
  skipped: { key: 'cardmarket.dayStatus.skipped', tone: 'neutral' },
} as const satisfies Record<string, { key: string; tone: Tone }>;

const JOB_STATUS = {
  queued: { key: 'job.status.queued', tone: 'accent' },
  running: { key: 'job.status.running', tone: 'accent' },
  success: { key: 'job.status.success', tone: 'success' },
  error: { key: 'job.status.error', tone: 'danger' },
} as const satisfies Record<string, { key: string; tone: Tone }>;

const FILE_TYPE = {
  price_guide: 'cardmarket.fileType.price_guide',
  singles: 'cardmarket.fileType.singles',
  nonsingles: 'cardmarket.fileType.nonsingles',
} as const;

const known = <T extends object>(table: T, value: string): value is Extract<keyof T, string> =>
  Object.hasOwn(table, value);

/** A UTC timestamp of the API in the reader's time, or a dash. */
export const formatStamp = (value: string | null | undefined): string =>
  value ? formatDateTime(asUtc(value)) : '—';

/** Status of a load day or of one of its files (an unknown value shows as sent). */
export function DayStatusBadge({ status }: { status: string }) {
  const { t } = useTranslation('admin');
  if (!known(DAY_STATUS, status)) return <Badge>{status}</Badge>;
  return <Badge tone={DAY_STATUS[status].tone}>{t(DAY_STATUS[status].key)}</Badge>;
}

export function JobStatusBadge({ status }: { status: string }) {
  const { t } = useTranslation('admin');
  if (!known(JOB_STATUS, status)) return <Badge>{status}</Badge>;
  return <Badge tone={JOB_STATUS[status].tone}>{t(JOB_STATUS[status].key)}</Badge>;
}

export function useFileTypeLabel() {
  const { t } = useTranslation('admin');
  return (type: string) => (known(FILE_TYPE, type) ? t(FILE_TYPE[type]) : type);
}

/** "10 s", "2 min 5 s"; a dash without a duration. */
export function useDurationText() {
  const { t } = useTranslation('admin');
  return (seconds: number | null | undefined) => {
    const label = durationLabel(seconds);
    if (!label) return '—';
    switch (label.key) {
      case 'cardmarket.duration.seconds':
        return t(label.key, label.values);
      case 'cardmarket.duration.minutes':
        return t(label.key, label.values);
      case 'cardmarket.duration.hours':
        return t(label.key, label.values);
    }
  };
}

/** The three files of a day as compact chips: type, rows and status. */
export function FileChips({ files }: { files: CardmarketFile[] }) {
  const typeLabel = useFileTypeLabel();
  return (
    <span className={styles.chips}>
      {files.map((file) => (
        <span key={file.type} className={styles.chip} data-status={file.status}>
          <span className={styles.chipType}>{typeLabel(file.type)}</span>
          <span>{file.rows === null ? '—' : formatNumber(file.rows)}</span>
          <DayStatusBadge status={file.status} />
        </span>
      ))}
    </span>
  );
}

/** New products of a day: highlighted when there are any, a dash when unknown. */
export function NewProducts({ value }: { value: number | null }) {
  if (value === null) return <>—</>;
  if (value > 0) {
    return (
      <strong className={styles.highlight} data-highlight="">
        {formatNumber(value)}
      </strong>
    );
  }
  return <span>{formatNumber(value)}</span>;
}
