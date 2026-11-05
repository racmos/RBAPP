import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';
import { deckExportHref } from '@/api/endpoints';
import { ApiError } from '@/api/errors';
import type { GameMode } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { Field } from '@/components/ui/Field';
import { Icon } from '@/components/ui/Icon';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { Select } from '@/components/ui/Select';
import { pushToast } from '@/components/ui/toastStore';
import { translateError } from '@/i18n';
import {
  useDeleteDeck,
  usePatchDeck,
  useSaveVersion,
  useShareDeck,
  useUnshareDeck,
} from './queries';
import type { DeckEditor } from './useDeckEditor';
import styles from './DeckView.module.css';

type Open = null | 'settings' | 'version' | 'share' | 'delete';

const nameTaken = (error: unknown) => error instanceof ApiError && error.code === 'already_exists';

/** Name and mode (`PATCH /decks/:id`); only what changed is sent. */
function SettingsForm({ editor, onClose }: { editor: DeckEditor; onClose: () => void }) {
  const { t, i18n } = useTranslation('decks');
  const { deck, setServer, rules } = editor;
  const patch = usePatchDeck(deck.id);
  const [name, setName] = useState(deck.name);
  const [mode, setMode] = useState<GameMode>(deck.mode);
  const [error, setError] = useState<string | null>(null);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return setError(t('settings.nameRequired'));
    const body = {
      ...(trimmed !== deck.name ? { name: trimmed } : {}),
      ...(mode !== deck.mode ? { mode } : {}),
    };
    if (Object.keys(body).length === 0) return onClose();
    patch.mutate(body, {
      onSuccess: (result) => {
        setServer(result);
        pushToast({ kind: 'success', message: t('settings.saved') });
        onClose();
      },
      onError: (failure) =>
        setError(nameTaken(failure) ? t('settings.nameTaken') : translateError(failure, i18n)),
    });
  };
  return (
    <form className={styles.form} onSubmit={submit} noValidate>
      <Field label={t('settings.name')} error={error}>
        {(control) => (
          <Input
            {...control}
            value={name}
            maxLength={80}
            onChange={(e) => setName(e.target.value)}
          />
        )}
      </Field>
      <Field label={t('settings.mode')}>
        {(control) => (
          <Select {...control} value={mode} onChange={(e) => setMode(e.target.value as GameMode)}>
            {(rules?.modes ?? [deck.mode]).map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </Select>
        )}
      </Field>
      <Button type="submit" pending={patch.isPending}>
        {t('settings.save')}
      </Button>
    </form>
  );
}

/** A copy of the current content as a new version (`POST /decks/:id/versions`). */
function VersionForm({ editor, onClose }: { editor: DeckEditor; onClose: () => void }) {
  const { t, i18n } = useTranslation('decks');
  const { deck, setServer } = editor;
  const saveVersion = useSaveVersion(deck.id);
  const [note, setNote] = useState('');
  const [error, setError] = useState<string | null>(null);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    saveVersion.mutate(note.trim() || undefined, {
      onSuccess: (version) => {
        setServer({ ...deck, current_seq: version.seq });
        pushToast({ kind: 'success', message: t('versionForm.saved', { seq: version.seq }) });
        onClose();
      },
      onError: (failure) => setError(translateError(failure, i18n)),
    });
  };
  return (
    <form className={styles.form} onSubmit={submit} noValidate>
      <Field label={t('versionForm.note')} hint={t('versionForm.noteHint')} error={error}>
        {(control) => (
          <Input
            {...control}
            value={note}
            maxLength={200}
            onChange={(e) => setNote(e.target.value)}
          />
        )}
      </Field>
      <Button type="submit" pending={saveVersion.isPending}>
        {t('versionForm.save')}
      </Button>
    </form>
  );
}

/** The read-only link (F5-g): create, copy, revoke. The public page itself is F5-m. */
function SharePanel({ editor }: { editor: DeckEditor }) {
  const { t, i18n } = useTranslation('decks');
  const { deck, setServer, offline } = editor;
  const share = useShareDeck(deck.id);
  const unshare = useUnshareDeck(deck.id);
  const onError = (failure: unknown) =>
    pushToast({ kind: 'error', message: translateError(failure, i18n) });
  const copy = async (url: string) => {
    try {
      await navigator.clipboard.writeText(url);
      pushToast({ kind: 'success', message: t('share.copied') });
    } catch {
      pushToast({ kind: 'error', message: t('share.copyFailed') });
    }
  };
  return (
    <div className={styles.form}>
      <p className={styles.muted}>{t('share.body')}</p>
      {deck.share ? (
        <>
          <Field label={t('share.url')}>
            {(control) => (
              <Input
                {...control}
                readOnly
                value={deck.share?.url ?? ''}
                onFocus={(e) => e.target.select()}
              />
            )}
          </Field>
          <div className={styles.actionsRow}>
            <Button onClick={() => void copy(deck.share?.url ?? '')}>
              <Icon name="copy" size={16} />
              {t('share.copy')}
            </Button>
            <Button
              variant="danger"
              disabled={offline}
              pending={unshare.isPending}
              onClick={() =>
                unshare.mutate(undefined, {
                  onSuccess: () => {
                    setServer({ ...deck, share: null });
                    pushToast({ kind: 'success', message: t('share.stopped') });
                  },
                  onError,
                })
              }
            >
              {t('share.stop')}
            </Button>
          </div>
        </>
      ) : (
        <>
          <p>{t('share.none')}</p>
          <Button
            disabled={offline}
            pending={share.isPending}
            onClick={() =>
              share.mutate(undefined, {
                onSuccess: (result) => setServer({ ...deck, share: result }),
                onError,
              })
            }
          >
            <Icon name="link" size={16} />
            {t('share.create')}
          </Button>
        </>
      )}
    </div>
  );
}

/** Rename / mode, save as version, share, export and delete (F5-h stage 2). */
export function DeckActions({ editor }: { editor: DeckEditor }) {
  const { t, i18n } = useTranslation('decks');
  const { t: tCommon } = useTranslation('common');
  const navigate = useNavigate();
  const { deck, offline, status } = editor;
  const [open, setOpen] = useState<Open>(null);
  const remove = useDeleteDeck(deck.id);
  const close = () => setOpen(null);
  const versionWait = status !== 'saved' ? t('actions.versionWait') : null;

  return (
    <div className={styles.actionsRow} role="group" aria-label={t('actions.label')}>
      <Button variant="ghost" size="sm" disabled={offline} onClick={() => setOpen('settings')}>
        <Icon name="edit" size={16} />
        {t('actions.settings')}
      </Button>
      <Button
        variant="ghost"
        size="sm"
        disabled={offline || versionWait !== null}
        title={versionWait ?? undefined}
        onClick={() => setOpen('version')}
      >
        {t('actions.version')}
      </Button>
      <Button variant="ghost" size="sm" disabled={offline} onClick={() => setOpen('share')}>
        <Icon name="link" size={16} />
        {t('actions.share')}
      </Button>
      <a className={styles.exportLink} href={deckExportHref(deck.id)} download>
        <Icon name="export" size={16} />
        {t('actions.export')}
      </a>
      <Button variant="ghost" size="sm" disabled={offline} onClick={() => setOpen('delete')}>
        <Icon name="trash" size={16} />
        {t('actions.delete')}
      </Button>

      <Modal open={open === 'settings'} onClose={close} title={t('settings.title')}>
        <SettingsForm editor={editor} onClose={close} />
      </Modal>
      <Modal open={open === 'version'} onClose={close} title={t('versionForm.title')}>
        <VersionForm editor={editor} onClose={close} />
      </Modal>
      <Modal open={open === 'share'} onClose={close} title={t('share.title')}>
        <SharePanel editor={editor} />
      </Modal>
      <ConfirmDialog
        open={open === 'delete'}
        title={t('remove.title', { name: deck.name })}
        message={t('remove.body')}
        confirmLabel={t('remove.confirm')}
        cancelLabel={tCommon('actions.cancel')}
        danger
        onCancel={close}
        onConfirm={() =>
          remove.mutate(undefined, {
            onSuccess: () => {
              close();
              pushToast({ kind: 'success', message: t('remove.done') });
              void navigate('/decks');
            },
            onError: (failure) => {
              close();
              pushToast({ kind: 'error', message: translateError(failure, i18n) });
            },
          })
        }
      />
    </div>
  );
}
