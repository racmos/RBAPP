import type { QueryClient } from '@tanstack/react-query';
import type { i18n as I18n } from 'i18next';
import {
  finalizeAdminImage,
  undoAdminImage,
  uploadAdminCardImage,
  uploadAdminProductImage,
  type AdminCard,
  type AdminImageUpload,
  type AdminProduct,
} from '@/api/endpoints';
import { pushToast } from '@/components/ui/toastStore';
import { translateError } from '@/i18n';
import { formatBytes } from '@/lib/format';

/** How long the Undo of an upload stays (S7: the previous file is deleted after it). */
export const UNDO_MS = 10000;

/** A card or a product an image goes to (F13-h S3, S6). */
export type UploadTarget =
  | { type: 'card'; setId: string; cardId: string; name: string }
  | { type: 'product'; productId: number; name: string };

export type UploadResult = (AdminCard | AdminProduct) & AdminImageUpload;

export const cardTarget = (card: AdminCard): UploadTarget => ({
  type: 'card',
  setId: card.set_id,
  cardId: card.card_id,
  name: card.name,
});

export const productTarget = (product: AdminProduct): UploadTarget => ({
  type: 'product',
  productId: product.id,
  name: product.name,
});

/** One upload through the route of the target (the server resizes and renames it, S4, S5). */
export function sendImage(target: UploadTarget, file: File): Promise<UploadResult> {
  return target.type === 'card'
    ? uploadAdminCardImage(target.setId, target.cardId, file)
    : uploadAdminProductImage(target.productId, file);
}

/** `Saved as ogn_66.webp, 640 × 894 px, 85 KB.` for the edit forms (S11). */
export const resultText = (i18n: I18n, result: AdminImageUpload) =>
  i18n.t('admin:cards.image.result', {
    image: result.image,
    width: result.width,
    height: result.height,
    size: formatBytes(result.bytes),
  });

/**
 * The success toast of a single upload (S3, S7): Undo gives the item its previous image back;
 * once the toast goes away without Undo, the previous file is deleted on the server (which
 * keeps it when a row still names it).
 */
export function announceUpload(
  i18n: I18n,
  queryClient: QueryClient,
  target: UploadTarget,
  result: UploadResult,
): void {
  const previous = result.previous;
  pushToast({
    kind: 'success',
    message: i18n.t('admin:images.uploaded', {
      name: target.name,
      image: result.image,
      width: result.width,
      height: result.height,
      size: formatBytes(result.bytes),
    }),
    duration: UNDO_MS,
    action: {
      label: i18n.t('admin:images.undo'),
      onAction: () => {
        const body =
          target.type === 'card'
            ? {
                type: 'card' as const,
                set_id: target.setId,
                card_id: target.cardId,
                image: result.image,
                previous,
              }
            : {
                type: 'product' as const,
                product_id: target.productId,
                image: result.image,
                previous,
              };
        undoAdminImage(body)
          .then(() => pushToast({ kind: 'success', message: i18n.t('admin:images.undone') }))
          .catch((error: unknown) =>
            pushToast({ kind: 'error', message: translateError(error, i18n) }),
          )
          .finally(() => void queryClient.invalidateQueries({ queryKey: ['admin'] }));
      },
    },
    onExpire: finalizeLater(
      target.type === 'card' ? { type: 'card', setId: target.setId } : { type: 'product' },
      previous,
    ),
  });
}

/**
 * The `onExpire` of an upload toast (S7): delete the previous file on the server, which keeps it
 * when a row still names it. Nothing to do without a previous file.
 */
export function finalizeLater(
  where: { type: 'card'; setId: string } | { type: 'product' },
  previous: string | null,
): (() => void) | undefined {
  if (!previous) return undefined;
  return () => {
    // A failure only leaves an orphan file: `flask images prune-orphans` removes it.
    void finalizeAdminImage({
      type: where.type,
      image: previous,
      ...(where.type === 'card' ? { set_id: where.setId } : {}),
    }).catch(() => undefined);
  };
}
