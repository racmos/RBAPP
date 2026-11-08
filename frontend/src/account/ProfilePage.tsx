import { useQueryClient } from '@tanstack/react-query';
import type { i18n as I18n } from 'i18next';
import { useRef, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import { patchAccount } from '@/api/endpoints';
import { ApiError } from '@/api/errors';
import type { AccountChanges, ErrorDetail, Session, UserPayload } from '@/api/types';
import { sessionQuery, useOffline, useSession } from '@/auth';
import { FormAlert } from '@/auth/FormAlert';
import { fieldErrorsFromDetails, useFormFocus, type FieldErrors } from '@/auth/formHelpers';
import {
  EMAIL_MAX_LENGTH,
  EMAIL_PATTERN,
  PASSWORD_MAX_LENGTH,
  PASSWORD_MIN_LENGTH,
} from '@/auth/registerChecks';
import { useRetryCountdown } from '@/auth/useRetryCountdown';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Icon } from '@/components/ui/Icon';
import { Input } from '@/components/ui/Input';
import { announce } from '@/components/ui/LiveAnnouncer';
import { PageHeader } from '@/components/ui/PageHeader';
import { PasswordInput } from '@/components/ui/PasswordInput';
import { SettingsCard, SettingsRow } from '@/components/ui/SettingsCard';
import { pushToast } from '@/components/ui/toastStore';
import { translateError, useDocumentTitle } from '@/i18n';
import styles from './ProfilePage.module.css';

const EMAIL_FIELDS = ['email'] as const;
type EmailField = (typeof EMAIL_FIELDS)[number];
const PASSWORD_FIELDS = ['current_password', 'password', 'confirm_password'] as const;
type PasswordField = (typeof PASSWORD_FIELDS)[number];

/** What a failed save shows: the 429 countdown, errors on the fields, or the form alert. */
type Failure<Name extends string> =
  | { kind: 'retry'; seconds: number }
  | { kind: 'fields'; errors: FieldErrors<Name>; focus: Name | null }
  | { kind: 'form'; message: string };

function failureOf<Name extends string>(
  error: unknown,
  i18n: I18n,
  fields: readonly Name[],
  /** Error codes that belong to one field (`email_taken` -> `email`). */
  codeFields: Partial<Record<string, Name>>,
): Failure<Name> {
  if (error instanceof ApiError && error.status === 429 && error.retryAfter) {
    return { kind: 'retry', seconds: error.retryAfter };
  }
  if (error instanceof ApiError && error.kind === 'http') {
    const field = error.code ? codeFields[error.code] : undefined;
    if (field) {
      return {
        kind: 'fields',
        errors: { [field]: translateError(error, i18n) } as FieldErrors<Name>,
        focus: field,
      };
    }
    const mapped = fieldErrorsFromDetails(error.details, i18n, fields);
    if (Object.keys(mapped).length > 0) return { kind: 'fields', errors: mapped, focus: null };
  }
  return { kind: 'form', message: translateError(error, i18n) };
}

const problem = (field: string, code: string, params?: ErrorDetail['params']): ErrorDetail => ({
  field,
  code,
  params,
  message: code,
  type: 'client_check',
});

function checkEmail(email: string): ErrorDetail[] {
  if (!email) return [problem('email', 'required')];
  if (email.length > EMAIL_MAX_LENGTH)
    return [problem('email', 'too_long', { max: EMAIL_MAX_LENGTH })];
  if (!EMAIL_PATTERN.test(email)) return [problem('email', 'invalid_format')];
  return [];
}

function checkPassword(current: string, password: string): ErrorDetail[] {
  const problems: ErrorDetail[] = [];
  if (!current) problems.push(problem('current_password', 'required'));
  if (!password) problems.push(problem('password', 'required'));
  else if (password.length < PASSWORD_MIN_LENGTH)
    problems.push(problem('password', 'too_short', { min: PASSWORD_MIN_LENGTH }));
  else if (password.length > PASSWORD_MAX_LENGTH)
    problems.push(problem('password', 'too_long', { max: PASSWORD_MAX_LENGTH }));
  return problems;
}

type FormProps = {
  /** Offline: the controls are read-only. */
  offline: boolean;
  /** The 429 countdown is running: nothing can be sent. */
  blocked: boolean;
  /** Sends the changes; the page keeps the session and the countdown up to date. */
  save: (changes: AccountChanges) => Promise<void>;
  onRateLimited: (seconds: number) => void;
};

/** The email form: sends only `email`, and only when it changed. */
function EmailForm({
  email,
  offline,
  blocked,
  save,
  onRateLimited,
}: FormProps & { email: string }) {
  const { t, i18n } = useTranslation('prefs');
  const form = useRef<HTMLFormElement>(null);
  const focus = useFormFocus(form);
  const [value, setValue] = useState(email);
  const [pending, setPending] = useState(false);
  const [errors, setErrors] = useState<FieldErrors<EmailField>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const next = value.trim();

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (pending || blocked || offline || next === email) return;
    const local = fieldErrorsFromDetails(checkEmail(next), i18n, EMAIL_FIELDS);
    setErrors(local);
    setFormError(null);
    if (Object.keys(local).length > 0) return focus.request();

    setPending(true);
    try {
      await save({ email: next });
      setValue(next);
      pushToast({ kind: 'success', message: t('profile.email.saved') });
    } catch (error) {
      const failure = failureOf(error, i18n, EMAIL_FIELDS, { email_taken: 'email' });
      if (failure.kind === 'retry') onRateLimited(failure.seconds);
      else if (failure.kind === 'form') setFormError(failure.message);
      else {
        setErrors(failure.errors);
        focus.request(failure.focus);
      }
    } finally {
      setPending(false);
    }
  };

  return (
    <SettingsCard title={t('profile.email.title')} description={t('profile.email.hint')}>
      <form
        ref={form}
        className={styles.form}
        aria-label={t('profile.email.title')}
        onSubmit={onSubmit}
        noValidate
      >
        {formError && <FormAlert message={formError} />}
        <Field label={t('profile.email.label')} error={errors.email} required>
          {(control) => (
            <Input
              {...control}
              name="email"
              type="email"
              value={value}
              onChange={(event) => {
                setValue(event.target.value);
                setErrors({});
              }}
              autoComplete="email"
              autoCapitalize="none"
              spellCheck={false}
              disabled={offline}
            />
          )}
        </Field>
        <div className={styles.actions}>
          <Button type="submit" pending={pending} disabled={offline || blocked || next === email}>
            {pending ? t('profile.email.saving') : t('profile.email.save')}
          </Button>
        </div>
      </form>
    </SettingsCard>
  );
}

/** The password form: sends `current_password` and `password`; clears itself once saved. */
function PasswordForm({ offline, blocked, save, onRateLimited }: FormProps) {
  const { t, i18n } = useTranslation('prefs');
  const form = useRef<HTMLFormElement>(null);
  const focus = useFormFocus(form);
  const [values, setValues] = useState<Record<PasswordField, string>>({
    current_password: '',
    password: '',
    confirm_password: '',
  });
  const [pending, setPending] = useState(false);
  const [errors, setErrors] = useState<FieldErrors<PasswordField>>({});
  const [formError, setFormError] = useState<string | null>(null);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (pending || blocked || offline) return;
    const { current_password: current, password, confirm_password: confirm } = values;
    const local = fieldErrorsFromDetails(checkPassword(current, password), i18n, PASSWORD_FIELDS);
    if (!local.password && confirm !== password) {
      local.confirm_password = t('profile.password.mismatch');
    }
    setErrors(local);
    setFormError(null);
    if (Object.keys(local).length > 0) return focus.request();

    setPending(true);
    try {
      await save({ current_password: current, password });
      setValues({ current_password: '', password: '', confirm_password: '' });
      pushToast({ kind: 'success', message: t('profile.password.saved') });
    } catch (error) {
      const failure = failureOf(error, i18n, PASSWORD_FIELDS, {
        current_password_incorrect: 'current_password',
      });
      if (failure.kind === 'retry') onRateLimited(failure.seconds);
      else if (failure.kind === 'form') setFormError(failure.message);
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

  return (
    <SettingsCard title={t('profile.password.title')} description={t('profile.password.hint')}>
      <form
        ref={form}
        className={styles.form}
        aria-label={t('profile.password.title')}
        onSubmit={onSubmit}
        noValidate
      >
        {formError && <FormAlert message={formError} />}
        <Field label={t('profile.password.current')} error={errors.current_password} required>
          {(props) => (
            <PasswordInput {...props} {...control('current_password', 'current-password')} />
          )}
        </Field>
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
        <div className={styles.actions}>
          <Button type="submit" pending={pending} disabled={offline || blocked}>
            {pending ? t('profile.password.saving') : t('profile.password.save')}
          </Button>
        </div>
      </form>
    </SettingsCard>
  );
}

/**
 * `/account/profile`: the username (read-only), the email and the password, each form saved on
 * its own through `PATCH /me/account`. A saved change updates the cached session, so the new
 * email shows everywhere; a password change keeps the session.
 */
export function ProfilePage() {
  const { t } = useTranslation('prefs');
  const { t: tAuth } = useTranslation('auth');
  useDocumentTitle(t('profile.title'));
  const queryClient = useQueryClient();
  const session = useSession();
  const offline = useOffline();
  const countdown = useRetryCountdown({ onEnd: () => announce(tAuth('retry.ready')) });
  const user = session?.user;

  const save = async (changes: AccountChanges) => {
    const fresh: UserPayload = await patchAccount(changes);
    queryClient.setQueryData<Session>(sessionQuery.queryKey, (old) =>
      old ? { ...old, user: fresh } : old,
    );
  };
  const onRateLimited = (seconds: number) => {
    countdown.start(seconds);
    announce(tAuth('retry.countdown', { count: seconds }));
  };
  const forms = { offline, blocked: countdown.active, save, onRateLimited };

  return (
    <>
      <PageHeader
        title={t('profile.title')}
        subtitle={t('profile.subtitle')}
        actions={
          <Link to="/account/interface" className={styles.link}>
            <Icon name="sliders" size={16} />
            {t('profile.interfaceLink')}
          </Link>
        }
      />
      {countdown.active && (
        <p className={styles.notice}>{tAuth('retry.countdown', { count: countdown.remaining })}</p>
      )}
      <div className={styles.layout}>
        <div className={styles.wide}>
          <SettingsCard title={t('profile.account')}>
            <SettingsRow>
              <div className={styles.text}>
                <span className={styles.label}>{t('profile.username')}</span>
                <p className={styles.hint}>{t('profile.usernameHint')}</p>
              </div>
              <span className={styles.value}>{user?.username}</span>
            </SettingsRow>
          </SettingsCard>
        </div>
        {user && <EmailForm email={user.email} {...forms} />}
        <PasswordForm {...forms} />
      </div>
    </>
  );
}
