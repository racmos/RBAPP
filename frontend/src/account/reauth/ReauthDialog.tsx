import { useRef, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { reauth } from '@/api/endpoints';
import { FormAlert } from '@/auth/FormAlert';
import { useFormFocus } from '@/auth/formHelpers';
import { useRetryCountdown } from '@/auth/useRetryCountdown';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { announce } from '@/components/ui/LiveAnnouncer';
import { Modal } from '@/components/ui/Modal';
import { PasswordInput } from '@/components/ui/PasswordInput';
import { CodeInput } from '@/account/CodeInput';
import { failureOf } from '@/account/formFailure';
import styles from '@/account/SecurityPage.module.css';
import type { ReauthMethod } from './withReauth';

type Props = {
  methods: ReauthMethod[];
  /** `POST /me/reauth` succeeded: the caller runs its action again. */
  onDone: () => void;
  onCancel: () => void;
};

const FIELDS = ['password', 'code'] as const;

/**
 * "Confirm it's you" (F9-j S3): the password, or a code from the authenticator app when the
 * account has 2FA, with a link between the two (password first). Wrong answers stay on the
 * field; too many attempts show the countdown.
 */
export function ReauthDialog({ methods, onDone, onCancel }: Props) {
  const { t, i18n } = useTranslation('account');
  const { t: tAuth } = useTranslation('auth');
  const form = useRef<HTMLFormElement>(null);
  const focus = useFormFocus(form);
  const [method, setMethod] = useState<ReauthMethod>(methods[0] ?? 'password');
  const [value, setValue] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const countdown = useRetryCountdown({ onEnd: () => announce(tAuth('retry.ready')) });
  const other = methods.find((candidate) => candidate !== method);

  const switchTo = (next: ReauthMethod) => {
    setMethod(next);
    setValue('');
    setError(null);
    setFormError(null);
    focus.request(next);
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (pending || countdown.active) return;
    const answer = method === 'totp' ? value.replace(/\s/g, '') : value;
    setFormError(null);
    if (!answer) {
      setError(i18n.t('errors:validation.required'));
      return focus.request(method);
    }
    setPending(true);
    try {
      await reauth(method === 'totp' ? { code: answer } : { password: answer });
      onDone();
    } catch (failed) {
      const failure = failureOf(failed, i18n, FIELDS, {
        current_password_incorrect: 'password',
        mfa_invalid: 'code',
      });
      if (failure.kind === 'retry') {
        countdown.start(failure.seconds);
        announce(tAuth('retry.countdown', { count: failure.seconds }));
      } else if (failure.kind === 'fields') {
        setError(failure.errors.password ?? failure.errors.code ?? null);
        focus.request(method);
      } else setFormError(failure.message);
    } finally {
      setPending(false);
    }
  };

  const field = method === 'totp' ? 'code' : 'password';
  return (
    <Modal open title={t('reauth.title')} onClose={onCancel}>
      <form ref={form} className={styles.form} onSubmit={onSubmit} noValidate>
        <p className={styles.text}>{t('reauth.text')}</p>
        {formError && <FormAlert message={formError} />}
        {countdown.active && (
          <p className={styles.notice}>
            {tAuth('retry.countdown', { count: countdown.remaining })}
          </p>
        )}
        <Field label={t(`reauth.${field}`)} error={error ?? undefined} required>
          {(control) =>
            method === 'totp' ? (
              <CodeInput
                {...control}
                name="code"
                value={value}
                onChange={(event) => {
                  setValue(event.target.value);
                  setError(null);
                }}
                data-autofocus
              />
            ) : (
              <PasswordInput
                {...control}
                name="password"
                value={value}
                onChange={(event) => {
                  setValue(event.target.value);
                  setError(null);
                }}
                autoComplete="current-password"
                data-autofocus
              />
            )
          }
        </Field>
        {other && (
          <button type="button" className={styles.linkButton} onClick={() => switchTo(other)}>
            {t(other === 'totp' ? 'reauth.useCode' : 'reauth.usePassword')}
          </button>
        )}
        <div className={styles.actions}>
          <Button variant="ghost" onClick={onCancel}>
            {t('reauth.cancel')}
          </Button>
          <Button type="submit" pending={pending} disabled={countdown.active}>
            {pending ? t('reauth.confirming') : t('reauth.confirm')}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
