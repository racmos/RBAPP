import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { ApiError } from '@/api/errors';
import type { Wishlist } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { Sheet } from '@/components/ui/Sheet';
import { pushToast } from '@/components/ui/toastStore';
import { useWishlistError } from './errors';
import type { ListActions } from './ListsMenu';
import {
  useCreateWishlist,
  useDeleteWishlist,
  usePatchWishlist,
  useRestoreWishlist,
} from './queries';
import styles from './Wishlists.module.css';

export const NAME_MAX = 80;

type FormState = { mode: 'new' } | { mode: 'rename'; list: Wishlist } | null;

/** A new list, or a new name for one (1-80 characters, unique per user ignoring case). */
function ListFormSheet({
  form,
  offline,
  onClose,
  onCreated,
}: {
  form: Exclude<FormState, null>;
  offline: boolean;
  onClose: () => void;
  onCreated: (list: Wishlist) => void;
}) {
  const { t } = useTranslation('wishlists');
  const { t: tCommon } = useTranslation('common');
  const message = useWishlistError();
  const create = useCreateWishlist();
  const patch = usePatchWishlist();
  const [name, setName] = useState(form.mode === 'rename' ? form.list.name : '');
  const [nameError, setNameError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const fromApi = (error: unknown) => {
    if (error instanceof ApiError && error.code === 'already_exists') {
      setNameError(t('form.nameTaken'));
      return;
    }
    const detail =
      error instanceof ApiError ? error.details.find((item) => item.field === 'name') : undefined;
    if (detail) setNameError(message(error));
    else setFormError(message(error));
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const value = name.trim();
    setFormError(null);
    if (!value) {
      setNameError(t('form.nameRequired'));
      return;
    }
    setNameError(null);
    if (form.mode === 'new') {
      create
        .mutateAsync(value)
        .then((created) => {
          pushToast({ kind: 'success', message: t('created', { name: created.name }) });
          onCreated(created);
        })
        .catch(fromApi);
      return;
    }
    if (value === form.list.name) return onClose();
    patch
      .mutateAsync({ id: form.list.id, body: { name: value } })
      .then(() => {
        pushToast({ kind: 'success', message: t('renamed') });
        onClose();
      })
      .catch(fromApi);
  };

  const title =
    form.mode === 'new' ? t('form.newTitle') : t('form.renameTitle', { name: form.list.name });
  return (
    <Sheet open onClose={onClose} title={title}>
      <form className={styles.form} onSubmit={submit} noValidate>
        {offline && <p className={styles.note}>{tCommon('offline.editDisabled')}</p>}
        <Field label={t('form.name')} hint={t('form.nameHint')} error={nameError}>
          {(control) => (
            <Input
              {...control}
              value={name}
              maxLength={NAME_MAX}
              autoComplete="off"
              disabled={offline}
              data-autofocus
              onChange={(event) => setName(event.target.value)}
            />
          )}
        </Field>
        {formError && (
          <p role="alert" className={styles.alert}>
            {formError}
          </p>
        )}
        <Button
          type="submit"
          block
          disabled={offline}
          pending={create.isPending || patch.isPending}
        >
          {form.mode === 'new' ? t('form.create') : t('form.save')}
        </Button>
      </form>
    </Sheet>
  );
}

/**
 * The list actions of both layouts (F3-j): the new / rename sheet, and delete after a
 * confirmation that says how many cards go, with an Undo that rebuilds the list.
 */
export function useListActions({
  offline,
  onCreated,
}: {
  offline: boolean;
  onCreated: (list: Wishlist) => void;
}) {
  const { t } = useTranslation('wishlists');
  const { t: tCommon } = useTranslation('common');
  const message = useWishlistError();
  const remove = useDeleteWishlist();
  const restore = useRestoreWishlist();
  const [form, setForm] = useState<FormState>(null);
  const [deleting, setDeleting] = useState<Wishlist | null>(null);

  const actions: ListActions = {
    onNew: () => setForm({ mode: 'new' }),
    onRename: (list) => setForm({ mode: 'rename', list }),
    onDelete: (list) => setDeleting(list),
  };

  const confirmDelete = () => {
    const target = deleting;
    setDeleting(null);
    if (!target) return;
    remove
      .mutateAsync(target.id)
      .then((gone) =>
        pushToast({
          kind: 'success',
          message: t('deleted', { name: target.name }),
          duration: 10000,
          action: {
            label: t('undo'),
            onAction: () =>
              void restore
                .mutateAsync(gone)
                .then(() =>
                  pushToast({ kind: 'success', message: t('restored', { name: target.name }) }),
                )
                .catch((error) => pushToast({ kind: 'error', message: message(error) })),
          },
        }),
      )
      .catch((error) => pushToast({ kind: 'error', message: message(error) }));
  };

  const sheets = (
    <>
      {form && (
        <ListFormSheet
          key={form.mode === 'new' ? 'new' : form.list.id}
          form={form}
          offline={offline}
          onClose={() => setForm(null)}
          onCreated={(list) => {
            setForm(null);
            onCreated(list);
          }}
        />
      )}
      {deleting && (
        <ConfirmDialog
          open
          title={t('confirmDelete.title', { name: deleting.name })}
          message={t('confirmDelete.body', { count: deleting.line_count })}
          confirmLabel={tCommon('actions.delete')}
          cancelLabel={tCommon('actions.cancel')}
          danger
          onConfirm={confirmDelete}
          onCancel={() => setDeleting(null)}
        />
      )}
    </>
  );
  return { actions, sheets };
}
