import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useRef, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { patchAccount, patchMe } from '@/api/endpoints';
import type { AccountChanges, ErrorDetail, ProfilePatch, UserPayload } from '@/api/types';
import { useOffline, useSession } from '@/auth';
import { FormAlert } from '@/auth/FormAlert';
import { fieldErrorsFromDetails, useFormFocus, type FieldErrors } from '@/auth/formHelpers';
import { EMAIL_MAX_LENGTH, EMAIL_PATTERN } from '@/auth/registerChecks';
import { useRetryCountdown } from '@/auth/useRetryCountdown';
import { Avatar } from '@/components/ui/Avatar';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { ErrorState } from '@/components/ui/ErrorState';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { announce } from '@/components/ui/LiveAnnouncer';
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

/** A non-empty e-mail; an empty one is a removal, confirmed apart (F9-i S8). */
function checkEmail(email: string): ErrorDetail[] {
  if (email.length > EMAIL_MAX_LENGTH)
    return [problem('email', 'too_long', { max: EMAIL_MAX_LENGTH })];
  if (!EMAIL_PATTERN.test(email)) return [problem('email', 'invalid_format')];
  return [];
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
 * email form (`PATCH /me/account`), each saved on its own. The password card moved to Security
 * (F9-j S1). A saved change updates
 * the cached session and `GET /me`, so it shows everywhere. Offline, everything is read-only
 * from the cache; the email card never waits for `GET /me`.
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
        </div>
      </div>
    </>
  );
}
