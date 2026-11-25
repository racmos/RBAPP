import { useRef, useState, type ReactNode } from 'react';
import type { i18n as I18n } from 'i18next';
import { useTranslation } from 'react-i18next';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ApiError } from '@/api/errors';
import { uploadAdminCardImage, type AdminCard } from '@/api/endpoints';
import type { ErrorDetail } from '@/api/types';
import { fieldErrorsFromDetails } from '@/auth/formHelpers';
import { Button } from '@/components/ui/Button';
import { Field, type FieldControlProps } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { pushToast } from '@/components/ui/toastStore';
import { translateError } from '@/i18n';
import { isCardNumber, readCardCode, type CardCodeRead } from './cardCode';
import { FormAlert } from './FormAlert';
import { finalizeLater, resultText } from './images/uploadImage';
import styles from './CardsAdminPage.module.css';

export type CardForm = Record<string, string>;

const TEXT_FIELDS = [
  ['name', true],
  ['domain', false],
  ['type', false],
  ['tags', false],
  ['energy', false],
  ['power', false],
  ['might', false],
  ['rarity', false],
  ['artist', false],
  ['image_url', false],
] as const;

/** Every field of the card form, in its order: the server `details[]` map onto these. */
export const CARD_FIELDS = [
  'set_id',
  'card_id',
  'name',
  'domain',
  'type',
  'tags',
  'energy',
  'power',
  'might',
  'ability',
  'rarity',
  'artist',
  'image_url',
] as const;
export type CardField = (typeof CARD_FIELDS)[number];

export function toForm(card: AdminCard | null): CardForm {
  return {
    set_id: card?.set_id ?? '',
    card_id: card?.card_id ?? '',
    name: card?.name ?? '',
    domain: card?.domain ?? '',
    type: card?.type ?? '',
    tags: card?.tags ?? '',
    energy: card?.energy?.toString() ?? '',
    power: card?.power?.toString() ?? '',
    might: card?.might?.toString() ?? '',
    ability: card?.ability ?? '',
    rarity: card?.rarity ?? '',
    artist: card?.artist ?? '',
    image_url: card?.image_url ?? '',
  };
}

/** The body of a card write without the keys: blank texts are null, numbers are parsed. */
export function cardInput(form: CardForm) {
  const numbers: Record<string, number | null> = {};
  for (const field of ['energy', 'power', 'might']) {
    const raw = form[field].trim();
    numbers[field] = raw === '' ? null : Number.parseInt(raw, 10);
  }
  return {
    name: form.name,
    domain: form.domain || null,
    type: form.type || null,
    tags: form.tags || null,
    ...numbers,
    ability: form.ability || null,
    rarity: form.rarity || null,
    artist: form.artist || null,
    image_url: form.image_url || null,
  };
}

/** The `card_id` detail codes that mean "not a card number" (pattern, length). */
const NUMBER_DETAIL_CODES = new Set(['invalid_format', 'too_long', 'too_short']);

/**
 * A 400 of a card write as errors per field (CM-j): the `card_id` pattern or length error
 * reads as the number rule, so the admin learns the set goes in the Set field.
 */
export function cardFieldErrors(
  details: readonly ErrorDetail[],
  i18n: I18n,
  numberRule: string,
): Partial<Record<CardField, string>> {
  const errors = fieldErrorsFromDetails(details, i18n, CARD_FIELDS);
  const number = details.find((detail) => detail.field === 'card_id');
  if (number && NUMBER_DETAIL_CODES.has(number.code ?? '')) errors.card_id = numberRule;
  return errors;
}

/** What the Number field of a new card needs from `useCardNumber`. */
export type CardNumberInput = {
  error: string | null;
  status: string | null;
  onChange: (value: string) => void;
  onBlur: () => void;
  onPaste: () => void;
};

/**
 * The Number field of a new card (CM-j). A full code whose letters are a set (`OGNX-197`)
 * is read when the field is left, pasted or submitted: the set goes to the set field and the
 * number stays. The number is checked as the API does, from the first time it is left.
 * A plated code (`PLAT-SFD-189`) reads as set PLAT, number `sfd189`; with PLAT chosen, a number
 * such as `sfd189` stays as typed (CM-k).
 */
export function useCardNumber(
  form: CardForm,
  onChange: (patch: Partial<CardForm>) => void,
  setIds: readonly string[],
) {
  const { t } = useTranslation('admin');
  const [checked, setChecked] = useState(false);
  const [read, setRead] = useState<CardCodeRead | null>(null);
  const pasted = useRef(false);

  const apply = (value: string, setId: string = form.set_id) => {
    const found = readCardCode(value, setIds, setId);
    if (found) {
      onChange({ set_id: found.setId, card_id: found.number });
      setRead(found);
    }
    return found;
  };

  const input: CardNumberInput = {
    error: checked && !isCardNumber(form.card_id) ? t('cards.number.invalid') : null,
    status: read
      ? t('cards.number.read', { code: read.code, set: read.setId, number: read.number })
      : null,
    onChange: (value) => {
      setRead(null);
      const paste = pasted.current;
      pasted.current = false;
      if (paste && apply(value)) return;
      onChange({ card_id: value });
    },
    onBlur: () => {
      apply(form.card_id);
      // an empty field left on the way is not an error yet: the submit says it
      if (form.card_id.trim() !== '') setChecked(true);
    },
    onPaste: () => {
      pasted.current = true;
    },
  };

  /** Before a create: the form to send (with a full code read), or null when it is refused. */
  const check = (current: CardForm): CardForm | null => {
    setChecked(true);
    const found = apply(current.card_id, current.set_id);
    const next = found ? { ...current, set_id: found.setId, card_id: found.number } : current;
    return isCardNumber(next.card_id) ? next : null;
  };

  return { input, check };
}

type CardFieldsProps = {
  form: CardForm;
  onChange: (patch: Partial<CardForm>) => void;
  errors: Partial<Record<string, string>>;
  disabled: boolean;
  creating: boolean;
  /** Another control for the set (the Cardmarket form offers a select of the sets). */
  setControl?: (control: FieldControlProps) => ReactNode;
  /** A hint per field; it comes before a field's own hint (domain, type, tags). */
  hints?: Partial<Record<CardField, string>>;
  /** The Number field of a new card (`useCardNumber`, CM-j). */
  number?: CardNumberInput;
};

/** The fields of a card, shared by the cards admin and the Cardmarket create form (CM-c). */
export function CardFields({
  form,
  onChange,
  errors,
  disabled,
  creating,
  setControl,
  hints,
  number,
}: CardFieldsProps) {
  const { t } = useTranslation('admin');
  return (
    <>
      <Field
        label={t('cards.fields.set_id')}
        hint={hints?.set_id}
        error={errors.set_id}
        required={creating}
      >
        {(control) =>
          setControl ? (
            setControl(control)
          ) : (
            <Input
              {...control}
              value={form.set_id}
              disabled={disabled || !creating}
              onChange={(event) => onChange({ set_id: event.target.value })}
            />
          )
        }
      </Field>
      <Field
        label={t('cards.fields.card_id')}
        hint={hints?.card_id}
        error={number?.error ?? errors.card_id}
        required={creating}
      >
        {(control) => (
          <Input
            {...control}
            value={form.card_id}
            disabled={disabled || !creating}
            onChange={(event) =>
              number
                ? number.onChange(event.target.value)
                : onChange({ card_id: event.target.value })
            }
            onBlur={number?.onBlur}
            onPaste={number?.onPaste}
          />
        )}
      </Field>
      {number?.status && (
        <p role="status" className={styles.hint}>
          {number.status}
        </p>
      )}
      {!creating && <p className={styles.hint}>{t('cards.keyLocked')}</p>}
      <Field
        label={t('cards.fields.name')}
        hint={hints?.name}
        error={errors.name}
        required={creating}
      >
        {(control) => (
          <Input
            {...control}
            value={form.name}
            disabled={disabled}
            onChange={(event) => onChange({ name: event.target.value })}
          />
        )}
      </Field>
      {TEXT_FIELDS.slice(1).map(([name, required]) => (
        <Field
          key={name}
          label={t(`cards.fields.${name}` as 'cards.fields.domain')}
          hint={
            [
              hints?.[name],
              name === 'domain'
                ? t('cards.hints.domain')
                : name === 'type'
                  ? t('cards.hints.type')
                  : name === 'tags'
                    ? t('cards.hints.tags')
                    : undefined,
            ]
              .filter(Boolean)
              .join(' ') || undefined
          }
          error={errors[name]}
          required={required && creating}
        >
          {(control) => (
            <Input
              {...control}
              value={form[name]}
              type={name === 'energy' || name === 'power' || name === 'might' ? 'number' : 'text'}
              disabled={disabled}
              onChange={(event) => onChange({ [name]: event.target.value })}
            />
          )}
        </Field>
      ))}
      <Field label={t('cards.fields.ability')} hint={hints?.ability} error={errors.ability}>
        {(control) => (
          <textarea
            {...control}
            rows={6}
            value={form.ability}
            disabled={disabled}
            onChange={(event) => onChange({ ability: event.target.value })}
          />
        )}
      </Field>
    </>
  );
}

type CardEditorProps = {
  initial: AdminCard | null;
  /** The set ids, to read a full card code typed in Number (CM-j). */
  setIds?: readonly string[];
  fieldErrors: Partial<Record<CardField, string>>;
  formError: string | null;
  pending: boolean;
  offline: boolean;
  offlineHint: string;
  onSave: (form: CardForm, creating: boolean) => void;
  onCancel: () => void;
  onDelete: () => void;
};

/** Create/edit form for a card, with the image block (F13-f S8). */
export function CardEditor({
  initial,
  setIds = [],
  fieldErrors: serverErrors,
  formError,
  pending,
  offline,
  offlineHint,
  onSave,
  onCancel,
  onDelete,
}: CardEditorProps) {
  const { t, i18n } = useTranslation('admin');
  const { t: common } = useTranslation('common');
  const queryClient = useQueryClient();
  const [form, setForm] = useState<CardForm>(() => toForm(initial));
  const [image, setImage] = useState(initial?.image ?? null);
  const [imageSrc, setImageSrc] = useState(initial?.image_src ?? null);
  const [fieldErrors, setFieldErrors] = useState<Partial<Record<string, string>>>({});
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadResult, setUploadResult] = useState<string | null>(null);
  const creating = initial === null;
  const disabled = pending || offline;
  const set = (patch: Partial<CardForm>) =>
    setForm((current) => ({ ...current, ...patch }) as CardForm);
  const shown = { ...serverErrors, ...fieldErrors };
  const number = useCardNumber(form, set, setIds);

  const upload = useMutation({
    mutationFn: (file: File) => {
      if (!initial) throw new Error('no card');
      return uploadAdminCardImage(initial.set_id, initial.card_id, file);
    },
    onSuccess: (card) => {
      setImage(card.image);
      setImageSrc(card.image_src);
      setUploadError(null);
      setFieldErrors({});
      // F13-h S11: the server resized and renamed it; its previous file goes with the toast (S7)
      setUploadResult(resultText(i18n, card));
      pushToast({
        kind: 'success',
        message: t('cards.image.uploaded'),
        onExpire: finalizeLater({ type: 'card', setId: card.set_id }, card.previous),
      });
      void queryClient.invalidateQueries({ queryKey: ['admin'] });
    },
    onError: (error: unknown) => {
      setUploadResult(null);
      if (error instanceof ApiError && error.kind === 'http' && error.status === 400) {
        const mapped = fieldErrorsFromDetails(error.details, i18n, ['file'] as const);
        setFieldErrors(mapped);
        if (Object.keys(mapped).length === 0) setUploadError(translateError(error, i18n));
      } else {
        setUploadError(translateError(error, i18n));
      }
    },
  });

  return (
    <form
      className={styles.form}
      onSubmit={(event) => {
        event.preventDefault();
        if (!creating) {
          onSave(form, creating);
          return;
        }
        const checked = number.check(form);
        if (checked) onSave(checked, creating);
      }}
    >
      <CardFields
        form={form}
        onChange={set}
        errors={shown}
        disabled={disabled}
        creating={creating}
        number={creating ? number.input : undefined}
      />
      <div>
        {imageSrc && <img src={imageSrc} alt="" className={styles.preview} />}
        {!creating && (
          <Field
            label={t('cards.image.upload')}
            hint={t('cards.image.hint')}
            error={uploadError ?? undefined}
          >
            {(control) => (
              <input
                {...control}
                type="file"
                accept="image/png,image/jpeg,image/webp"
                disabled={disabled || upload.isPending}
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) upload.mutate(file);
                }}
              />
            )}
          </Field>
        )}
      </div>
      {image && <p className={styles.hint}>{image}</p>}
      {uploadResult && (
        <p role="status" className={styles.hint}>
          {uploadResult}
        </p>
      )}
      {formError && <FormAlert message={formError} />}
      <div className={styles.actions}>
        <Button type="submit" disabled={disabled}>
          {common('actions.save')}
        </Button>
        <Button type="button" variant="ghost" onClick={onCancel}>
          {common('actions.cancel')}
        </Button>
        {!creating && (
          <Button type="button" variant="danger" disabled={disabled} onClick={onDelete}>
            {common('actions.delete')}
          </Button>
        )}
      </div>
      {offline && <span className="sr-only">{offlineHint}</span>}
    </form>
  );
}
