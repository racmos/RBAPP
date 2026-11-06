import { useId, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type {
  DeckDetail,
  DeckDiff,
  DeckDiffEntry,
  DeckVersionDetail,
  DeckVersionItem,
  DeckZoneName,
} from '@/api/types';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Icon } from '@/components/ui/Icon';
import { Modal } from '@/components/ui/Modal';
import { Skeleton } from '@/components/ui/Skeleton';
import { pushToast } from '@/components/ui/toastStore';
import { translateError } from '@/i18n';
import { formatDateTime } from '@/lib/format';
import { cardLabel, refKey } from './labels';
import { useDeckDiff, useDeckVersions, useRestoreVersion } from './queries';
import type { DeckEditor } from './useDeckEditor';
import styles from './DeckView.module.css';

const ZONES: DeckZoneName[] = [
  'legend',
  'champion',
  'main',
  'runes',
  'battlefields',
  'sideboard',
  'workbench',
];

/** The deck after a restore: the head as it is, the body and current seq of the new version. */
function restoredDeck(deck: DeckDetail, version: DeckVersionDetail): DeckDetail {
  return {
    ...deck,
    current_seq: version.seq,
    updated_at: version.created_at,
    content: version.content,
    cards: version.cards,
    unknown_cards: version.unknown_cards,
    domains: version.domains,
    counts: version.counts,
    value: version.value,
    value_unpriced: version.value_unpriced,
    legality: version.legality,
  };
}

/** `+1 Rakelstake`, `−1 Hush`, `Discipline 2 → 3`, grouped by zone in deck order. */
function DiffZones({ diff }: { diff: DeckDiff }) {
  const { t } = useTranslation('decks');
  const id = useId();
  const name = (entry: DeckDiffEntry) => {
    const card = diff.cards[refKey(entry)];
    return card ? cardLabel(card) : refKey(entry);
  };
  const zones = ZONES.filter((zone) => {
    const changes = diff.zones[zone];
    return changes && changes.added.length + changes.removed.length + changes.changed.length > 0;
  });
  if (zones.length === 0) return <p className={styles.muted}>{t('versions.none')}</p>;
  return (
    <>
      {zones.map((zone) => {
        const { added, removed, changed } = diff.zones[zone];
        return (
          <section key={zone} className={styles.diffZone} aria-labelledby={`${id}-${zone}`}>
            <h3 id={`${id}-${zone}`}>{t(`section.${zone}`)}</h3>
            <ul>
              {added.map((entry) => (
                <li key={`a-${refKey(entry)}`} data-kind="added">
                  {t('versions.added', { qty: entry.after, name: name(entry) })}
                </li>
              ))}
              {removed.map((entry) => (
                <li key={`r-${refKey(entry)}`} data-kind="removed">
                  {t('versions.removed', { qty: entry.before, name: name(entry) })}
                </li>
              ))}
              {changed.map((entry) => (
                <li key={`c-${refKey(entry)}`} data-kind="changed">
                  {t('versions.changed', {
                    name: name(entry),
                    before: entry.before,
                    after: entry.after,
                  })}
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </>
  );
}

/** The diff against the previous (older) version, loaded when the row opens. */
function VersionDiff({ deckId, from, to }: { deckId: number; from: number; to: number }) {
  const { t } = useTranslation('decks');
  const diff = useDeckDiff(deckId, from, to);
  if (diff.isPending) return <Skeleton label={t('versions.loadingChanges')} lines={2} />;
  if (!diff.data) {
    return <ErrorState message={t('versions.changesError')} onRetry={() => void diff.refetch()} />;
  }
  return <DiffZones diff={diff.data} />;
}

type RowProps = {
  deckId: number;
  item: DeckVersionItem;
  /** The next older version; null for the first one. */
  previous: DeckVersionItem | null;
  /** Why a restore cannot start now (null when it can). */
  wait: string | null;
  disabled: boolean;
  pending: boolean;
  onRestore: (seq: number) => void;
};

function VersionRow({ deckId, item, previous, wait, disabled, pending, onRestore }: RowProps) {
  const { t } = useTranslation('decks');
  const id = useId();
  const [open, setOpen] = useState(false);
  const changes = t('versions.changes', { seq: item.seq });
  return (
    <li className={styles.versionRow} aria-labelledby={`${id}-title`}>
      <div className={styles.versionHead}>
        <button
          type="button"
          className={styles.versionToggle}
          aria-expanded={open}
          aria-controls={open ? `${id}-changes` : undefined}
          aria-label={changes}
          onClick={() => setOpen((value) => !value)}
        >
          <Icon name="arrow" size={14} className={styles.versionChevron} />
          <span id={`${id}-title`}>{t('version', { seq: item.seq })}</span>
        </button>
        {item.is_current && <Badge tone="accent">{t('versions.current')}</Badge>}
        <span className={styles.muted}>{formatDateTime(item.created_at)}</span>
        {!item.is_current && (
          <Button
            variant="ghost"
            size="sm"
            className={styles.versionRestore}
            aria-label={t('versions.restoreLabel', { seq: item.seq })}
            title={wait ?? undefined}
            disabled={disabled || wait !== null}
            pending={pending}
            onClick={() => onRestore(item.seq)}
          >
            {t('versions.restore')}
          </Button>
        )}
      </div>
      {item.note && <p className={styles.versionNote}>{item.note}</p>}
      {open && (
        <div id={`${id}-changes`} role="region" aria-label={changes} className={styles.diff}>
          {previous ? (
            <VersionDiff deckId={deckId} from={previous.seq} to={item.seq} />
          ) : (
            <p className={styles.muted}>{t('versions.first')}</p>
          )}
        </div>
      )}
    </li>
  );
}

function VersionList(
  props: Omit<RowProps, 'item' | 'previous' | 'pending'> & {
    restoring: number | null;
  },
) {
  const { t } = useTranslation('decks');
  const { deckId, restoring, ...rest } = props;
  const versions = useDeckVersions(deckId);
  if (versions.isPending) return <Skeleton label={t('versions.loading')} lines={4} />;
  if (!versions.data) {
    return <ErrorState message={t('versions.error')} onRetry={() => void versions.refetch()} />;
  }
  const items = versions.data.items;
  if (items.length === 0) return <EmptyState title={t('versions.empty')} />;
  return (
    <ol className={styles.versionList} aria-label={t('versions.list')}>
      {items.map((item, index) => (
        <VersionRow
          key={item.seq}
          deckId={deckId}
          item={item}
          previous={items[index + 1] ?? null}
          pending={restoring === item.seq}
          {...rest}
        />
      ))}
    </ol>
  );
}

/**
 * The versions of the deck (F5-i step 6, image 6): newest first, each one opens to what changed
 * since the previous one, and an older one can be restored. A restore adds a new current version
 * on the server and the open editor takes it as saved (`editor.reset`); it waits until every
 * change is saved, so the autosave can neither lose an edit nor overwrite the restored deck.
 */
export function DeckVersions({
  editor,
  open,
  onClose,
}: {
  editor: DeckEditor;
  open: boolean;
  onClose: () => void;
}) {
  const { t, i18n } = useTranslation('decks');
  const { t: tCommon } = useTranslation('common');
  const { deck, offline, status } = editor;
  const restore = useRestoreVersion(deck.id);
  const [confirming, setConfirming] = useState<number | null>(null);
  const wait = status !== 'saved' ? t('actions.versionWait') : null;

  const run = (seq: number) => {
    setConfirming(null);
    restore.mutate(seq, {
      onSuccess: (version) => {
        editor.reset(restoredDeck(deck, version));
        pushToast({
          kind: 'success',
          message: t('versions.restored', { seq, current: version.seq }),
        });
        onClose();
      },
      onError: (failure) => pushToast({ kind: 'error', message: translateError(failure, i18n) }),
    });
  };

  return (
    <>
      <Modal open={open} onClose={onClose} title={t('versions.title')} size="lg">
        <VersionList
          deckId={deck.id}
          wait={wait}
          disabled={offline || restore.isPending}
          restoring={restore.isPending ? (restore.variables ?? null) : null}
          onRestore={setConfirming}
        />
      </Modal>
      <ConfirmDialog
        open={confirming !== null}
        title={t('versions.confirmTitle', { seq: confirming ?? 0 })}
        message={t('versions.confirmBody')}
        confirmLabel={t('versions.restore')}
        cancelLabel={tCommon('actions.cancel')}
        onCancel={() => setConfirming(null)}
        onConfirm={() => confirming !== null && run(confirming)}
      />
    </>
  );
}
