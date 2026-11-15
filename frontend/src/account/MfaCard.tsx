import { useQueryClient } from '@tanstack/react-query';
import { useRef, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { disableMfa, regenerateRecoveryCodes, setupMfa } from '@/api/endpoints';
import type { MeData, MfaSetup } from '@/api/types';
import { FormAlert } from '@/auth/FormAlert';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { SettingsCard } from '@/components/ui/SettingsCard';
import { pushToast } from '@/components/ui/toastStore';
import { translateError } from '@/i18n';
import { failureOf } from './formFailure';
import { MfaWizard } from './MfaWizard';
import { RecoveryCodesDialog } from './RecoveryCodes';
import { isReauthCancelled } from './reauth/withReauth';
import { useReauth } from './reauth/ReauthProvider';
import styles from './SecurityPage.module.css';

type Mfa = MeData['security']['mfa'];

/** At or below this many codes left the count is a warning (F9-j S5). */
const LOW_CODES = 3;

/**
 * "Turn off two-factor authentication?" (F9-j S7): a TOTP or a recovery code, sent through
 * `withReauth`; a wrong code stays on the field.
 */
function DisableDialog({ onCancel, onDone }: { onCancel: () => void; onDone: () => void }) {
  const { t, i18n } = useTranslation('account');
  const { t: tCommon } = useTranslation('common');
  const withReauth = useReauth();
  const form = useRef<HTMLFormElement>(null);
  const [code, setCode] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const focusCode = () => form.current?.querySelector<HTMLElement>('[name="code"]')?.focus();

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (pending) return;
    const value = code.trim();
    setFormError(null);
    if (!value) {
      setError(i18n.t('errors:validation.required'));
      return focusCode();
    }
    setPending(true);
    try {
      await withReauth(() => disableMfa(value));
      onDone();
    } catch (failed) {
      if (isReauthCancelled(failed)) return;
      const failure = failureOf(failed, i18n, ['code'] as const, { mfa_invalid: 'code' });
      if (failure.kind === 'fields' && failure.errors.code) {
        setError(failure.errors.code);
        focusCode();
      } else setFormError(translateError(failed, i18n));
    } finally {
      setPending(false);
    }
  };

  return (
    <Modal open title={t('mfa.disableTitle')} onClose={onCancel}>
      <form ref={form} className={styles.form} onSubmit={onSubmit} noValidate>
        <p className={styles.text}>{t('mfa.disableText')}</p>
        {formError && <FormAlert message={formError} />}
        <Field label={t('mfa.disableCode')} error={error ?? undefined} required>
          {(control) => (
            <Input
              {...control}
              name="code"
              value={code}
              onChange={(event) => {
                setCode(event.target.value);
                setError(null);
              }}
              autoComplete="one-time-code"
              autoCapitalize="none"
              spellCheck={false}
              className={styles.code}
              data-autofocus
            />
          )}
        </Field>
        <div className={styles.actions}>
          <Button variant="ghost" onClick={onCancel}>
            {tCommon('actions.cancel')}
          </Button>
          <Button type="submit" variant="danger" pending={pending}>
            {t('mfa.turnOff')}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

/**
 * The two-factor card (F9-j S5-S8): its state from `GET /me`, the set-up wizard, turning it off
 * and new recovery codes. Codes and the setup secret live in this component's state only and
 * are dropped when their dialog closes.
 */
export function MfaCard({ mfa, offline }: { mfa: Mfa | null; offline: boolean }) {
  const { t, i18n } = useTranslation('account');
  const { t: tCommon } = useTranslation('common');
  const queryClient = useQueryClient();
  const withReauth = useReauth();
  const [starting, setStarting] = useState(false);
  const [setup, setSetup] = useState<MfaSetup | null>(null);
  const [disabling, setDisabling] = useState(false);
  const [confirmCodes, setConfirmCodes] = useState(false);
  const [creating, setCreating] = useState(false);
  const [codes, setCodes] = useState<string[] | null>(null);
  const [codesSaved, setCodesSaved] = useState(false);

  // 2FA on/off and new codes change the summary and end the other devices' sessions.
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ['me'] });
  const fail = (error: unknown) => {
    if (!isReauthCancelled(error)) {
      pushToast({ kind: 'error', message: translateError(error, i18n) });
    }
  };

  const start = async () => {
    setStarting(true);
    try {
      setSetup(await withReauth(setupMfa));
    } catch (error) {
      fail(error);
    } finally {
      setStarting(false);
    }
  };

  const createCodes = async () => {
    setConfirmCodes(false);
    setCreating(true);
    try {
      const result = await withReauth(regenerateRecoveryCodes);
      setCodesSaved(false);
      setCodes(result.recovery_codes);
    } catch (error) {
      fail(error);
    } finally {
      setCreating(false);
    }
  };

  let body;
  if (!mfa) body = null;
  else if (!mfa.available) body = <p className={styles.text}>{t('mfa.unavailable')}</p>;
  else if (!mfa.enabled) {
    body = (
      <div className={styles.row}>
        <Badge>{t('mfa.off')}</Badge>
        <Button onClick={() => void start()} pending={starting} disabled={offline}>
          {t('mfa.turnOn')}
        </Button>
      </div>
    );
  } else {
    const low = mfa.recovery_codes_left <= LOW_CODES;
    body = (
      <>
        <div className={styles.row}>
          <Badge tone="success">{t('mfa.on')}</Badge>
          <span className={low ? styles.low : styles.hint}>
            {t('mfa.codesLeft', { count: mfa.recovery_codes_left })}
          </span>
        </div>
        <div className={styles.actions}>
          <Button
            variant="ghost"
            onClick={() => setConfirmCodes(true)}
            pending={creating}
            disabled={offline}
          >
            {t('mfa.newCodes')}
          </Button>
          <Button variant="danger" onClick={() => setDisabling(true)} disabled={offline}>
            {t('mfa.turnOff')}
          </Button>
        </div>
      </>
    );
  }

  return (
    <SettingsCard title={t('mfa.title')} description={t('mfa.hint')}>
      <div className={styles.form}>{body}</div>
      {setup && (
        <MfaWizard
          setup={setup}
          onAbandon={() => setSetup(null)}
          onFinish={() => {
            setSetup(null);
            pushToast({ kind: 'success', message: t('mfa.enabled') });
            refresh();
          }}
        />
      )}
      {disabling && (
        <DisableDialog
          onCancel={() => setDisabling(false)}
          onDone={() => {
            setDisabling(false);
            pushToast({ kind: 'success', message: t('mfa.disabled') });
            refresh();
          }}
        />
      )}
      <ConfirmDialog
        open={confirmCodes}
        title={t('mfa.newCodesTitle')}
        message={t('mfa.newCodesText')}
        confirmLabel={t('mfa.newCodesConfirm')}
        cancelLabel={tCommon('actions.cancel')}
        onConfirm={() => void createCodes()}
        onCancel={() => setConfirmCodes(false)}
      />
      {codes && (
        <RecoveryCodesDialog
          codes={codes}
          saved={codesSaved}
          onSavedChange={setCodesSaved}
          onDone={() => {
            setCodes(null);
            refresh();
          }}
        />
      )}
    </SettingsCard>
  );
}
