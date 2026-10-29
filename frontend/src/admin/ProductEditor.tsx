import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ApiError } from '@/api/errors';
import {
  uploadAdminProductImage,
  type AdminProduct,
  type AdminProductPatch,
} from '@/api/endpoints';
import { PRODUCT_KINDS, type ProductKind } from '@/api/types';
import { fieldErrorsFromDetails } from '@/auth/formHelpers';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Icon } from '@/components/ui/Icon';
import { Select } from '@/components/ui/Select';
import { Switch } from '@/components/ui/Switch';
import { pushToast } from '@/components/ui/toastStore';
import { translateError } from '@/i18n';
import { FormAlert } from './FormAlert';
import styles from './ProductEditor.module.css';

// Sentinel values of the set select: set ids are upper-case codes, so they never collide.
const SET_AUTO = '__auto__';
const SET_NONE = '__none__';

type ProductForm = { kind: ProductKind | ''; set: string; hidden: boolean };

/** The form mirrors the locks: an unlocked kind or set shows the "automatic" option. */
function toForm(product: AdminProduct): ProductForm {
  return {
    kind: product.kind_locked ? product.kind : '',
    set: product.set_locked ? (product.set_id ?? SET_NONE) : SET_AUTO,
    hidden: product.hidden,
  };
}

/** Only what changed: `kind: null` unlocks the kind, `set_id: 'auto'` unlocks the set (F14-d S3). */
function toPatch(initial: ProductForm, form: ProductForm): AdminProductPatch {
  const patch: AdminProductPatch = {};
  if (form.kind !== initial.kind) patch.kind = form.kind || null;
  if (form.set !== initial.set) {
    patch.set_id = form.set === SET_AUTO ? 'auto' : form.set === SET_NONE ? null : form.set;
  }
  if (form.hidden !== initial.hidden) patch.hidden = form.hidden;
  return patch;
}

/** A 40 px product image, or the gift placeholder when it has none. */
export function ProductThumb({ src }: { src: string | null }) {
  return src ? (
    <img src={src} alt="" className={styles.thumb} />
  ) : (
    <span className={styles.placeholder}>
      <Icon name="gift" size={20} />
    </span>
  );
}

type ProductEditorProps = {
  product: AdminProduct;
  sets: readonly { id: string; name: string }[];
  fieldErrors: Partial<Record<'kind' | 'set_id' | 'hidden', string>>;
  formError: string | null;
  pending: boolean;
  offline: boolean;
  offlineHint: string;
  onSave: (patch: AdminProductPatch) => void;
  onCancel: () => void;
};

/** Kind, set and visibility of one product, with its image (F14-d S5). */
export function ProductEditor({
  product,
  sets,
  fieldErrors,
  formError,
  pending,
  offline,
  offlineHint,
  onSave,
  onCancel,
}: ProductEditorProps) {
  const { t, i18n } = useTranslation('admin');
  const { t: tp } = useTranslation('products');
  const { t: common } = useTranslation('common');
  const queryClient = useQueryClient();
  const [initial] = useState(() => toForm(product));
  const [form, setForm] = useState(initial);
  const [imageSrc, setImageSrc] = useState(product.image_src);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const disabled = pending || offline;
  const knownSet = product.set_id === null || sets.some((set) => set.id === product.set_id);

  const upload = useMutation({
    mutationFn: (file: File) => uploadAdminProductImage(product.id, file),
    onSuccess: (updated) => {
      setImageSrc(updated.image_src);
      setUploadError(null);
      pushToast({ kind: 'success', message: t('cards.image.uploaded') });
      void queryClient.invalidateQueries({ queryKey: ['admin'] });
    },
    onError: (error: unknown) => {
      const mapped =
        error instanceof ApiError && error.kind === 'http' && error.status === 400
          ? fieldErrorsFromDetails(error.details, i18n, ['file'] as const).file
          : undefined;
      setUploadError(mapped ?? translateError(error, i18n));
    },
  });

  const locked = <Badge tone="accent">{t('products.locked')}</Badge>;

  return (
    <form
      className={styles.form}
      onSubmit={(event) => {
        event.preventDefault();
        const patch = toPatch(initial, form);
        if (Object.keys(patch).length === 0) onCancel();
        else onSave(patch);
      }}
    >
      <Field
        label={
          <>
            {t('products.fields.kind')} {product.kind_locked && locked}
          </>
        }
        error={fieldErrors.kind}
      >
        {(control) => (
          <Select
            {...control}
            value={form.kind}
            disabled={disabled}
            onChange={(event) =>
              setForm((current) => ({ ...current, kind: event.target.value as ProductKind | '' }))
            }
          >
            <option value="">{t('products.kindAuto')}</option>
            {PRODUCT_KINDS.map((kind) => (
              <option key={kind} value={kind}>
                {tp(`kind.${kind}`)}
              </option>
            ))}
          </Select>
        )}
      </Field>
      <Field
        label={
          <>
            {t('products.fields.set')} {product.set_locked && locked}
          </>
        }
        error={fieldErrors.set_id}
      >
        {(control) => (
          <Select
            {...control}
            value={form.set}
            disabled={disabled}
            onChange={(event) => setForm((current) => ({ ...current, set: event.target.value }))}
          >
            <option value={SET_AUTO}>{t('products.setAuto')}</option>
            <option value={SET_NONE}>{t('products.noSet')}</option>
            {!knownSet && product.set_id && (
              <option value={product.set_id}>{product.set_id}</option>
            )}
            {sets.map((set) => (
              <option key={set.id} value={set.id}>
                {set.id} · {set.name}
              </option>
            ))}
          </Select>
        )}
      </Field>
      <Switch
        label={t('products.fields.hidden')}
        checked={form.hidden}
        disabled={disabled}
        onCheckedChange={(hidden) => setForm((current) => ({ ...current, hidden }))}
      />
      {fieldErrors.hidden && <FormAlert message={fieldErrors.hidden} />}
      <div className={styles.image}>
        <ProductThumb src={imageSrc} />
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
      </div>
      {formError && <FormAlert message={formError} />}
      <div className={styles.actions}>
        <Button type="submit" disabled={disabled}>
          {common('actions.save')}
        </Button>
        <Button type="button" variant="ghost" onClick={onCancel}>
          {common('actions.cancel')}
        </Button>
      </div>
      {offline && <span className="sr-only">{offlineHint}</span>}
    </form>
  );
}
