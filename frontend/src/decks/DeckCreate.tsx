import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';
import { ApiError } from '@/api/errors';
import type { DeckImportPreview, DeckImportWarning, GameMode } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { Select } from '@/components/ui/Select';
import { pushToast } from '@/components/ui/toastStore';
import { translateError } from '@/i18n';
import { hardLimitMessage } from './issues';
import { useCreateDeck, useDeckRules, useImportDeck, useImportPreview } from './queries';
import styles from './DecksPage.module.css';

type Props = { open: boolean; onClose: () => void };
type Loose = (key: string, options?: Record<string, unknown>) => string;

const nameTaken = (error: unknown) => error instanceof ApiError && error.code === 'already_exists';

function ModeField({ mode, onChange }: { mode: GameMode; onChange: (mode: GameMode) => void }) {
  const { t } = useTranslation('decks');
  const { rules } = useDeckRules();
  return (
    <Field label={t('settings.mode')}>
      {(control) => (
        <Select {...control} value={mode} onChange={(e) => onChange(e.target.value as GameMode)}>
          {(rules?.modes ?? ['1v1', '2v2']).map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </Select>
      )}
    </Field>
  );
}

/** `POST /decks` then the new deck's screen. */
export function NewDeckModal({ open, onClose }: Props) {
  const { t, i18n } = useTranslation('decks');
  const navigate = useNavigate();
  const create = useCreateDeck();
  const [name, setName] = useState('');
  const [mode, setMode] = useState<GameMode>('1v1');
  const [error, setError] = useState<string | null>(null);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return setError(t('settings.nameRequired'));
    create.mutate(
      { name: trimmed, mode },
      {
        onSuccess: (deck) => {
          pushToast({ kind: 'success', message: t('create.done') });
          void navigate(`/decks/${deck.id}`);
        },
        onError: (failure) =>
          setError(nameTaken(failure) ? t('settings.nameTaken') : translateError(failure, i18n)),
      },
    );
  };
  return (
    <Modal open={open} onClose={onClose} title={t('create.title')}>
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
        <ModeField mode={mode} onChange={setMode} />
        <Button type="submit" pending={create.isPending}>
          {t('create.submit')}
        </Button>
      </form>
    </Modal>
  );
}

/** One import warning in words (F5-e reason codes). */
export function warningText(t: Loose, warning: DeckImportWarning): string {
  const { reason_code: code, params } = warning;
  let reason: string;
  if (code === 'hard_limit') {
    reason = hardLimitMessage(t as never, params as { rule: string; max: number; name?: string });
  } else {
    const zone = typeof params.zone === 'string' ? t(`zoneIn.${params.zone}`) : undefined;
    const to = typeof params.to === 'string' ? t(`zoneIn.${params.to}`) : undefined;
    reason = t(`importReason.${code}`, { ...params, zone, to });
    if (!reason) reason = t('importReason.unknown', { code });
  }
  return warning.line === null
    ? t('importForm.warningNoLine', { reason })
    : t('importForm.warning', { line: warning.line, text: warning.text, reason });
}

function PreviewBlock({ preview }: { preview: DeckImportPreview }) {
  const { t } = useTranslation('decks');
  const tl = t as unknown as Loose;
  const { counts, deck_preview: deck, warnings } = preview;
  return (
    <section className={styles.preview} aria-label={t('importForm.preview')}>
      <p>{t('importForm.summary', counts)}</p>
      <p>{t('importForm.sections', deck.counts)}</p>
      {warnings.length === 0 ? (
        <p className={styles.muted}>{t('importForm.noWarnings')}</p>
      ) : (
        <ul aria-label={t('importForm.warnings')}>
          {warnings.map((warning, index) => (
            <li key={index}>{warningText(tl, warning)}</li>
          ))}
        </ul>
      )}
    </section>
  );
}

/** Paste a deck text, preview it (`POST /decks/import/preview`), then import it. */
export function ImportDeckModal({ open, onClose }: Props) {
  const { t, i18n } = useTranslation('decks');
  const navigate = useNavigate();
  const previewMutation = useImportPreview();
  const importMutation = useImportDeck();
  const [text, setText] = useState('');
  const [name, setName] = useState('');
  const [mode, setMode] = useState<GameMode>('1v1');
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<DeckImportPreview | null>(null);
  const [previewed, setPreviewed] = useState('');

  const runPreview = () => {
    if (!text.trim()) return setError(t('importForm.textRequired'));
    setError(null);
    previewMutation.mutate(text, {
      onSuccess: (result) => {
        setPreview(result);
        setPreviewed(text);
      },
      onError: (failure) => setError(translateError(failure, i18n)),
    });
  };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!preview || previewed !== text) return runPreview();
    importMutation.mutate(
      { text, mode, ...(name.trim() ? { name: name.trim() } : {}) },
      {
        onSuccess: (deck) => {
          pushToast({
            kind: 'success',
            message:
              deck.warnings.length > 0
                ? t('importForm.doneWarnings', { count: deck.warnings.length })
                : t('importForm.done'),
          });
          void navigate(`/decks/${deck.id}`);
        },
        onError: (failure) => setError(translateError(failure, i18n)),
      },
    );
  };
  const ready = preview !== null && previewed === text;
  return (
    <Modal open={open} onClose={onClose} title={t('importForm.title')} size="lg">
      <form className={styles.form} onSubmit={submit} noValidate>
        <Field label={t('importForm.text')} hint={t('importForm.textHint')} error={error}>
          {(control) => (
            <textarea
              {...control}
              className={styles.textarea}
              rows={10}
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          )}
        </Field>
        <Field label={t('importForm.name')}>
          {(control) => (
            <Input
              {...control}
              value={name}
              maxLength={80}
              onChange={(e) => setName(e.target.value)}
            />
          )}
        </Field>
        <ModeField mode={mode} onChange={setMode} />
        {ready && <PreviewBlock preview={preview} />}
        <div className={styles.formActions}>
          <Button variant="ghost" pending={previewMutation.isPending} onClick={runPreview}>
            {t('importForm.preview')}
          </Button>
          <Button type="submit" disabled={!ready} pending={importMutation.isPending}>
            {t('importForm.submit')}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
