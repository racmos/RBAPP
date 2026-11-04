import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import { ApiError } from '@/api/errors';
import type { LocationBump, StorageLocation } from '@/api/types';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { Field } from '@/components/ui/Field';
import { Icon } from '@/components/ui/Icon';
import { Input } from '@/components/ui/Input';
import { Sheet } from '@/components/ui/Sheet';
import { Switch } from '@/components/ui/Switch';
import { pushToast } from '@/components/ui/toastStore';
import { translateDetail, translateError } from '@/i18n';
import {
  CODE_MAX,
  DESCRIPTION_MAX,
  cardsHref,
  cleanDescription,
  codeProblem,
  useLocationCounts,
} from './labels';
import {
  useBumpCode,
  useCreateLocation,
  useDeleteLocation,
  usePatchLocation,
  useSuggestedCode,
} from './queries';
import styles from './LocationSheets.module.css';

const BUMPS: LocationBump[] = ['block', 'row', 'pack'];

/** "Locked" and "Deck": the text says it, colour is never the only signal. */
export function LocationBadges({ location }: { location: StorageLocation }) {
  const { t } = useTranslation('locations');
  if (!location.locked && location.deck_id === null) return null;
  return (
    <span className={styles.badges}>
      {location.locked && (
        <Badge tone="warning">
          <Icon name="lock" size={12} /> {t('locked')}
        </Badge>
      )}
      {location.deck_id !== null && <Badge tone="accent">{t('deck')}</Badge>}
    </span>
  );
}

/**
 * The errors of a create or an update: a repeated code and a bad code belong to the code field,
 * anything else to the whole form.
 */
function useFormErrors() {
  const { t, i18n } = useTranslation('locations');
  const [codeError, setCodeError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const fromApi = (error: unknown) => {
    if (error instanceof ApiError && error.code === 'already_exists') {
      setCodeError(t('form.codeTaken'));
      return;
    }
    const codeDetail =
      error instanceof ApiError ? error.details.find((detail) => detail.field === 'code') : null;
    if (codeDetail) setCodeError(translateDetail(codeDetail, i18n));
    else setFormError(translateError(error, i18n));
  };
  /** Checks the code before it is sent; true when it can be. */
  const checkCode = (code: string) => {
    const problem = codeProblem(code);
    setCodeError(problem ? t(`form.${problem}`) : null);
    setFormError(null);
    return problem === null;
  };
  return { codeError, setCodeError, formError, setFormError, fromApi, checkCode };
}

/** A new location: the suggested code, the block, row and pack buttons, a description (F16-R1a). */
export function NewLocationSheet({ offline, onClose }: { offline: boolean; onClose: () => void }) {
  const { t } = useTranslation('locations');
  const { t: tCommon } = useTranslation('common');
  const suggested = useSuggestedCode();
  const bump = useBumpCode();
  const create = useCreateLocation();
  const errors = useFormErrors();
  // null until the user types or asks for a suggestion: the code follows the server's suggestion
  const [typed, setTyped] = useState<string | null>(null);
  const [description, setDescription] = useState('');
  const [noPattern, setNoPattern] = useState(false);
  const code = typed ?? suggested.data?.code ?? '';

  const suggest = (part: LocationBump) => {
    const after = code.trim();
    bump.mutate(
      { bump: part, after: after || undefined },
      {
        onSuccess: (result) => {
          setNoPattern(result.code === null);
          if (result.code !== null) setTyped(result.code);
        },
        onError: errors.fromApi,
      },
    );
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const value = code.trim();
    if (!errors.checkCode(value)) return;
    create.mutate(
      { code: value, description: cleanDescription(description) },
      {
        onSuccess: () => {
          pushToast({ kind: 'success', message: t('created') });
          onClose();
        },
        onError: errors.fromApi,
      },
    );
  };

  return (
    <Sheet open onClose={onClose} title={t('new')}>
      <form className={styles.body} onSubmit={submit} noValidate>
        {offline && <p className={styles.note}>{tCommon('offline.editDisabled')}</p>}
        <Field label={t('form.code')} hint={t('form.codeHint')} error={errors.codeError}>
          {(control) => (
            <Input
              {...control}
              value={code}
              maxLength={CODE_MAX}
              autoComplete="off"
              spellCheck={false}
              disabled={offline}
              onChange={(event) => {
                setTyped(event.target.value);
                setNoPattern(false);
              }}
            />
          )}
        </Field>
        <div role="group" aria-label={t('form.suggest')} className={styles.bumps}>
          {BUMPS.map((part) => (
            <Button
              key={part}
              variant="ghost"
              size="sm"
              disabled={offline || bump.isPending}
              onClick={() => suggest(part)}
            >
              {t(`form.bump.${part}`)}
            </Button>
          ))}
        </div>
        {noPattern && <p className={styles.note}>{t('form.noPattern')}</p>}
        <Field label={t('form.description')}>
          {(control) => (
            <Input
              {...control}
              value={description}
              maxLength={DESCRIPTION_MAX}
              disabled={offline}
              onChange={(event) => setDescription(event.target.value)}
            />
          )}
        </Field>
        {errors.formError && (
          <p role="alert" className={styles.alert}>
            {errors.formError}
          </p>
        )}
        <Button type="submit" block disabled={offline} pending={create.isPending}>
          {t('form.create')}
        </Button>
      </form>
    </Sheet>
  );
}

/**
 * One location: rename, describe, lock, see its cards, delete (F16-R1, R3). A locked location can
 * be renamed; a locked deck location cannot be deleted, and the server says why (409).
 */
export function LocationSheet({
  location,
  offline,
  onClose,
}: {
  location: StorageLocation;
  offline: boolean;
  onClose: () => void;
}) {
  const { t } = useTranslation('locations');
  const { t: tCommon } = useTranslation('common');
  const counts = useLocationCounts();
  const patch = usePatchLocation();
  const remove = useDeleteLocation();
  const errors = useFormErrors();
  const [code, setCode] = useState(location.code);
  const [description, setDescription] = useState(location.description ?? '');
  const [confirming, setConfirming] = useState(false);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const value = code.trim();
    if (!errors.checkCode(value)) return;
    const next = cleanDescription(description);
    const body = {
      ...(value !== location.code ? { code: value } : {}),
      ...(next !== location.description ? { description: next } : {}),
    };
    if (Object.keys(body).length === 0) return;
    patch.mutate(
      { id: location.id, body },
      {
        onSuccess: () => pushToast({ kind: 'success', message: t('saved') }),
        onError: errors.fromApi,
      },
    );
  };

  const lock = (locked: boolean) => {
    errors.setFormError(null);
    patch.mutate({ id: location.id, body: { locked } }, { onError: errors.fromApi });
  };

  // A promise, not `mutate` callbacks: they would be lost if the sheet closes meanwhile.
  const confirmDelete = () => {
    setConfirming(false);
    errors.setFormError(null);
    remove
      .mutateAsync(location.id)
      .then(() => {
        pushToast({ kind: 'success', message: t('deleted') });
        onClose();
      })
      .catch(errors.fromApi);
  };

  return (
    <>
      <Sheet open onClose={onClose} title={t('editTitle', { code: location.code })}>
        <div className={styles.body}>
          {offline && <p className={styles.note}>{tCommon('offline.editDisabled')}</p>}
          <p className={styles.summary}>
            <span>{counts(location)}</span>
            <LocationBadges location={location} />
          </p>
          <form className={styles.form} onSubmit={submit} noValidate>
            <Field label={t('form.code')} hint={t('form.codeHint')} error={errors.codeError}>
              {(control) => (
                <Input
                  {...control}
                  value={code}
                  maxLength={CODE_MAX}
                  autoComplete="off"
                  spellCheck={false}
                  disabled={offline}
                  onChange={(event) => setCode(event.target.value)}
                />
              )}
            </Field>
            <Field label={t('form.description')}>
              {(control) => (
                <Input
                  {...control}
                  value={description}
                  maxLength={DESCRIPTION_MAX}
                  disabled={offline}
                  onChange={(event) => setDescription(event.target.value)}
                />
              )}
            </Field>
            <Button type="submit" disabled={offline} pending={patch.isPending}>
              {t('form.save')}
            </Button>
          </form>
          <Switch
            label={t('lock')}
            checked={location.locked}
            disabled={offline || patch.isPending}
            onCheckedChange={lock}
          />
          <p className={styles.note}>{t('lockHint')}</p>
          {errors.formError && (
            <p role="alert" className={styles.alert}>
              {errors.formError}
            </p>
          )}
          <div className={styles.actions}>
            <Link className={styles.link} to={cardsHref(location.code)}>
              {t('viewCards')}
            </Link>
            <Button
              variant="danger"
              size="sm"
              disabled={offline}
              pending={remove.isPending}
              onClick={() => setConfirming(true)}
            >
              {t('delete')}
            </Button>
          </div>
        </div>
      </Sheet>
      {/* Outside the sheet: a nested dialog's close event would close the sheet too. */}
      <ConfirmLocationDelete
        location={location}
        open={confirming}
        onConfirm={confirmDelete}
        onCancel={() => setConfirming(false)}
      />
    </>
  );
}

/** "Delete B001…? Its 5 copies go back to unassigned." */
export function ConfirmLocationDelete({
  location,
  open,
  onConfirm,
  onCancel,
}: {
  location: StorageLocation;
  open: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const { t } = useTranslation('locations');
  const { t: tCommon } = useTranslation('common');
  return (
    <ConfirmDialog
      open={open}
      title={t('confirmDelete.title', { code: location.code })}
      message={t('confirmDelete.body', { count: location.copies })}
      confirmLabel={tCommon('actions.delete')}
      cancelLabel={tCommon('actions.cancel')}
      danger
      onConfirm={onConfirm}
      onCancel={onCancel}
    />
  );
}
