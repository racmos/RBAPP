import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import type { AdminSet } from '@/api/endpoints';
import { FormAlert } from './FormAlert';
import styles from './SetEditor.module.css';

export type SetForm = {
  id: string;
  name: string;
  releaseDate: string;
  declaredCount: string;
};

type SetEditorProps = {
  initial: AdminSet | null;
  fieldErrors: Record<string, string>;
  formError: string | null;
  pending: boolean;
  offline: boolean;
  offlineHint: string;
  onSave: (form: SetForm) => void;
  onCancel: () => void;
};

/** Create/edit form for a set (F13-f S5): controlled inputs, server errors per field. */
export function SetEditor({
  initial,
  fieldErrors,
  formError,
  pending,
  offline,
  offlineHint,
  onSave,
  onCancel,
}: SetEditorProps) {
  const { t } = useTranslation('admin');
  const { t: common } = useTranslation('common');
  const [form, setForm] = useState<SetForm>(() => ({
    id: initial?.id ?? '',
    name: initial?.name ?? '',
    releaseDate: initial?.release_date ?? '',
    declaredCount: initial?.declared_count?.toString() ?? '',
  }));
  const locked = (initial?.card_count ?? 0) > 0;
  const disabled = pending || offline;
  const set = (patch: Partial<SetForm>) => setForm((current) => ({ ...current, ...patch }));

  return (
    <form
      className={styles.form}
      onSubmit={(event) => {
        event.preventDefault();
        onSave(form);
      }}
    >
      <Field
        label={t('sets.fields.id')}
        hint={locked ? t('sets.idLocked') : undefined}
        error={fieldErrors.id}
        required
      >
        {(control) => (
          <Input
            {...control}
            value={form.id}
            disabled={disabled || locked}
            onChange={(event) => set({ id: event.target.value })}
          />
        )}
      </Field>
      <Field label={t('sets.fields.name')} error={fieldErrors.name} required>
        {(control) => (
          <Input
            {...control}
            value={form.name}
            disabled={disabled}
            onChange={(event) => set({ name: event.target.value })}
          />
        )}
      </Field>
      <Field label={t('sets.fields.releaseDate')} error={fieldErrors.releaseDate} required>
        {(control) => (
          <Input
            {...control}
            type="date"
            value={form.releaseDate}
            disabled={disabled}
            onChange={(event) => set({ releaseDate: event.target.value })}
          />
        )}
      </Field>
      <Field label={t('sets.fields.declaredCount')} error={fieldErrors.declaredCount}>
        {(control) => (
          <Input
            {...control}
            type="number"
            value={form.declaredCount}
            min={0}
            max={999}
            disabled={disabled}
            onChange={(event) => set({ declaredCount: event.target.value })}
          />
        )}
      </Field>
      <p className={styles.help}>{t('sets.windowHelp')}</p>
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
