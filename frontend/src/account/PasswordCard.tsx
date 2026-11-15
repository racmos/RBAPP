import { useQueryClient } from '@tanstack/react-query';
import { useRef, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { patchAccount } from '@/api/endpoints';
import type { ErrorDetail } from '@/api/types';
import { FormAlert } from '@/auth/FormAlert';
import { fieldErrorsFromDetails, useFormFocus, type FieldErrors } from '@/auth/formHelpers';
import { PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH } from '@/auth/registerChecks';
import { useRetryCountdown } from '@/auth/useRetryCountdown';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { announce } from '@/components/ui/LiveAnnouncer';
import { PasswordInput } from '@/components/ui/PasswordInput';
import { SettingsCard } from '@/components/ui/SettingsCard';
import { pushToast } from '@/components/ui/toastStore';
import { failureOf, problem } from './formFailure';
import { applyUserChange } from './queries';
import { isReauthCancelled } from './reauth/withReauth';
import { useReauth } from './reauth/ReauthProvider';
import styles from './SecurityPage.module.css';

const FIELDS = ['current_password', 'password', 'confirm_password'] as const;
type PasswordField = (typeof FIELDS)[number];
const EMPTY: Record<PasswordField, string> = {
  current_password: '',
  password: '',
  confirm_password: '',
};

/** The client checks: the current password (when there is one) and the new one's length. */
function checkPassword(current: string | null, password: string): ErrorDetail[] {
  const problems: ErrorDetail[] = [];
  if (current !== null && !current) problems.push(problem('current_password', 'required'));
  if (!password) problems.push(problem('password', 'required'));
  else if (password.length < PASSWORD_MIN_LENGTH)
    problems.push(problem('password', 'too_short', { min: PASSWORD_MIN_LENGTH }));
  else if (password.length > PASSWORD_MAX_LENGTH)
    problems.push(problem('password', 'too_long', { max: PASSWORD_MAX_LENGTH }));
  return problems;
}

/**
 * The password card of Security (F9-j S4, moved from Profile with its `prefs:profile.password.*`
 * strings). With a password: current + new + confirm, and the note that other devices are
 * signed out. Without one (an OAuth account): "Set a password", new + confirm only, sent
 * through `withReauth`. Either way `PATCH /me/account`, then `GET /me` (and the devices) are
 * refreshed.
 */
export function PasswordCard({ hasPassword, offline }: { hasPassword: boolean; offline: boolean }) {
  const { t, i18n } = useTranslation('prefs');
  const { t: tAccount } = useTranslation('account');
  const { t: tAuth } = useTranslation('auth');
  const queryClient = useQueryClient();
  const withReauth = useReauth();
  const form = useRef<HTMLFormElement>(null);
  const focus = useFormFocus(form);
  const [values, setValues] = useState(EMPTY);
  const [pending, setPending] = useState(false);
  const [errors, setErrors] = useState<FieldErrors<PasswordField>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const countdown = useRetryCountdown({ onEnd: () => announce(tAuth('retry.ready')) });
  const blocked = countdown.active;
  const title = hasPassword ? t('profile.password.title') : tAccount('password.setTitle');

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (pending || blocked || offline) return;
    const { current_password: current, password, confirm_password: confirm } = values;
    const local = fieldErrorsFromDetails(
      checkPassword(hasPassword ? current : null, password),
      i18n,
      FIELDS,
    );
    if (!local.password && confirm !== password) {
      local.confirm_password = t('profile.password.mismatch');
    }
    setErrors(local);
    setFormError(null);
    if (Object.keys(local).length > 0) return focus.request();

    setPending(true);
    try {
      const user = await withReauth(() =>
        patchAccount(hasPassword ? { current_password: current, password } : { password }),
      );
      applyUserChange(queryClient, user);
      setValues(EMPTY);
      pushToast({
        kind: 'success',
        message: hasPassword ? t('profile.password.saved') : tAccount('password.set'),
      });
      // `has_password` and the other devices (signed out by a change) are read again.
      void queryClient.invalidateQueries({ queryKey: ['me'] });
    } catch (error) {
      if (isReauthCancelled(error)) return;
      const failure = failureOf(error, i18n, FIELDS, {
        current_password_incorrect: 'current_password',
      });
      if (failure.kind === 'retry') {
        countdown.start(failure.seconds);
        announce(tAuth('retry.countdown', { count: failure.seconds }));
      } else if (failure.kind === 'form') setFormError(failure.message);
      else {
        setErrors(failure.errors);
        focus.request(failure.focus);
      }
    } finally {
      setPending(false);
    }
  };

  const control = (name: PasswordField, autoComplete: string) => ({
    name,
    value: values[name],
    onChange: (event: { target: { value: string } }) => {
      setValues((previous) => ({ ...previous, [name]: event.target.value }));
      setErrors((previous) => ({ ...previous, [name]: undefined }));
    },
    autoComplete,
    disabled: offline,
  });

  let label = hasPassword ? t('profile.password.save') : tAccount('password.setSave');
  if (pending) label = t('profile.password.saving');

  return (
    <SettingsCard
      title={title}
      description={hasPassword ? t('profile.password.hint') : tAccount('password.setHint')}
    >
      <form ref={form} className={styles.form} aria-label={title} onSubmit={onSubmit} noValidate>
        {formError && <FormAlert message={formError} />}
        {blocked && (
          <p className={styles.notice}>
            {tAuth('retry.countdown', { count: countdown.remaining })}
          </p>
        )}
        {hasPassword && (
          <Field label={t('profile.password.current')} error={errors.current_password} required>
            {(props) => (
              <PasswordInput {...props} {...control('current_password', 'current-password')} />
            )}
          </Field>
        )}
        <Field
          label={t('profile.password.new')}
          hint={t('profile.password.newHint')}
          error={errors.password}
          required
        >
          {(props) => <PasswordInput {...props} {...control('password', 'new-password')} />}
        </Field>
        <Field label={t('profile.password.confirm')} error={errors.confirm_password} required>
          {(props) => <PasswordInput {...props} {...control('confirm_password', 'new-password')} />}
        </Field>
        {hasPassword && <p className={styles.hint}>{tAccount('password.othersNote')}</p>}
        <div className={styles.actions}>
          <Button type="submit" pending={pending} disabled={offline || blocked}>
            {label}
          </Button>
        </div>
      </form>
    </SettingsCard>
  );
}
