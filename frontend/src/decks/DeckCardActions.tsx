import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';
import type { DeckListItem } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { Field } from '@/components/ui/Field';
import { Icon } from '@/components/ui/Icon';
import { Input } from '@/components/ui/Input';
import { Popover } from '@/components/ui/Popover';
import { pushToast } from '@/components/ui/toastStore';
import { translateError } from '@/i18n';
import {
  useDeleteDeck,
  useDuplicateDeck,
  useExportDeckText,
  useShareDeck,
  useUnshareDeck,
} from './queries';
import styles from './DecksPage.module.css';

/**
 * The actions of one deck card in a small panel: duplicate, copy the text (never a download,
 * owner 2026-11-06), the share link and delete. None of them leaves the list; the duplicate's toast offers to open it.
 */
export function DeckCardActions({ deck, offline }: { deck: DeckListItem; offline: boolean }) {
  const { t, i18n } = useTranslation('decks');
  const { t: tCommon } = useTranslation('common');
  const navigate = useNavigate();
  const duplicate = useDuplicateDeck();
  const exportText = useExportDeckText();
  const share = useShareDeck(deck.id);
  const unshare = useUnshareDeck(deck.id);
  const remove = useDeleteDeck(deck.id);
  const [confirming, setConfirming] = useState(false);
  const onError = (failure: unknown) =>
    pushToast({ kind: 'error', message: translateError(failure, i18n) });

  const copy = async (text: string, done: string, failed: string) => {
    try {
      await navigator.clipboard.writeText(text);
      pushToast({ kind: 'success', message: done });
    } catch {
      pushToast({ kind: 'error', message: failed });
    }
  };
  const copyLink = (url: string) => void copy(url, t('share.copied'), t('share.copyFailed'));

  const runDuplicate = () =>
    duplicate.mutate(
      { id: deck.id },
      {
        onSuccess: (copied) =>
          pushToast({
            kind: 'success',
            message: t('card.duplicated', { name: copied.name }),
            action: {
              label: t('card.openCopy'),
              onAction: () => void navigate(`/decks/${copied.id}`),
            },
          }),
        onError,
      },
    );
  const runCopyText = () =>
    exportText.mutate(deck.id, {
      onSuccess: (text) => void copy(text, t('card.textCopied'), t('card.textCopyFailed')),
      onError,
    });
  // The card goes away once the list is refreshed, so wait on the promise, not on callbacks.
  const runDelete = async () => {
    setConfirming(false);
    try {
      await remove.mutateAsync();
      pushToast({ kind: 'success', message: t('card.deleted', { name: deck.name }) });
    } catch (failure) {
      onError(failure);
    }
  };

  return (
    <>
      <Popover
        title={t('card.actions', { name: deck.name })}
        trigger={<Icon name="more" size={18} />}
        triggerLabel={t('card.more', { name: deck.name })}
        disabled={offline}
        size="sm"
      >
        {(close) => (
          <div className={styles.cardActions}>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                close();
                runDuplicate();
              }}
            >
              <Icon name="copy" size={16} />
              {t('card.duplicate')}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                close();
                runCopyText();
              }}
            >
              <Icon name="export" size={16} />
              {t('card.copyText')}
            </Button>
            {deck.share && (
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
            )}
            <Button
              variant="ghost"
              size="sm"
              pending={share.isPending}
              onClick={() => {
                if (deck.share) return copyLink(deck.share.url);
                share.mutate(undefined, { onSuccess: (result) => copyLink(result.url), onError });
              }}
            >
              <Icon name="link" size={16} />
              {t('card.copyLink')}
            </Button>
            {deck.share && (
              <Button
                variant="ghost"
                size="sm"
                pending={unshare.isPending}
                onClick={() =>
                  unshare.mutate(undefined, {
                    onSuccess: () => pushToast({ kind: 'success', message: t('share.stopped') }),
                    onError,
                  })
                }
              >
                {t('share.stop')}
              </Button>
            )}
            <Button
              variant="danger"
              size="sm"
              onClick={() => {
                close();
                setConfirming(true);
              }}
            >
              <Icon name="trash" size={16} />
              {t('actions.delete')}
            </Button>
          </div>
        )}
      </Popover>
      <ConfirmDialog
        open={confirming}
        title={t('remove.title', { name: deck.name })}
        message={t('remove.body')}
        confirmLabel={t('remove.confirm')}
        cancelLabel={tCommon('actions.cancel')}
        danger
        onCancel={() => setConfirming(false)}
        onConfirm={() => void runDelete()}
      />
    </>
  );
}
