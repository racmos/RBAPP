import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createLocation,
  deleteLocation,
  getLineLocations,
  listLocations,
  moveLineLocations,
  patchLocation,
  putLineLocations,
  reorderLocations,
  suggestLocationCode,
} from '@/api/endpoints';
import type {
  LineLocationMove,
  LineLocations,
  LocationBump,
  LocationCreateBody,
  LocationList,
  LocationPatchBody,
} from '@/api/types';

const STALE_MS = 60 * 1000;
export const LOCATIONS_KEY = ['locations', 'list'] as const;
const ORDER_KEY = ['locations', 'order'] as const;
const lineKey = (lineId: number) => ['locations', 'line', lineId] as const;

/** The user's locations in their order and the unassigned copies (F16-b S1). */
export function useLocations() {
  return useQuery({
    queryKey: LOCATIONS_KEY,
    queryFn: ({ signal }) => listLocations(signal),
    staleTime: STALE_MS,
  });
}

/**
 * A location write changes the location counts and the location summary of the collection lines
 * (codes, order, copies), so every write refreshes both.
 */
function useRefresh() {
  const client = useQueryClient();
  return async () => {
    await Promise.all([
      client.invalidateQueries({ queryKey: ['locations'] }),
      client.invalidateQueries({ queryKey: ['collection'] }),
    ]);
  };
}

export function useCreateLocation() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (body: LocationCreateBody) => createLocation(body),
    onSuccess: refresh,
  });
}

export function usePatchLocation() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: LocationPatchBody }) => patchLocation(id, body),
    onSuccess: refresh,
  });
}

export function useDeleteLocation() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (id: number) => deleteLocation(id),
    onSuccess: refresh,
  });
}

/** The suggested code (F16-R1a): `bump` the part that starts a new one, after `after`. */
export function useSuggestedCode() {
  return useQuery({
    queryKey: ['locations', 'next-code'] as const,
    queryFn: ({ signal }) => suggestLocationCode('pack', undefined, signal),
    staleTime: 0,
    retry: false,
  });
}

/** A GET on demand (the block, row and pack buttons): a mutation gives it a pending state. */
export function useBumpCode() {
  return useMutation({
    mutationFn: ({ bump, after }: { bump: LocationBump; after?: string }) =>
      suggestLocationCode(bump, after),
  });
}

/**
 * Saves the whole order at once (F16-R2). The list shows the new order at once and goes back to
 * the previous one when saving fails; the answer is the server's order, kept unless another
 * reorder is already on its way.
 */
export function useReorderLocations() {
  const client = useQueryClient();
  return useMutation({
    mutationKey: ORDER_KEY,
    mutationFn: (ids: number[]) => reorderLocations(ids),
    onMutate: async (ids) => {
      await client.cancelQueries({ queryKey: LOCATIONS_KEY });
      const previous = client.getQueryData<LocationList>(LOCATIONS_KEY);
      if (previous) {
        const byId = new Map(previous.items.map((item) => [item.id, item]));
        const items = ids.flatMap((id, index) => {
          const item = byId.get(id);
          return item ? [{ ...item, position: index + 1 }] : [];
        });
        client.setQueryData<LocationList>(LOCATIONS_KEY, { ...previous, items });
      }
      return { previous };
    },
    onError: (_error, _ids, context) => {
      if (context?.previous) client.setQueryData(LOCATIONS_KEY, context.previous);
    },
    onSuccess: async ({ items }) => {
      if (client.isMutating({ mutationKey: ORDER_KEY }) <= 1) {
        client.setQueryData<LocationList>(LOCATIONS_KEY, (current) =>
          current ? { ...current, items } : current,
        );
      }
      // the lines list their locations in the user's order
      await client.invalidateQueries({ queryKey: ['collection'] });
    },
  });
}

/** Every location of one collection line (`GET /collection/:id/locations`), on demand. */
export function useLineLocations(lineId: number, enabled: boolean) {
  return useQuery({
    queryKey: lineKey(lineId),
    queryFn: ({ signal }) => getLineLocations(lineId, signal),
    enabled,
  });
}

function useLineWrite<V>(write: (variables: V & { lineId: number }) => Promise<LineLocations>) {
  const client = useQueryClient();
  const refresh = useRefresh();
  return useMutation({
    mutationFn: write,
    onSuccess: async (result, { lineId }) => {
      client.setQueryData(lineKey(lineId), result);
      await refresh();
    },
  });
}

/** Moves copies of a line between two places; `null` is unassigned (F16-R4). */
export function useMoveLineLocations() {
  return useLineWrite<{ body: LineLocationMove }>(({ lineId, body }) =>
    moveLineLocations(lineId, body),
  );
}

/** Replaces the whole assignment of a line (F16-R4). */
export function usePutLineLocations() {
  return useLineWrite<{ assignments: { location_id: number; qty: number }[] }>(
    ({ lineId, assignments }) => putLineLocations(lineId, assignments),
  );
}
