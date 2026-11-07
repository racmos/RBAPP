import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { ApiError } from '@/api/errors';
import type { CardmarketCandidateCard, CardmarketFoil } from '@/api/endpoints';
import { CardImage } from '@/components/card';
import { translateError } from '@/i18n';
import { cardRef } from './format';
import styles from './MatchingPage.module.css';

type SlotTarget = { set_id: string; card_id: string; foil: CardmarketFoil };

export const slotKey = (foil: CardmarketFoil) => foil ?? 'none';

/** "N", "S" or "None". */
export function useSlotLabel() {
  const { t } = useTranslation('admin');
  return (foil: CardmarketFoil) => t(`matching.slot.${slotKey(foil)}`);
}

/** "OGN-066, slot N". */
export function useSlotRef() {
  const { t } = useTranslation('admin');
  const slot = useSlotLabel();
  return (target: SlotTarget) =>
    t('matching.slotRef', { ref: cardRef(target.set_id, target.card_id), slot: slot(target.foil) });
}

/** What a 409 `already_exists` of a link write says, when it says it in its params. */
export type LinkConflict =
  { field: 'card'; linkedId: number } | { field: 'id_product'; current: SlotTarget };

export function linkConflict(error: unknown): LinkConflict | null {
  if (!(error instanceof ApiError) || error.status !== 409 || error.code !== 'already_exists') {
    return null;
  }
  const params: Record<string, unknown> = error.params ?? {};
  if (params.field === 'card' && typeof params.linked_id_product === 'number') {
    return { field: 'card', linkedId: params.linked_id_product };
  }
  if (
    params.field === 'id_product' &&
    typeof params.set_id === 'string' &&
    typeof params.card_id === 'string'
  ) {
    const foil = params.foil === 'N' || params.foil === 'S' ? params.foil : null;
    return {
      field: 'id_product',
      current: { set_id: params.set_id, card_id: params.card_id, foil },
    };
  }
  return null;
}

/** The text of a failed link: who holds the slot, what the product is linked to, or the error. */
export function useLinkErrorText() {
  const { t, i18n } = useTranslation('admin');
  const slotRef = useSlotRef();
  return (error: unknown, target: SlotTarget) => {
    const conflict = linkConflict(error);
    if (conflict?.field === 'id_product') {
      return t('matching.dialog.productLinked', { target: slotRef(conflict.current) });
    }
    if (conflict?.field === 'card') {
      const taken = t('matching.dialog.slotTaken', {
        target: slotRef(target),
        id: conflict.linkedId,
      });
      const server = error instanceof ApiError ? error.serverMessage : null;
      return server ? `${server} ${taken}` : taken;
    }
    return translateError(error, i18n);
  };
}

/** The image of a candidate card; the API gives only part of a `CardSummary`. */
export function CandidateImage({ card }: { card: CardmarketCandidateCard }) {
  const image = useMemo(
    () => ({
      name: card.name,
      image_src: card.image_src,
      image_thumb_src: null,
      domains: [],
      type: card.type ?? '',
      supertype: null,
      energy: null,
      might: null,
    }),
    [card.name, card.image_src, card.type],
  );
  return <CardImage card={image} size="thumb" className={styles.candidateImage} />;
}
