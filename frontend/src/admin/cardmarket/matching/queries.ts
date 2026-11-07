import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import {
  createCardmarketLink,
  deleteCardmarketLink,
  getCardmarketCandidates,
  ignoreCardmarketProduct,
  listCardmarketIgnored,
  listCardmarketLinks,
  listCardmarketReview,
  listCardmarketUnmatched,
  relinkCardmarketLink,
  unignoreCardmarketProduct,
  type CardmarketLink,
  type CardmarketLinkTarget,
} from '@/api/endpoints';
import { pushToast } from '@/components/ui/toastStore';
import { translateError } from '@/i18n';
import { cardmarketKeys } from '@/admin/cardmarket/queries';
import { cardRef } from './format';
import { useSlotRef } from './parts';

/** Query keys of the workbench, under the Cardmarket ones so a write refreshes them all. */
export const matchingKeys = {
  all: [...cardmarketKeys.all, 'matching'] as const,
  unmatched: (query: string) => [...cardmarketKeys.all, 'matching', 'unmatched', query] as const,
  candidates: (id: number, q: string) =>
    [...cardmarketKeys.all, 'matching', 'candidates', id, q] as const,
  links: (query: string) => [...cardmarketKeys.all, 'matching', 'links', query] as const,
  ignored: [...cardmarketKeys.all, 'matching', 'ignored'] as const,
  review: (query: string) => [...cardmarketKeys.all, 'matching', 'review', query] as const,
};

export const useUnmatched = (query: string) =>
  useQuery({
    queryKey: matchingKeys.unmatched(query),
    queryFn: ({ signal }) => listCardmarketUnmatched(query, signal),
    placeholderData: keepPreviousData,
  });

/** `q` empty asks for the suggested cards; a 1-character `q` is never sent. */
export const useCandidates = (id: number, q: string, enabled = true) =>
  useQuery({
    queryKey: matchingKeys.candidates(id, q),
    queryFn: ({ signal }) => getCardmarketCandidates(id, q, signal),
    enabled: enabled && q.length !== 1,
    placeholderData: keepPreviousData,
  });

export const useLinks = (query: string) =>
  useQuery({
    queryKey: matchingKeys.links(query),
    queryFn: ({ signal }) => listCardmarketLinks(query, signal),
    placeholderData: keepPreviousData,
  });

export const useIgnored = () =>
  useQuery({
    queryKey: matchingKeys.ignored,
    queryFn: ({ signal }) => listCardmarketIgnored(signal),
  });

export const useReview = (query: string) =>
  useQuery({
    queryKey: matchingKeys.review(query),
    queryFn: ({ signal }) => listCardmarketReview(query, signal),
    placeholderData: keepPreviousData,
  });

/** After any write: the lists, the status counters and the load days change. */
export function useRefreshCardmarket() {
  const queryClient = useQueryClient();
  return () => void queryClient.invalidateQueries({ queryKey: cardmarketKeys.all });
}

const targetOf = (link: CardmarketLink): CardmarketLinkTarget => ({
  card: { set_id: link.set_id, card_id: link.card_id },
  foil: link.foil,
});

/**
 * The toasts of the writes, each with an Undo that sends the opposite write: a link is
 * unlinked, an unlink posts the removed link back, a relink goes back to the previous target,
 * an ignore is restored and a restore ignored again.
 */
export function useUndoToasts() {
  const { t, i18n } = useTranslation('admin');
  const refresh = useRefreshCardmarket();
  const slotRef = useSlotRef();

  const undoable = (message: string, undo: () => Promise<unknown>) => {
    refresh();
    pushToast({
      kind: 'success',
      message,
      action: {
        label: t('matching.undo'),
        onAction: () => {
          undo().then(refresh, (error: unknown) => {
            pushToast({ kind: 'error', message: translateError(error, i18n) });
            refresh();
          });
        },
      },
    });
  };

  return {
    /** A card created from a Cardmarket item and linked (CM-c): Undo unlinks, the card stays. */
    createdAndLinked: (link: CardmarketLink) =>
      undoable(t('matching.create.done'), () => deleteCardmarketLink(link.id_product)),
    linked: (name: string, link: CardmarketLink) =>
      undoable(t('matching.linkedTo', { name, ref: cardRef(link.set_id, link.card_id) }), () =>
        deleteCardmarketLink(link.id_product),
      ),
    relinked: (name: string, link: CardmarketLink, previous: CardmarketLink) =>
      undoable(t('matching.relinked', { name, from: slotRef(previous), to: slotRef(link) }), () =>
        relinkCardmarketLink(link.id_product, targetOf(previous)),
      ),
    unlinked: (name: string, link: CardmarketLink) =>
      undoable(t('matching.unlinked', { name }), () =>
        createCardmarketLink(link.id_product, targetOf(link)),
      ),
    ignored: (id: number, name: string) =>
      undoable(t('matching.ignored', { name }), () => unignoreCardmarketProduct(id, name)),
    restored: (id: number, name: string) =>
      undoable(t('matching.restored', { name }), () => ignoreCardmarketProduct(id, name)),
  };
}
