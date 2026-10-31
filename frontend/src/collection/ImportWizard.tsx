import { useId, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import { ApiError } from '@/api/errors';
import type {
  ImportMode,
  ImportPreview,
  ImportResult,
  ImportRow,
  ImportRowStatus,
} from '@/api/types';
import { useOffline } from '@/auth';
import { CardImage } from '@/components/card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { PageHeader } from '@/components/ui/PageHeader';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { translateError, useDocumentTitle, useEnumLabel } from '@/i18n';
import { up } from '@/lib/breakpoints';
import { formatMoney } from '@/lib/format';
import { useMediaQuery } from '@/lib/useMediaQuery';
import { useImportCommit, useImportPreview } from './queries';
import { StepIndicator } from './StepIndicator';
import styles from './ImportWizard.module.css';

type Step = 'file' | 'review' | 'mode' | 'result';
type Filter = 'all' | ImportRowStatus;

/** The limit of `POST /collection/import/preview` (F3-e), checked here first. */
const MAX_BYTES = 2 * 1024 * 1024;
const TONES = { ok: 'success', warning: 'warning', error: 'danger' } as const;

function readText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(typeof reader.result === 'string' ? reader.result : '');
    reader.onerror = () => reject(reader.error ?? new Error('read failed'));
    reader.readAsText(file);
  });
}

/** One row of the preview, as table cells or as a list item (F3-i S2). */
function useRowText() {
  const { t } = useTranslation('collection');
  const { label } = useEnumLabel();
  const money = (value: number | null) => (value === null ? '—' : formatMoney(value));
  const reasons = (row: ImportRow) =>
    [...new Set(row.reason_codes)].map((code) => t(`import.reason.${code}`) || code).join(' ');
  const card = (row: ImportRow): ReactNode =>
    row.card ? (
      <span className={styles.card}>
        <CardImage card={row.card} size="thumb" decorative className={styles.thumb} />
        <span className={styles.cardText}>
          <span className={styles.cardName}>{row.card.name}</span>
          <span className={styles.muted}>{`${row.set_id} · #${row.card_id}`}</span>
        </span>
      </span>
    ) : (
      <span className={styles.muted}>{`${row.set_id} · #${row.card_id}`}</span>
    );
  return {
    money,
    reasons,
    card,
    status: (row: ImportRow) => (
      <Badge tone={TONES[row.status]}>{t(`import.status.${row.status}`)}</Badge>
    ),
    foil: (row: ImportRow) => (row.foil === null ? '—' : row.foil ? t('foil') : '—'),
    qty: (row: ImportRow) => (row.qty === null ? '—' : String(row.qty)),
    condition: (row: ImportRow) => (row.condition ? label('condition', row.condition) : '—'),
    language: (row: ImportRow) => (row.language ? label('language', row.language) : '—'),
  };
}

function ReviewTable({ rows }: { rows: ImportRow[] }) {
  const { t } = useTranslation('collection');
  const text = useRowText();
  return (
    <div className={styles.scroll}>
      <table className={styles.table} aria-label={t('import.steps.review')}>
        <thead>
          <tr>
            <th scope="col">{t('import.columns.line')}</th>
            <th scope="col">{t('import.columns.status')}</th>
            <th scope="col">{t('import.columns.card')}</th>
            <th scope="col">{t('table.columns.foil')}</th>
            <th scope="col">{t('table.columns.qty')}</th>
            <th scope="col">{t('table.columns.condition')}</th>
            <th scope="col">{t('table.columns.language')}</th>
            <th scope="col">{t('table.columns.purchase')}</th>
            <th scope="col">{t('table.columns.sellPrice')}</th>
            <th scope="col">{t('import.columns.reasons')}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.line} data-status={row.status}>
              <td className={styles.num}>{row.line}</td>
              <td>{text.status(row)}</td>
              <td>{text.card(row)}</td>
              <td>{text.foil(row)}</td>
              <td className={styles.num}>{text.qty(row)}</td>
              <td>{text.condition(row)}</td>
              <td>{text.language(row)}</td>
              <td className={styles.num}>{text.money(row.purchase_price)}</td>
              <td className={styles.num}>{text.money(row.sell_price)}</td>
              <td className={styles.reasons}>{text.reasons(row)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ReviewList({ rows }: { rows: ImportRow[] }) {
  const { t } = useTranslation('collection');
  const text = useRowText();
  return (
    <ul className={styles.list} aria-label={t('import.steps.review')}>
      {rows.map((row) => {
        const details = [
          row.foil ? t('foil') : null,
          row.qty === null ? null : t('qtyBadge', { count: row.qty }),
          row.condition ? text.condition(row) : null,
          row.language ? text.language(row) : null,
          row.purchase_price === null
            ? null
            : `${t('table.columns.purchase')}: ${text.money(row.purchase_price)}`,
          row.sell_price === null
            ? null
            : `${t('table.columns.sellPrice')}: ${text.money(row.sell_price)}`,
        ].filter(Boolean);
        const reasons = text.reasons(row);
        return (
          <li key={row.line} className={styles.item} data-status={row.status}>
            <div className={styles.itemHead}>
              <span className={styles.muted}>{`${t('import.columns.line')} ${row.line}`}</span>
              {text.status(row)}
            </div>
            {text.card(row)}
            {details.length > 0 && <p className={styles.details}>{details.join(' · ')}</p>}
            {reasons && <p className={styles.reasons}>{reasons}</p>}
          </li>
        );
      })}
    </ul>
  );
}

/** `/collection/import`: file, review, mode, result (F3-i S2-S4). */
export function ImportWizard() {
  const { t, i18n } = useTranslation('collection');
  const { t: tCommon } = useTranslation('common');
  useDocumentTitle(t('import.title'));
  const ids = useId();
  const offline = useOffline();
  const desktop = useMediaQuery(up('md'));
  const previewImport = useImportPreview();
  const commitImport = useImportCommit();

  const [step, setStep] = useState<Step>('file');
  const [file, setFile] = useState<File | null>(null);
  const [fileKey, setFileKey] = useState(0);
  const [pasted, setPasted] = useState('');
  const [reading, setReading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [filter, setFilter] = useState<Filter>('all');
  const [mode, setMode] = useState<ImportMode>('add');
  const [confirming, setConfirming] = useState(false);
  const [commitError, setCommitError] = useState<string | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);

  const steps = [
    { key: 'file', label: t('import.steps.file') },
    { key: 'review', label: t('import.steps.review') },
    { key: 'mode', label: t('import.steps.mode') },
    { key: 'result', label: t('import.steps.result') },
  ] as const;

  const review = async () => {
    setError(null);
    let text = pasted;
    if (file) {
      if (file.size > MAX_BYTES) return setError(t('import.errors.tooBig'));
      setReading(true);
      try {
        text = await readText(file);
      } catch (cause) {
        return setError(translateError(cause, i18n));
      } finally {
        setReading(false);
      }
    }
    if (text.trim() === '') return setError(t('import.errors.empty'));
    if (new Blob([text]).size > MAX_BYTES) return setError(t('import.errors.tooBig'));
    previewImport.mutate(text, {
      onSuccess: (data) => {
        setPreview(data);
        setFilter('all');
        setMode('add');
        setCommitError(null);
        setStep('review');
      },
      onError: (cause) => setError(translateError(cause, i18n)),
    });
  };

  const commit = () => {
    setConfirming(false);
    if (!preview) return;
    setCommitError(null);
    commitImport.mutate(
      { previewId: preview.preview_id, mode },
      {
        onSuccess: (data) => {
          setResult(data);
          setPreview(null);
          setStep('result');
        },
        onError: (cause) => {
          if (cause instanceof ApiError && cause.code === 'import_expired') {
            setPreview(null);
            setError(translateError(cause, i18n));
            setStep('file');
          } else {
            setCommitError(translateError(cause, i18n));
          }
        },
      },
    );
  };

  const again = () => {
    setFile(null);
    setFileKey((key) => key + 1);
    setPasted('');
    setError(null);
    setResult(null);
    setStep('file');
  };

  const summary = preview?.summary;
  const rows = preview
    ? preview.rows.filter((row) => filter === 'all' || row.status === filter)
    : [];

  let body: ReactNode = null;
  if (step === 'file') {
    body = (
      <form
        className={styles.form}
        onSubmit={(event) => {
          event.preventDefault();
          void review();
        }}
      >
        <p className={styles.muted}>{t('import.formatHint')}</p>
        <label className={styles.field}>
          <span className={styles.label}>{t('import.fileLabel')}</span>
          <input
            key={fileKey}
            type="file"
            accept=".csv"
            disabled={offline}
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null);
              setError(null);
            }}
          />
        </label>
        <label className={styles.field}>
          <span className={styles.label}>{t('import.pasteLabel')}</span>
          <textarea
            className={styles.textarea}
            rows={8}
            spellCheck={false}
            value={pasted}
            disabled={offline}
            onChange={(event) => {
              setPasted(event.target.value);
              setError(null);
            }}
          />
        </label>
        {error && (
          <p className={styles.error} role="alert">
            {error}
          </p>
        )}
        <div className={styles.actions}>
          <Button type="submit" disabled={offline} pending={reading || previewImport.isPending}>
            {t('import.preview')}
          </Button>
        </div>
      </form>
    );
  } else if (step === 'review' && preview && summary) {
    body = (
      <div className={styles.review}>
        <div className={styles.side}>
          <p className={styles.summary}>{t('import.summary', summary)}</p>
          {summary.error > 0 && <p className={styles.muted}>{t('import.skipNote')}</p>}
          <SegmentedControl
            label={t('import.columns.status')}
            options={[
              { value: 'all', label: t('import.statusFilter.all') },
              { value: 'ok', label: t('import.status.ok') },
              { value: 'warning', label: t('import.status.warning') },
              { value: 'error', label: t('import.status.error') },
            ]}
            value={filter}
            onChange={setFilter}
          />
        </div>
        <div className={styles.rows}>
          {desktop ? <ReviewTable rows={rows} /> : <ReviewList rows={rows} />}
        </div>
        <div className={styles.actions}>
          <Button variant="ghost" onClick={() => setStep('file')}>
            {t('import.back')}
          </Button>
          <Button
            disabled={offline || summary.ok + summary.warning === 0}
            onClick={() => setStep('mode')}
          >
            {t('import.next')}
          </Button>
        </div>
      </div>
    );
  } else if (step === 'mode' && preview && summary) {
    body = (
      <form
        className={styles.form}
        onSubmit={(event) => {
          event.preventDefault();
          if (mode === 'replace') setConfirming(true);
          else commit();
        }}
      >
        <fieldset className={styles.modes}>
          <legend className={styles.label}>{t('import.steps.mode')}</legend>
          {(['add', 'replace'] as const).map((value) => (
            <div key={value} className={styles.option}>
              <input
                id={`${ids}-${value}`}
                type="radio"
                name={`${ids}-mode`}
                value={value}
                checked={mode === value}
                aria-describedby={`${ids}-${value}-hint`}
                onChange={() => setMode(value)}
              />
              <div className={styles.optionText}>
                <label htmlFor={`${ids}-${value}`} className={styles.optionLabel}>
                  {value === 'add' ? t('import.mode.add') : t('import.mode.replace')}
                </label>
                <p
                  id={`${ids}-${value}-hint`}
                  className={value === 'add' ? styles.muted : styles.warning}
                >
                  {value === 'add' ? t('import.mode.addHint') : t('import.mode.replaceHint')}
                </p>
              </div>
            </div>
          ))}
        </fieldset>
        {commitError && (
          <p className={styles.error} role="alert">
            {commitError}
          </p>
        )}
        <div className={styles.actions}>
          <Button variant="ghost" onClick={() => setStep('review')}>
            {t('import.back')}
          </Button>
          <Button type="submit" disabled={offline} pending={commitImport.isPending}>
            {t('import.commit')}
          </Button>
        </div>
        <ConfirmDialog
          open={confirming}
          title={t('import.mode.replace')}
          message={t('import.confirmReplace', { count: summary.printings })}
          confirmLabel={t('import.commit')}
          cancelLabel={tCommon('actions.cancel')}
          danger
          onConfirm={commit}
          onCancel={() => setConfirming(false)}
        />
      </form>
    );
  } else if (step === 'result' && result) {
    body = (
      <div className={styles.form}>
        <p className={styles.summary} role="status">
          {t('import.result', result)}
        </p>
        <div className={styles.actions}>
          <Button variant="ghost" disabled={offline} onClick={again}>
            {t('import.again')}
          </Button>
          <Link className={styles.link} to="/collection">
            {t('import.goCollection')}
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <PageHeader title={t('import.title')} />
      <StepIndicator label={t('import.title')} steps={steps} current={step} />
      {offline && <p className={styles.offline}>{tCommon('offline.editDisabled')}</p>}
      {body}
    </div>
  );
}
