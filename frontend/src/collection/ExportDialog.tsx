import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { exportCollection } from '@/api/endpoints';
import type { CollectionParams, ExportFormat } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { pushToast } from '@/components/ui/toastStore';
import { translateError } from '@/i18n';
import { exportQuery, type ExportScope } from './params';
import styles from './ExportDialog.module.css';

type ExportDialogProps = {
  open: boolean;
  onClose: () => void;
  /** The collection URL params: the `filtered` scope sends their filters. */
  params: CollectionParams;
  offline: boolean;
};

const FORMATS: ExportFormat[] = ['rbapp', 'cardmarket'];
const SCOPES: ExportScope[] = ['all', 'filtered', 'selling'];

/** Save a Blob under `name` through a temporary link (no navigation, no new tab). */
function saveBlob(blob: Blob, name: string): void {
  const href = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = href;
  link.download = name;
  link.hidden = true;
  document.body.append(link);
  try {
    link.click();
  } finally {
    link.remove();
    // Some browsers read the URL after the click returns.
    setTimeout(() => URL.revokeObjectURL(href), 0);
  }
}

/** Download the collection as RBAPP or Cardmarket CSV (F3-i S1). */
export function ExportDialog({ open, onClose, params, offline }: ExportDialogProps) {
  const { t, i18n } = useTranslation('collection');
  const [format, setFormat] = useState<ExportFormat>('rbapp');
  const [scope, setScope] = useState<ExportScope>('all');
  const [pending, setPending] = useState(false);
  const cardmarket = format === 'cardmarket';
  const shownScope = cardmarket ? 'selling' : scope;

  const download = async () => {
    setPending(true);
    try {
      const file = await exportCollection(exportQuery(params, format, scope));
      saveBlob(
        file.blob,
        file.filename ?? (cardmarket ? 'cardmarket.csv' : 'rbapp_collection.csv'),
      );
      pushToast({ kind: 'success', message: t('export.done', { count: file.rowsExported ?? 0 }) });
      onClose();
    } catch (error) {
      pushToast({ kind: 'error', message: translateError(error, i18n) });
    } finally {
      setPending(false);
    }
  };

  const formatLabel = (value: ExportFormat) =>
    value === 'rbapp' ? t('export.formatRbapp') : t('export.formatCardmarket');
  const scopeLabel = (value: ExportScope) =>
    value === 'all'
      ? t('export.scopeAll')
      : value === 'filtered'
        ? t('export.scopeFiltered')
        : t('export.scopeSelling');

  return (
    <Modal open={open} onClose={onClose} title={t('export.title')}>
      <form
        className={styles.form}
        onSubmit={(event) => {
          event.preventDefault();
          void download();
        }}
      >
        <fieldset className={styles.group}>
          <legend className={styles.legend}>{t('export.format')}</legend>
          {FORMATS.map((value) => (
            <label key={value} className={styles.option}>
              <input
                type="radio"
                name="export-format"
                value={value}
                checked={format === value}
                onChange={() => setFormat(value)}
              />
              <span>{formatLabel(value)}</span>
            </label>
          ))}
          {cardmarket && <p className={styles.hint}>{t('export.cardmarketHint')}</p>}
        </fieldset>
        <fieldset className={styles.group}>
          <legend className={styles.legend}>{t('export.scope')}</legend>
          {SCOPES.map((value) => (
            <label key={value} className={styles.option}>
              <input
                type="radio"
                name="export-scope"
                value={value}
                checked={shownScope === value}
                disabled={cardmarket && value !== 'selling'}
                onChange={() => setScope(value)}
              />
              <span>{scopeLabel(value)}</span>
            </label>
          ))}
        </fieldset>
        <div className={styles.actions}>
          <Button variant="ghost" onClick={onClose}>
            {i18n.t('actions.cancel', { ns: 'common' })}
          </Button>
          <Button type="submit" pending={pending} disabled={offline}>
            {t('export.download')}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
