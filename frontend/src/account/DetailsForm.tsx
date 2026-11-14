import { useMemo, useRef, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import type { ErrorDetail, MeData, ProfileData, ProfilePatch } from '@/api/types';
import { FormAlert } from '@/auth/FormAlert';
import { fieldErrorsFromDetails, useFormFocus, type FieldErrors } from '@/auth/formHelpers';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { SettingsCard } from '@/components/ui/SettingsCard';
import { pushToast } from '@/components/ui/toastStore';
import { failureOf, problem } from './formFailure';
import styles from './ProfilePage.module.css';

const FIELDS = ['display_name', 'bio', 'country', 'city'] as const;
type DetailField = (typeof FIELDS)[number];
type Values = Record<DetailField, string>;

/** The server limits of the profile (F9-b S8), mirrored so a long value never leaves. */
const LIMITS: Record<Exclude<DetailField, 'country'>, number> = {
  display_name: 40,
  bio: 240,
  city: 80,
};

/** Characters as the server counts them (code points, not UTF-16 units). */
const length = (value: string) => Array.from(value).length;

const valuesOf = (profile: ProfileData | null): Values => ({
  display_name: profile?.display_name ?? '',
  bio: profile?.bio ?? '',
  country: profile?.country ?? '',
  city: profile?.city ?? '',
});

function check(values: Values): ErrorDetail[] {
  return (Object.keys(LIMITS) as (keyof typeof LIMITS)[])
    .filter((field) => length(values[field].trim()) > LIMITS[field])
    .map((field) => problem(field, 'too_long', { max: LIMITS[field] }));
}

/** Country codes labelled with their English names (the code when there is none), sorted. */
export function countryOptions(codes: readonly string[]): { code: string; label: string }[] {
  let names: Intl.DisplayNames | null = null;
  try {
    names = new Intl.DisplayNames(['en'], { type: 'region' });
  } catch {
    names = null;
  }
  const label = (code: string) => {
    try {
      return names?.of(code) || code;
    } catch {
      return code;
    }
  };
  return codes
    .map((code) => ({ code, label: label(code) }))
    .sort((a, b) => a.label.localeCompare(b.label, 'en'));
}

type DetailsFormProps = {
  profile: ProfileData | null;
  countries: readonly string[];
  offline: boolean;
  /** The 429 countdown is running: nothing can be sent. */
  blocked: boolean;
  /** Sends the changes; the page updates the caches with the answer. */
  save: (changes: ProfilePatch) => Promise<MeData>;
  onRateLimited: (seconds: number) => void;
};

/**
 * The details card (F9-i S7): display name, bio, country and city, saved together through
 * `PATCH /me` with only the fields that changed (`""` clears one).
 */
export function DetailsForm({
  profile,
  countries,
  offline,
  blocked,
  save,
  onRateLimited,
}: DetailsFormProps) {
  const { t, i18n } = useTranslation('account');
  const form = useRef<HTMLFormElement>(null);
  const focus = useFormFocus(form);
  const [saved, setSaved] = useState<Values>(() => valuesOf(profile));
  const [values, setValues] = useState<Values>(saved);
  const [pending, setPending] = useState(false);
  const [errors, setErrors] = useState<FieldErrors<DetailField>>({});
  const [formError, setFormError] = useState<string | null>(null);

  const changes = useMemo(() => {
    const changed: ProfilePatch = {};
    for (const field of FIELDS) {
      const next = values[field].trim();
      if (next !== saved[field]) changed[field] = next;
    }
    return changed;
  }, [values, saved]);
  const dirty = Object.keys(changes).length > 0;

  // The saved country stays selectable even when the list does not have it (offline).
  const options = useMemo(
    () =>
      countryOptions(
        saved.country && !countries.includes(saved.country)
          ? [...countries, saved.country]
          : countries,
      ),
    [countries, saved.country],
  );

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (pending || blocked || offline || !dirty) return;
    const local = fieldErrorsFromDetails(check(values), i18n, FIELDS);
    setErrors(local);
    setFormError(null);
    if (Object.keys(local).length > 0) return focus.request();

    setPending(true);
    try {
      const fresh = await save(changes);
      const next = valuesOf(fresh.profile);
      setSaved(next);
      setValues(next);
      pushToast({ kind: 'success', message: t('details.saved') });
    } catch (error) {
      const failure = failureOf(error, i18n, FIELDS);
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

  const edit = (field: DetailField) => (event: { target: { value: string } }) => {
    setValues((previous) => ({ ...previous, [field]: event.target.value }));
    setErrors((previous) => ({ ...previous, [field]: undefined }));
  };

  return (
    <SettingsCard title={t('details.title')} description={t('details.hint')}>
      <form
        ref={form}
        className={styles.form}
        aria-label={t('details.title')}
        onSubmit={onSubmit}
        noValidate
      >
        {formError && <FormAlert message={formError} />}
        <Field
          label={t('details.displayName')}
          hint={t('details.displayNameHint')}
          error={errors.display_name}
        >
          {(control) => (
            <Input
              {...control}
              name="display_name"
              value={values.display_name}
              onChange={edit('display_name')}
              autoComplete="nickname"
              disabled={offline}
            />
          )}
        </Field>
        <Field
          label={t('details.bio')}
          hint={t('details.bioCount', { count: length(values.bio) })}
          error={errors.bio}
        >
          {(control) => (
            <textarea
              {...control}
              name="bio"
              className={styles.textarea}
              rows={4}
              value={values.bio}
              onChange={edit('bio')}
              disabled={offline}
            />
          )}
        </Field>
        <Field label={t('details.country')} error={errors.country}>
          {(control) => (
            <Select
              {...control}
              name="country"
              value={values.country}
              onChange={edit('country')}
              autoComplete="country"
              disabled={offline}
            >
              <option value="">{t('details.countryNone')}</option>
              {options.map((option) => (
                <option key={option.code} value={option.code}>
                  {option.label}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label={t('details.city')} error={errors.city}>
          {(control) => (
            <Input
              {...control}
              name="city"
              value={values.city}
              onChange={edit('city')}
              autoComplete="address-level2"
              disabled={offline}
            />
          )}
        </Field>
        <div className={styles.actions}>
          <Button type="submit" pending={pending} disabled={offline || blocked || !dirty}>
            {pending ? t('details.saving') : t('details.save')}
          </Button>
        </div>
      </form>
    </SettingsCard>
  );
}
