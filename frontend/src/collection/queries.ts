import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  addCollectionLine,
  deleteCollectionLine,
  keepPlayset,
  listCollection,
  patchCollectionLine,
  splitCollectionLine,
} from '@/api/endpoints';
import type { CollectionAddBody, CollectionParams, CollectionPatchBody } from '@/api/types';
import type { CollectionSplitBody } from '@/api/types';
import { serializeCollectionParams } from './params';

const STALE_MS = 60 * 1000;

/** The collection list for the URL params (F3-g S1). */
export function useCollectionList(params: CollectionParams) {
  const query = serializeCollectionParams(params);
  return useQuery({
    queryKey: ['collection', 'list', query] as const,
    queryFn: ({ signal }) => listCollection(query, signal),
    placeholderData: keepPreviousData,
    staleTime: STALE_MS,
  });
}

/**
 * A write changes the collection list and the owned counts of the catalog, so every mutation
 * refreshes both.
 */
function useRefresh() {
  const client = useQueryClient();
  return async () => {
    await Promise.all([
      client.invalidateQueries({ queryKey: ['collection'] }),
      client.invalidateQueries({ queryKey: ['cards'] }),
    ]);
  };
}

export function useAddLine() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (body: CollectionAddBody) => addCollectionLine(body),
    onSuccess: refresh,
  });
}

export function usePatchLine() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: CollectionPatchBody }) =>
      patchCollectionLine(id, body),
    onSuccess: refresh,
  });
}

export function useDeleteLine() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (id: number) => deleteCollectionLine(id),
    onSuccess: refresh,
  });
}

export function useSplitLine() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: CollectionSplitBody }) =>
      splitCollectionLine(id, body),
    onSuccess: refresh,
  });
}

export function useKeepPlayset() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (body: { set_id: string; card_id: string; keep: boolean }) => keepPlayset(body),
    onSuccess: refresh,
  });
}
