import { useId, type Ref } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Checkbox } from '@/components/ui/Checkbox';
import { Modal } from '@/components/ui/Modal';
import { useCopy } from './copy';
import styles from './SecurityPage.module.css';

export const CODES_FILE = 'rift-manager-recovery-codes.txt';

/** Save the codes as a text file, one per line, through a Blob URL revoked right after. */
export function downloadCodes(codes: readonly string[]): void {
  const href = URL.createObjectURL(new Blob([`${codes.join('\n')}\n`], { type: 'text/plain' }));
  const link = document.createElement('a');
  link.href = href;
  link.download = CODES_FILE;
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

type ViewProps = {
  codes: readonly string[];
  saved: boolean;
  onSavedChange: (saved: boolean) => void;
  onDone: () => void;
  /** The heading takes focus when the view appears (F9-j S15). */
  headingRef?: Ref<HTMLHeadingElement>;
};

/**
 * "Save your recovery codes" (F9-j S6 step 3, S8): the ten codes, copy, download and the
 * "I saved these codes" box that unlocks Done. The codes live only in the caller's state.
 */
export function RecoveryCodesView({ codes, saved, onSavedChange, onDone, headingRef }: ViewProps) {
  const { t } = useTranslation('account');
  const copy = useCopy();
  const headingId = useId();
  return (
    <div className={styles.form}>
      <h3 id={headingId} ref={headingRef} className={styles.stepTitle} tabIndex={-1} data-autofocus>
        {t('mfa.codesTitle')}
      </h3>
      <p className={styles.text}>{t('mfa.codesText')}</p>
      <ol className={styles.codes} aria-labelledby={headingId}>
        {codes.map((code) => (
          <li key={code}>{code}</li>
        ))}
      </ol>
      <div className={styles.row}>
        <Button variant="ghost" onClick={() => void copy(codes.join('\n'))}>
          {t('mfa.copyCodes')}
        </Button>
        <Button variant="ghost" onClick={() => downloadCodes(codes)}>
          {t('mfa.download')}
        </Button>
      </div>
      <Checkbox
        label={t('mfa.saved')}
        checked={saved}
        onChange={(event) => onSavedChange(event.target.checked)}
      />
      <div className={styles.actions}>
        <Button onClick={onDone} disabled={!saved}>
          {t('mfa.done')}
        </Button>
      </div>
    </div>
  );
}

/** New recovery codes (F9-j S8): the same view in its own dialog, locked until saved. */
export function RecoveryCodesDialog({
  codes,
  saved,
  onSavedChange,
  onDone,
}: Omit<ViewProps, 'headingRef'>) {
  const { t } = useTranslation('account');
  return (
    <Modal open title={t('mfa.newCodesModal')} onClose={onDone} dismissible={saved}>
      <RecoveryCodesView
        codes={codes}
        saved={saved}
        onSavedChange={onSavedChange}
        onDone={onDone}
      />
    </Modal>
  );
}
