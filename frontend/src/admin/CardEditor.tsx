import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ApiError } from '@/api/errors';
import { uploadAdminCardImage, type AdminCard } from '@/api/endpoints';
import { fieldErrorsFromDetails } from '@/auth/formHelpers';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { pushToast } from '@/components/ui/toastStore';
import { translateError } from '@/i18n';
import { FormAlert } from './FormAlert';
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

type CardField = (typeof TEXT_FIELDS)[number][0] | 'set_id' | 'card_id' | 'ability';

function toForm(card: AdminCard | null): CardForm {
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

type CardEditorProps = {
  initial: AdminCard | null;
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
  const creating = initial === null;
  const disabled = pending || offline;
  const set = (patch: Partial<CardForm>) =>
    setForm((current) => ({ ...current, ...patch }) as CardForm);
  const shown = { ...serverErrors, ...fieldErrors };

  const upload = useMutation({
    mutationFn: (file: File) => {
      if (!initial) throw new Error('no card');
      return uploadAdminCardImage(initial.set_id, initial.card_id, file);
    },
    onSuccess: (card) => {
      setImage(card.image);
      setImageSrc(card.image_src);
      setUploadError(null);
      pushToast({ kind: 'success', message: t('cards.image.uploaded') });
      void queryClient.invalidateQueries({ queryKey: ['admin'] });
    },
    onError: (error: unknown) => {
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
        onSave(form, creating);
      }}
    >
      <Field label={t('cards.fields.set_id')} error={shown.set_id} required={creating}>
        {(control) => (
          <Input
            {...control}
            value={form.set_id}
            disabled={disabled || !creating}
            onChange={(event) => set({ set_id: event.target.value })}
          />
        )}
      </Field>
      <Field label={t('cards.fields.card_id')} error={shown.card_id} required={creating}>
        {(control) => (
          <Input
            {...control}
            value={form.card_id}
            disabled={disabled || !creating}
            onChange={(event) => set({ card_id: event.target.value })}
          />
        )}
      </Field>
      {!creating && <p className={styles.hint}>{t('cards.keyLocked')}</p>}
      <Field label={t('cards.fields.name')} error={shown.name} required={creating}>
        {(control) => (
          <Input
            {...control}
            value={form.name}
            disabled={disabled}
            onChange={(event) => set({ name: event.target.value })}
          />
        )}
      </Field>
      {TEXT_FIELDS.slice(1).map(([name, required]) => (
        <Field
          key={name}
          label={t(`cards.fields.${name}` as 'cards.fields.domain')}
          hint={
            name === 'domain'
              ? t('cards.hints.domain')
              : name === 'type'
                ? t('cards.hints.type')
                : name === 'tags'
                  ? t('cards.hints.tags')
                  : undefined
          }
          error={shown[name]}
          required={required && creating}
        >
          {(control) => (
            <Input
              {...control}
              value={form[name]}
              type={name === 'energy' || name === 'power' || name === 'might' ? 'number' : 'text'}
              disabled={disabled}
              onChange={(event) => set({ [name]: event.target.value })}
            />
          )}
        </Field>
      ))}
      <Field label={t('cards.fields.ability')} error={shown.ability}>
        {(control) => (
          <textarea
            {...control}
            rows={6}
            value={form.ability}
            disabled={disabled}
            onChange={(event) => set({ ability: event.target.value })}
          />
        )}
      </Field>
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
