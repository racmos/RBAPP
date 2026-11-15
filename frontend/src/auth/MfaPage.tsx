import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useSearchParams } from 'react-router';
import { completeMfa } from '@/api/endpoints';
import { ApiError } from '@/api/errors';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { announce } from '@/components/ui/LiveAnnouncer';
import { pushToast } from '@/components/ui/toastStore';
import { translateError, useDocumentTitle } from '@/i18n';
import { navigateDocument } from '@/lib/navigateDocument';
import styles from './AuthForm.module.css';
import { FormAlert } from './FormAlert';
import { useOffline } from './offline';
import { safeNext } from './safeNext';
import { sessionQuery } from './session';
import { useRetryCountdown } from './useRetryCountdown';

type Mode = 'code' | 'recovery';

/** `/login` with the same `next`, for "Back to sign in" and an ended step. */
const loginPath = (next: string | null) =>
  next ? `/login?next=${encodeURIComponent(next)}` : '/login';

/**
 * Two-step verification (F9-j S13): after the password, a code from the authenticator app or
 * a recovery code completes the sign-in (`POST /auth/mfa`). Without a pending step the screen
 * sends the visitor back to `/login`; an expired step does too, with the reason.
 */
export function MfaPage() {
  const { t, i18n } = useTranslation('auth');
  useDocumentTitle(t('mfa.title'));
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [params] = useSearchParams();
  const next = params.get('next');
  const offline = useOffline();
  const form = useRef<HTMLFormElement>(null);
  const [mode, setMode] = useState<Mode>('code');
  const [value, setValue] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const countdown = useRetryCountdown({ onEnd: () => announce(t('retry.ready')) });
  const blocked = countdown.active;

  const focusField = () => form.current?.querySelector<HTMLElement>('input')?.focus();

  // The login page does not read the session before coming here: this screen does, once.
  useEffect(() => {
    let active = true;
    queryClient
      .fetchQuery({ ...sessionQuery, staleTime: 0 })
      .then((session) => {
        if (active && !session.authenticated && !session.mfa_pending) {
          void navigate(loginPath(next), { replace: true });
        }
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
    // Only on arrival.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // The field takes focus on arrival and after each switch (F9-j S13).
  useEffect(() => {
    form.current?.querySelector<HTMLElement>('input')?.focus();
  }, [mode]);

  const switchTo = (nextMode: Mode) => {
    setMode(nextMode);
    setValue('');
    setError(null);
    setFormError(null);
  };

  const goNext = () => {
    const target = safeNext(next);
    if (target.kind === 'document') navigateDocument(target.href);
    else void navigate(target.to, { replace: true });
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (pending || blocked || offline) return;
    const answer = mode === 'code' ? value.replace(/\s/g, '') : value.trim();
    setFormError(null);
    if (!answer) {
      setError(i18n.t('errors:validation.required'));
      return focusField();
    }
    setPending(true);
    try {
      const result = await completeMfa(
        mode === 'code' ? { code: answer } : { recovery_code: answer },
      );
      const session = await queryClient.fetchQuery({ ...sessionQuery, staleTime: 0 });
      if (!session.authenticated) throw new ApiError({ kind: 'parse' });
      if (result.recovery_code_used) {
        pushToast({
          kind: 'info',
          message: t('mfa.codesLeft', { count: result.recovery_codes_left }),
        });
      }
      goNext();
    } catch (failed) {
      if (failed instanceof ApiError && failed.code === 'mfa_expired') {
        void navigate(loginPath(next), {
          replace: true,
          state: { alert: translateError(failed, i18n) },
        });
        return;
      }
      if (failed instanceof ApiError && failed.status === 429 && failed.retryAfter) {
        countdown.start(failed.retryAfter);
        announce(t('retry.countdown', { count: failed.retryAfter }));
      } else if (failed instanceof ApiError && failed.code === 'mfa_invalid') {
        setError(translateError(failed, i18n));
        focusField();
      } else setFormError(translateError(failed, i18n));
    } finally {
      setPending(false);
    }
  };

  const onChange = (event: { target: { value: string } }) => {
    setValue(event.target.value);
    setError(null);
  };

  return (
    <>
      <h1 className={styles.title}>{t('mfa.title')}</h1>
      <p className={styles.subtitle}>{mode === 'code' ? t('mfa.text') : t('mfa.recoveryText')}</p>
      <form ref={form} className={styles.form} onSubmit={onSubmit} noValidate>
        {formError && <FormAlert message={formError} />}
        {blocked && (
          <p className={styles.notice}>{t('retry.countdown', { count: countdown.remaining })}</p>
        )}
        {offline && <p className={styles.notice}>{t('mfa.offline')}</p>}
        {mode === 'code' ? (
          <Field key="code" label={t('mfa.code')} error={error ?? undefined} required>
            {(control) => (
              <Input
                {...control}
                name="code"
                value={value}
                onChange={onChange}
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                spellCheck={false}
              />
            )}
          </Field>
        ) : (
          <Field key="recovery" label={t('mfa.recovery')} error={error ?? undefined} required>
            {(control) => (
              <Input
                {...control}
                name="recovery_code"
                value={value}
                onChange={onChange}
                type="text"
                autoComplete="off"
                autoCapitalize="none"
                spellCheck={false}
              />
            )}
          </Field>
        )}
        <button
          type="button"
          className={styles.linkButton}
          onClick={() => switchTo(mode === 'code' ? 'recovery' : 'code')}
        >
          {mode === 'code' ? t('mfa.useRecovery') : t('mfa.useApp')}
        </button>
        <Button type="submit" block pending={pending} disabled={blocked || offline}>
          {pending ? t('mfa.submitting') : t('mfa.submit')}
        </Button>
      </form>
      <p className={styles.footer}>
        <Link to={loginPath(next)}>{t('mfa.back')}</Link>
      </p>
    </>
  );
}
