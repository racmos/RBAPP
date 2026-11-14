import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useRef, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { patchAccount, patchMe } from '@/api/endpoints';
import type { AccountChanges, ErrorDetail, ProfilePatch, UserPayload } from '@/api/types';
import { useOffline, useSession } from '@/auth';
import { FormAlert } from '@/auth/FormAlert';
import { fieldErrorsFromDetails, useFormFocus, type FieldErrors } from '@/auth/formHelpers';
import {
  EMAIL_MAX_LENGTH,
  EMAIL_PATTERN,
  PASSWORD_MAX_LENGTH,
  PASSWORD_MIN_LENGTH,
} from '@/auth/registerChecks';
import { useRetryCountdown } from '@/auth/useRetryCountdown';
import { Avatar } from '@/components/ui/Avatar';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { ErrorState } from '@/components/ui/ErrorState';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { announce } from '@/components/ui/LiveAnnouncer';
import { PasswordInput } from '@/components/ui/PasswordInput';
import { SettingsCard } from '@/components/ui/SettingsCard';
import { Skeleton } from '@/components/ui/Skeleton';
import { pushToast } from '@/components/ui/toastStore';
import { translateError, useDocumentTitle } from '@/i18n';
import { formatDate } from '@/lib/format';
import { AccountHeader } from './AccountNav';
import { AvatarUpload } from './AvatarUpload';
import { DetailsForm } from './DetailsForm';
import { failureOf, problem } from './formFailure';
import styles from './ProfilePage.module.css';
import { applyUserChange, meQuery, metaConfigQuery } from './queries';

const EMAIL_FIELDS = ['email'] as const;
type EmailField = (typeof EMAIL_FIELDS)[number];
const PASSWORD_FIELDS = ['current_password', 'password', 'confirm_password'] as const;
type PasswordField = (typeof PASSWORD_FIELDS)[number];

/** A non-empty e-mail; an empty one is a removal, confirmed apart (F9-i S8). */
function checkEmail(email: string): ErrorDetail[] {
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

/**
 * The email form: sends only `email`, and only when it changed. Emptied with an e-mail on file,
 * it offers "Remove email" instead, after a confirmation (F9-i S8).
 */
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
  const [confirmRemove, setConfirmRemove] = useState(false);
  const { t: tAccount } = useTranslation('account');
  const next = value.trim();
  const removing = next === '' && email !== '';

  const fail = (error: unknown) => {
    const failure = failureOf(error, i18n, EMAIL_FIELDS, { email_taken: 'email' });
    if (failure.kind === 'retry') onRateLimited(failure.seconds);
    else if (failure.kind === 'form') setFormError(failure.message);
    else {
      setErrors(failure.errors);
      focus.request(failure.focus);
    }
  };

  const remove = async () => {
    setConfirmRemove(false);
    setFormError(null);
    setPending(true);
    try {
      await save({ email: null });
      setValue('');
      pushToast({ kind: 'success', message: tAccount('email.removed') });
    } catch (error) {
      fail(error);
    } finally {
      setPending(false);
    }
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (pending || blocked || offline || next === email) return;
    if (removing) return setConfirmRemove(true);
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
      fail(error);
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
        {!email && <p className={styles.hint}>{tAccount('email.none')}</p>}
        <Field label={t('profile.email.label')} error={errors.email}>
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
          {removing ? (
            <Button type="submit" variant="danger" pending={pending} disabled={offline || blocked}>
              {tAccount('email.remove')}
            </Button>
          ) : (
            <Button type="submit" pending={pending} disabled={offline || blocked || next === email}>
              {pending ? t('profile.email.saving') : t('profile.email.save')}
            </Button>
          )}
        </div>
      </form>
      <ConfirmDialog
        open={confirmRemove}
        title={tAccount('email.removeTitle')}
        message={tAccount('email.removeBody')}
        confirmLabel={tAccount('email.removeConfirm')}
        cancelLabel={tAccount('photo.cancel')}
        danger
        onConfirm={() => void remove()}
        onCancel={() => setConfirmRemove(false)}
      />
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

/** The identity card (F9-i S4): photo, name, `@username`, member date and the photo actions. */
function IdentityCard({
  user,
  memberSince,
  offline,
}: {
  user: UserPayload | null | undefined;
  memberSince: string | null;
  offline: boolean;
}) {
  const { t } = useTranslation('account');
  const username = user?.username ?? '';
  const name = user?.display_name || username;
  return (
    <SettingsCard title={t('identity.title')}>
      <div className={styles.identity}>
        <Avatar
          name={name}
          src={user?.avatar_url}
          size={80}
          label={t('identity.photoAlt', { name })}
        />
        <div className={styles.identityText}>
          <p className={styles.name}>{name}</p>
          <p className={styles.handle}>@{username}</p>
          {memberSince && (
            <p className={styles.hint}>
              {t('identity.memberSince', { date: formatDate(memberSince) })}
            </p>
          )}
        </div>
      </div>
      <AvatarUpload hasPhoto={Boolean(user?.avatar_url)} name={name} offline={offline} />
    </SettingsCard>
  );
}

/** A card-sized loading placeholder (F9-i S12). */
function CardSkeleton({ label }: { label: string }) {
  return (
    <div className={styles.skeletonCard}>
      <Skeleton label={label} lines={4} />
    </div>
  );
}

/**
 * `/account/profile` (F9-i): the identity card (photo), the details form (`PATCH /me`), and the
 * email and password forms (`PATCH /me/account`), each saved on its own. A saved change updates
 * the cached session and `GET /me`, so it shows everywhere. Offline, everything is read-only
 * from the cache; the email and password cards never wait for `GET /me`.
 */
export function ProfilePage() {
  const { t, i18n } = useTranslation('prefs');
  const { t: tAuth } = useTranslation('auth');
  const { t: tCommon } = useTranslation('common');
  useDocumentTitle(t('profile.title'));
  const queryClient = useQueryClient();
  const session = useSession();
  const offline = useOffline();
  const me = useQuery({ ...meQuery, enabled: !offline });
  const config = useQuery({ ...metaConfigQuery, enabled: !offline });
  const countdown = useRetryCountdown({ onEnd: () => announce(tAuth('retry.ready')) });
  const user = session?.user;

  const save = async (changes: AccountChanges) => {
    const fresh: UserPayload = await patchAccount(changes);
    applyUserChange(queryClient, fresh);
  };
  const saveDetails = async (changes: ProfilePatch) => {
    const fresh = await patchMe(changes);
    queryClient.setQueryData(meQuery.queryKey, fresh);
    applyUserChange(queryClient, fresh.user);
    return fresh;
  };
  const onRateLimited = (seconds: number) => {
    countdown.start(seconds);
    announce(tAuth('retry.countdown', { count: seconds }));
  };
  const forms = { offline, blocked: countdown.active, save, onRateLimited };

  // Offline the cards show what the cache has (S12); online they wait for `GET /me`.
  const ready = offline || me.data !== undefined;
  let profileCards;
  if (ready) {
    profileCards = (
      <>
        <IdentityCard
          user={user}
          memberSince={me.data?.security.member_since ?? null}
          offline={offline}
        />
        <DetailsForm
          key={me.data ? 'loaded' : 'empty'}
          profile={me.data?.profile ?? null}
          countries={config.data?.countries ?? []}
          offline={offline}
          blocked={countdown.active}
          save={saveDetails}
          onRateLimited={onRateLimited}
        />
      </>
    );
  } else if (me.isError) {
    profileCards = (
      <ErrorState message={translateError(me.error, i18n)} onRetry={() => void me.refetch()} />
    );
  } else {
    profileCards = (
      <>
        <CardSkeleton label={tCommon('loadingRegion')} />
        <CardSkeleton label={tCommon('loadingRegion')} />
      </>
    );
  }

  return (
    <>
      <AccountHeader title={t('profile.title')} subtitle={t('profile.subtitle')} />
      {countdown.active && (
        <p className={styles.notice}>{tAuth('retry.countdown', { count: countdown.remaining })}</p>
      )}
      <div className={styles.columns}>
        <div className={styles.stack}>{profileCards}</div>
        <div className={styles.forms}>
          {/* An account without an email (F9-b) shows an empty field. */}
          {user && <EmailForm email={user.email ?? ''} {...forms} />}
          <PasswordForm {...forms} />
        </div>
      </div>
    </>
  );
}
