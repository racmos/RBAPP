import { useEffect, useId, useRef, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { enableMfa } from '@/api/endpoints';
import type { MfaSetup } from '@/api/types';
import { FormAlert } from '@/auth/FormAlert';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Modal } from '@/components/ui/Modal';
import { translateError } from '@/i18n';
import { CodeInput } from './CodeInput';
import { useCopy } from './copy';
import { failureOf } from './formFailure';
import { RecoveryCodesView } from './RecoveryCodes';
import { isReauthCancelled } from './reauth/withReauth';
import { useReauth } from './reauth/ReauthProvider';
import styles from './SecurityPage.module.css';

type Props = {
  setup: MfaSetup;
  /** Closed before step 3: nothing is on yet (the pending secret is harmless). */
  onAbandon: () => void;
  /** Done at step 3: 2FA is on and the codes were saved. */
  onFinish: () => void;
};

/**
 * "Turn on two-factor authentication" (F9-j S6), three steps: scan the QR (or type the key),
 * confirm a code (`POST /me/2fa/enable` through `withReauth`), save the recovery codes. At step
 * 3 the dialog cannot be dismissed until the codes are marked as saved.
 */
export function MfaWizard({ setup, onAbandon, onFinish }: Props) {
  const { t, i18n } = useTranslation('account');
  const withReauth = useReauth();
  const copy = useCopy();
  const keyId = useId();
  const heading = useRef<HTMLHeadingElement>(null);
  const form = useRef<HTMLFormElement>(null);
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [code, setCode] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [codes, setCodes] = useState<string[]>([]);
  const [saved, setSaved] = useState(false);
  const moved = useRef(false);

  // Each new step starts at its heading (F9-j S15); the first one through `data-autofocus`.
  useEffect(() => {
    if (moved.current) heading.current?.focus();
    moved.current = true;
  }, [step]);

  const finish = () => {
    setCodes([]);
    onFinish();
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (pending) return;
    const value = code.replace(/\s/g, '');
    setFormError(null);
    if (!value) {
      setError(i18n.t('errors:validation.required'));
      form.current?.querySelector<HTMLElement>('[name="code"]')?.focus();
      return;
    }
    setPending(true);
    try {
      const result = await withReauth(() => enableMfa(value));
      setCodes(result.recovery_codes);
      setCode('');
      setStep(3);
    } catch (failed) {
      if (isReauthCancelled(failed)) return;
      const failure = failureOf(failed, i18n, ['code'] as const, { mfa_invalid: 'code' });
      if (failure.kind === 'fields' && failure.errors.code) {
        setError(failure.errors.code);
        form.current?.querySelector<HTMLElement>('[name="code"]')?.focus();
      } else setFormError(translateError(failed, i18n));
    } finally {
      setPending(false);
    }
  };

  return (
    <Modal
      open
      title={t('mfa.wizardTitle')}
      onClose={step === 3 ? finish : onAbandon}
      dismissible={step !== 3 || saved}
    >
      <div className={styles.form}>
        <p className={styles.step}>{t('mfa.step', { step })}</p>
        {step === 1 && (
          <>
            <h3 ref={heading} className={styles.stepTitle} tabIndex={-1} data-autofocus>
              {t('mfa.scan')}
            </h3>
            <div className={styles.qr}>
              <img
                className={styles.qrImage}
                src={setup.qr}
                alt={t('mfa.qrAlt')}
                width={220}
                height={220}
                aria-describedby={keyId}
              />
              <p id={keyId} className={styles.secret}>
                {setup.secret}
              </p>
              <Button variant="ghost" size="sm" onClick={() => void copy(setup.secret)}>
                {t('mfa.copyKey')}
              </Button>
            </div>
            <div className={styles.actions}>
              <Button onClick={() => setStep(2)}>{t('mfa.next')}</Button>
            </div>
          </>
        )}
        {step === 2 && (
          <form ref={form} className={styles.form} onSubmit={onSubmit} noValidate>
            <h3 ref={heading} className={styles.stepTitle} tabIndex={-1}>
              {t('mfa.enterCode')}
            </h3>
            {formError && <FormAlert message={formError} />}
            <Field label={t('reauth.code')} error={error ?? undefined} required>
              {(control) => (
                <CodeInput
                  {...control}
                  name="code"
                  value={code}
                  onChange={(event) => {
                    setCode(event.target.value);
                    setError(null);
                  }}
                />
              )}
            </Field>
            <div className={styles.actions}>
              <Button
                variant="ghost"
                onClick={() => {
                  setError(null);
                  setFormError(null);
                  setStep(1);
                }}
              >
                {t('mfa.back')}
              </Button>
              <Button type="submit" pending={pending}>
                {pending ? t('mfa.enabling') : t('mfa.enable')}
              </Button>
            </div>
          </form>
        )}
        {step === 3 && (
          <RecoveryCodesView
            codes={codes}
            saved={saved}
            onSavedChange={setSaved}
            onDone={finish}
            headingRef={heading}
          />
        )}
      </div>
    </Modal>
  );
}
