import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router';
import { login } from '@/api/endpoints';
import { ApiError } from '@/api/errors';
import { Button } from '@/components/ui/Button';
import { Checkbox } from '@/components/ui/Checkbox';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { announce } from '@/components/ui/LiveAnnouncer';
import { PasswordInput } from '@/components/ui/PasswordInput';
import { useDocumentTitle, translateError } from '@/i18n';
import { navigateDocument } from '@/lib/navigateDocument';
import styles from './AuthForm.module.css';
import { FormAlert } from './FormAlert';
import { fieldErrorsFromDetails, useFormFocus, type FieldErrors } from './formHelpers';
import { safeNext } from './safeNext';
import { sessionQuery } from './session';
import { useRetryCountdown } from './useRetryCountdown';

const FIELDS = ['username', 'password'] as const;

const registeredUsername = (state: unknown): string =>
  typeof state === 'object' &&
  state !== null &&
  'username' in state &&
  typeof state.username === 'string'
    ? state.username
    : '';
type Field = (typeof FIELDS)[number];

/** Login (FAUTH-2, FAUTH-7, FAUTH-10). */
export function LoginPage() {
  const { t, i18n } = useTranslation('auth');
  useDocumentTitle(t('login.title'));
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [params] = useSearchParams();
  const location = useLocation();

  const form = useRef<HTMLFormElement>(null);
  const focus = useFormFocus(form);
  // After registering, the new username arrives in the navigation state.
  const [username, setUsername] = useState(() => registeredUsername(location.state));
  const [password, setPassword] = useState('');
  const [remember, setRemember] = useState(true);
  const [pending, setPending] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors<Field>>({});
  const [formError, setFormError] = useState<string | null>(null);

  // Start in the first empty field (after registering the username is already filled in).
  useEffect(() => {
    const first = username ? 'password' : 'username';
    const element = form.current?.elements.namedItem(first);
    if (element instanceof HTMLElement) element.focus();
    // Only on arrival.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const countdown = useRetryCountdown({ onEnd: () => announce(t('retry.ready')) });
  const blocked = countdown.active;

  const fail = (error: unknown) => {
    setFormError(null);
    if (error instanceof ApiError && error.status === 429 && error.retryAfter) {
      countdown.start(error.retryAfter);
      announce(t('retry.countdown', { count: error.retryAfter }));
      return;
    }
    if (error instanceof ApiError && error.kind === 'http' && error.details.length > 0) {
      const mapped = fieldErrorsFromDetails(error.details, i18n, FIELDS);
      if (Object.keys(mapped).length > 0) {
        setFieldErrors(mapped);
        focus.request();
        return;
      }
    }
    setFormError(translateError(error, i18n));
    if (error instanceof ApiError && error.code === 'invalid_credentials') {
      setPassword('');
      focus.request('password');
    }
  };

  const goNext = () => {
    const target = safeNext(params.get('next'));
    if (target.kind === 'document') navigateDocument(target.href);
    else void navigate(target.to, { replace: true });
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (pending || blocked) return;

    const missing: FieldErrors<Field> = {};
    if (!username.trim()) missing.username = i18n.t('errors:validation.required');
    if (!password) missing.password = i18n.t('errors:validation.required');
    setFieldErrors(missing);
    setFormError(null);
    if (Object.keys(missing).length > 0) {
      focus.request();
      return;
    }

    setPending(true);
    try {
      await login({ username: username.trim(), password, remember });
      const session = await queryClient.fetchQuery({ ...sessionQuery, staleTime: 0 });
      if (!session.authenticated) throw new ApiError({ kind: 'parse' });
      goNext();
    } catch (error) {
      fail(error);
    } finally {
      setPending(false);
    }
  };

  const edit =
    (field: Field, set: (value: string) => void) => (event: { target: { value: string } }) => {
      set(event.target.value);
      setFieldErrors((previous) => ({ ...previous, [field]: undefined }));
    };

  return (
    <>
      <h1 className={styles.title}>{t('login.title')}</h1>
      <p className={styles.subtitle}>{t('login.subtitle')}</p>
      <form ref={form} className={styles.form} onSubmit={onSubmit} noValidate>
        {formError && <FormAlert message={formError} />}
        {blocked && (
          <p className={styles.notice}>{t('retry.countdown', { count: countdown.remaining })}</p>
        )}
        <Field label={t('login.username')} error={fieldErrors.username} required>
          {(control) => (
            <Input
              {...control}
              name="username"
              value={username}
              onChange={edit('username', setUsername)}
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
            />
          )}
        </Field>
        <Field label={t('login.password')} error={fieldErrors.password} required>
          {(control) => (
            <PasswordInput
              {...control}
              name="password"
              value={password}
              onChange={edit('password', setPassword)}
              autoComplete="current-password"
            />
          )}
        </Field>
        <Checkbox
          label={t('login.remember')}
          checked={remember}
          onChange={(event) => setRemember(event.target.checked)}
        />
        <Button type="submit" block pending={pending} disabled={blocked}>
          {pending ? t('login.submitting') : t('login.submit')}
        </Button>
      </form>
      <p className={styles.footer}>
        {t('login.noAccount')} <Link to="/register">{t('login.createAccount')}</Link>
      </p>
    </>
  );
}
