import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import type { MyProductPatchBody } from '@/api/types';
import { pushToast } from '@/components/ui/toastStore';
import { translateError } from '@/i18n';
import { usePatchProduct } from './queries';

/**
 * Saves the changes of one owned line, one after another (like `useLineSaver` of the
 * collection; products have no `if_updated_at`). A failure shows its translated message and
 * reloads the lines.
 */
export function useProductLineSaver(id: number) {
  const { i18n } = useTranslation('products');
  const client = useQueryClient();
  const patch = usePatchProduct();
  const queue = useRef<Promise<unknown>>(Promise.resolve());

  return useCallback(
    (body: MyProductPatchBody) => {
      const run = async () => {
        try {
          await patch.mutateAsync({ id, body });
        } catch (error) {
          pushToast({ kind: 'error', message: translateError(error, i18n) });
          await client.invalidateQueries({ queryKey: ['me-products'] });
        }
      };
      queue.current = queue.current.then(run, run);
      return queue.current;
    },
    [patch, id, client, i18n],
  );
}
