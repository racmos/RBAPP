import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router';
import { getCaptcha, getMetaConfig, register } from '@/api/endpoints';
import { ApiError } from '@/api/errors';
import { Button } from '@/components/ui/Button';
import { ErrorState } from '@/components/ui/ErrorState';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { announce } from '@/components/ui/LiveAnnouncer';
import { PasswordInput } from '@/components/ui/PasswordInput';
import { Skeleton } from '@/components/ui/Skeleton';
import { pushToast } from '@/components/ui/toastStore';
import { translateDetail, translateError, useDocumentTitle } from '@/i18n';
import type { AltchaState } from './altcha';
import { AltchaWidget } from './AltchaWidget';
import styles from './AuthForm.module.css';
import { FormAlert } from './FormAlert';
import { fieldErrorsFromDetails, useFormFocus, type FieldErrors } from './formHelpers';
import { checkRegister } from './registerChecks';
import { useRetryCountdown } from './useRetryCountdown';

const FIELDS = ['username', 'email', 'password'] as const;
type FieldName = (typeof FIELDS)[number];

type Setup =
  | { status: 'loading' }
  | { status: 'error'; error: unknown }
  | { status: 'ready'; challenge: Record<string, unknown> | null; id: number };

/** Register (FAUTH-3, FAUTH-4, FAUTH-10). The ALTCHA widget exists only when the server asks for it. */
export function RegisterPage() {
  const { t, i18n } = useTranslation('auth');
  useDocumentTitle(t('register.title'));
  const navigate = useNavigate();

  const form = useRef<HTMLFormElement>(null);
  const focus = useFormFocus(form);
  const [values, setValues] = useState({ username: '', email: '', password: '' });
  const [fieldErrors, setFieldErrors] = useState<FieldErrors<FieldName>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [setup, setSetup] = useState<Setup>({ status: 'loading' });
  const [payload, setPayload] = useState<string | null>(null);
  const challengeId = useRef(0);
  const countdown = useRetryCountdown({ onEnd: () => announce(t('retry.ready')) });

  /** Config and a fresh challenge. `null` when the request was aborted (the page went away). */
  const fetchSetup = useCallback(async (signal?: AbortSignal): Promise<Setup | null> => {
    try {
      const [, captcha] = await Promise.all([getMetaConfig(signal), getCaptcha(signal)]);
      challengeId.current += 1;
      return {
        status: 'ready',
        challenge: captcha.provider !== 'none' ? captcha.challenge : null,
        id: challengeId.current,
      };
    } catch (error) {
      return signal?.aborted ? null : { status: 'error', error };
    }
  }, []);

  /** A new challenge after the old widget is dead: its payload is spent (FAUTH-4). */
  const reloadSetup = useCallback(
    async (showLoading = false) => {
      setPayload(null);
      if (showLoading) setSetup({ status: 'loading' });
      const next = await fetchSetup();
      if (next) setSetup(next);
    },
    [fetchSetup],
  );

  useEffect(() => {
    const controller = new AbortController();
    void fetchSetup(controller.signal).then((next) => {
      if (next) setSetup(next);
    });
    return () => controller.abort();
  }, [fetchSetup]);

  const onWidgetState = useCallback(
    (state: AltchaState, solved?: string) => {
      setPayload(state === 'verified' && solved ? solved : null);
      if (state === 'expired') void reloadSetup();
    },
    [reloadSetup],
  );

  const widgetInUse = setup.status === 'ready' && setup.challenge !== null;
  const waitingForWidget = widgetInUse && payload === null;
  const blocked = countdown.active;

  const fail = (error: unknown) => {
    setFormError(null);
    setFieldErrors({});
    const detail = error instanceof ApiError ? error : null;

    const taken =
      detail?.code === 'username_taken'
        ? 'username'
        : detail?.code === 'email_taken'
          ? 'email'
          : null;
    if (taken) {
      const message = translateError(error, i18n);
      setFieldErrors({ [taken]: message });
      announce(message);
      focus.request(taken);
    } else if (detail?.kind === 'http' && detail.details.length > 0) {
      const mapped = fieldErrorsFromDetails(detail.details, i18n, FIELDS);
      if (Object.keys(mapped).length > 0) {
        setFieldErrors(mapped);
        announce(Object.values(mapped).join(' '));
        focus.request();
      } else {
        setFormError(translateError(error, i18n));
      }
    } else if (detail?.status === 429 && detail.retryAfter) {
      countdown.start(detail.retryAfter);
      announce(t('retry.countdown', { count: detail.retryAfter }));
    } else {
      setFormError(translateError(error, i18n));
    }
    // The payload was consumed by the server whatever went wrong (FAUTH-4).
    void reloadSetup();
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (pending || blocked || waitingForWidget || setup.status !== 'ready') return;

    const problems = checkRegister(values);
    setFormError(null);
    if (problems.length > 0) {
      const errors: FieldErrors<FieldName> = {};
      for (const problem of problems) {
        errors[problem.field as FieldName] ??= translateDetail(problem, i18n);
      }
      setFieldErrors(errors);
      focus.request();
      return;
    }
    setFieldErrors({});

    setPending(true);
    try {
      await register({
        username: values.username.trim(),
        email: values.email.trim(),
        password: values.password,
        ...(widgetInUse && payload ? { altcha: payload } : {}),
      });
      pushToast({ kind: 'success', message: t('register.created') });
      await navigate('/login', { state: { username: values.username.trim() } });
    } catch (error) {
      fail(error);
    } finally {
      setPending(false);
    }
  };

  const edit = (field: FieldName) => (event: { target: { value: string } }) => {
    setValues((previous) => ({ ...previous, [field]: event.target.value }));
    setFieldErrors((previous) => ({ ...previous, [field]: undefined }));
  };

  return (
    <>
      <h1 className={styles.title}>{t('register.title')}</h1>
      <p className={styles.subtitle}>{t('register.subtitle')}</p>

      {setup.status === 'loading' && <Skeleton label={t('register.captchaLoading')} />}
      {setup.status === 'error' && (
        <ErrorState
          message={translateError(setup.error, i18n)}
          onRetry={() => void reloadSetup(true)}
        />
      )}
      {setup.status === 'ready' && (
        <form ref={form} className={styles.form} onSubmit={onSubmit} noValidate>
          {formError && <FormAlert message={formError} />}
          {blocked && (
            <p className={styles.notice}>{t('retry.countdown', { count: countdown.remaining })}</p>
          )}
          <Field
            label={t('register.username')}
            hint={t('register.usernameHint')}
            error={fieldErrors.username}
            required
          >
            {(control) => (
              <Input
                {...control}
                name="username"
                value={values.username}
                onChange={edit('username')}
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
              />
            )}
          </Field>
          <Field label={t('register.email')} error={fieldErrors.email} required>
            {(control) => (
              <Input
                {...control}
                name="email"
                type="email"
                value={values.email}
                onChange={edit('email')}
                autoComplete="email"
                spellCheck={false}
              />
            )}
          </Field>
          <Field
            label={t('register.password')}
            hint={t('register.passwordHint')}
            error={fieldErrors.password}
            required
          >
            {(control) => (
              <PasswordInput
                {...control}
                name="password"
                value={values.password}
                onChange={edit('password')}
                autoComplete="new-password"
              />
            )}
          </Field>
          {setup.challenge && (
            <fieldset className={styles.captcha}>
              <legend className={styles.captchaLegend}>{t('register.captchaGroup')}</legend>
              <AltchaWidget key={setup.id} challenge={setup.challenge} onState={onWidgetState} />
              {waitingForWidget && <p className={styles.hint}>{t('register.captchaPending')}</p>}
            </fieldset>
          )}
          <Button type="submit" block pending={pending} disabled={waitingForWidget || blocked}>
            {pending ? t('register.submitting') : t('register.submit')}
          </Button>
        </form>
      )}
      <p className={styles.footer}>
        {t('register.haveAccount')} <Link to="/login">{t('register.signIn')}</Link>
      </p>
    </>
  );
}
