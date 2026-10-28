import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import type { CollectionLine, CollectionPatchBody } from '@/api/types';
import { pushToast } from '@/components/ui/toastStore';
import { translateError } from '@/i18n';
import { usePatchLine } from './queries';

/**
 * Saves changes of one line (F3-g S6). Each save carries the change time the server last told us
 * (`if_updated_at`) and they run one after another, so a quick second edit does not collide with
 * the first one. A failure shows its translated message and reloads the list: after a `stale_line`
 * the screen shows what the other window saved.
 */
export function useLineSaver(line: CollectionLine) {
  const { t, i18n } = useTranslation('collection');
  const client = useQueryClient();
  const patch = usePatchLine();
  const stamp = useRef(line.updated_at);
  const queue = useRef<Promise<unknown>>(Promise.resolve());

  useEffect(() => {
    stamp.current = line.updated_at;
  }, [line.updated_at]);

  return useCallback(
    (body: CollectionPatchBody) => {
      const run = async () => {
        try {
          const saved = await patch.mutateAsync({
            id: line.id,
            body: { ...body, if_updated_at: stamp.current },
          });
          stamp.current = saved.updated_at;
          pushToast({ kind: 'success', message: t('line.saved'), duration: 1500 });
        } catch (error) {
          pushToast({ kind: 'error', message: translateError(error, i18n) });
          await client.invalidateQueries({ queryKey: ['collection'] });
        }
      };
      queue.current = queue.current.then(run, run);
      return queue.current;
    },
    [patch, line.id, client, i18n, t],
  );
}
