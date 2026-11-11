import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query';
import {
  addWishlistLine,
  createWishlist,
  deleteWishlist,
  deleteWishlistLine,
  listWishlistLines,
  listWishlists,
  moveWishlistLines,
  patchWishlist,
  patchWishlistLine,
  reorderWishlists,
} from '@/api/endpoints';
import type {
  Wishlist,
  WishlistLine,
  WishlistLineCreateBody,
  WishlistLinePatchBody,
  WishlistLines,
  WishlistMoveBody,
  WishlistPatchBody,
} from '@/api/types';

const STALE_MS = 60 * 1000;
/** The user's lists; the lines of a list live below it: `['wishlists', id, 'lines', q]`. */
export const WISHLISTS_KEY = ['wishlists'] as const;
const ORDER_KEY = ['wishlists', 'order'] as const;
const linesKey = (id: number, q: string) => ['wishlists', id, 'lines', q] as const;

type ListsData = { items: Wishlist[] };

/** The lists in the user's order; the first call of a new user creates the default list. */
export function useWishlists() {
  return useQuery({
    queryKey: WISHLISTS_KEY,
    queryFn: ({ signal }) => listWishlists(signal),
    staleTime: STALE_MS,
  });
}

/** The lines of one list; the previous answer stays on screen only while the search changes. */
export function useWishlistLines(id: number | null, q: string) {
  return useQuery({
    queryKey: linesKey(id ?? 0, q),
    queryFn: ({ signal }) => listWishlistLines(id ?? 0, q, signal),
    enabled: id !== null,
    staleTime: STALE_MS,
    placeholderData: (previous, previousQuery) =>
      previousQuery?.queryKey[1] === id ? previous : undefined,
  });
}

/** Every wishlist write changes the counts of the lists and the lines: refresh both. */
const refreshAll = (client: QueryClient) => client.invalidateQueries({ queryKey: WISHLISTS_KEY });

export function useCreateWishlist() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => createWishlist(name),
    onSuccess: () => refreshAll(client),
  });
}

export function usePatchWishlist() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: WishlistPatchBody }) => patchWishlist(id, body),
    onSuccess: () => refreshAll(client),
  });
}

export function useDeleteWishlist() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => deleteWishlist(id),
    onSuccess: () => refreshAll(client),
  });
}

/** What a line posts back to restore it: the API ignores the read-only keys, these are enough. */
export const lineBody = (line: WishlistLine): WishlistLineCreateBody => ({
  set_id: line.set_id,
  card_id: line.card_id,
  name: line.name,
  foil: line.foil,
  qty: line.qty,
  max_price: line.max_price,
  note: line.note,
});

/**
 * Undo of a list delete: the list again under its name, its lines posted back in their order
 * and the list put back at its place. Returns the new list.
 */
export function useRestoreWishlist() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ deleted, lines }: { deleted: Wishlist; lines: WishlistLine[] }) => {
      const created = await createWishlist(deleted.name);
      for (const line of lines) await addWishlistLine(created.id, lineBody(line));
      const { items } = await listWishlists();
      const ids = items.map((item) => item.id).filter((id) => id !== created.id);
      ids.splice(Math.min(deleted.position - 1, ids.length), 0, created.id);
      if (ids.some((id, index) => items[index]?.id !== id)) await reorderWishlists(ids);
      return created;
    },
    onSettled: () => refreshAll(client),
  });
}

/**
 * Saves the whole order at once. The lists show the new order at once and go back to the
 * previous one when saving fails (as the storage locations do).
 */
export function useReorderWishlists() {
  const client = useQueryClient();
  return useMutation({
    mutationKey: ORDER_KEY,
    mutationFn: (ids: number[]) => reorderWishlists(ids),
    onMutate: async (ids) => {
      await client.cancelQueries({ queryKey: WISHLISTS_KEY, exact: true });
      const previous = client.getQueryData<ListsData>(WISHLISTS_KEY);
      if (previous) {
        const byId = new Map(previous.items.map((item) => [item.id, item]));
        const items = ids.flatMap((id, index) => {
          const item = byId.get(id);
          return item ? [{ ...item, position: index + 1 }] : [];
        });
        client.setQueryData<ListsData>(WISHLISTS_KEY, { items });
      }
      return { previous };
    },
    onError: (_error, _ids, context) => {
      if (context?.previous) client.setQueryData(WISHLISTS_KEY, context.previous);
    },
    onSuccess: ({ items }) => {
      if (client.isMutating({ mutationKey: ORDER_KEY }) <= 1) {
        client.setQueryData<ListsData>(WISHLISTS_KEY, { items });
      }
    },
  });
}

export function useAddWishlistLine() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ listId, body }: { listId: number; body: WishlistLineCreateBody }) =>
      addWishlistLine(listId, body),
    onSuccess: () => refreshAll(client),
  });
}

/** The saved line replaces the cached one at once; the totals come with the refresh. */
export function usePatchWishlistLine() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({
      listId,
      lineId,
      body,
    }: {
      listId: number;
      lineId: number;
      body: WishlistLinePatchBody;
    }) => patchWishlistLine(listId, lineId, body),
    onSuccess: async (saved, { listId }) => {
      client.setQueriesData<WishlistLines>({ queryKey: ['wishlists', listId, 'lines'] }, (data) =>
        data
          ? { ...data, items: data.items.map((item) => (item.id === saved.id ? saved : item)) }
          : data,
      );
      await client.invalidateQueries({ queryKey: ['wishlists', listId, 'lines'] });
    },
  });
}

export function useDeleteWishlistLine() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ listId, lineId }: { listId: number; lineId: number }) =>
      deleteWishlistLine(listId, lineId),
    onSuccess: () => refreshAll(client),
  });
}

export function useMoveWishlistLines() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ listId, body }: { listId: number; body: WishlistMoveBody }) =>
      moveWishlistLines(listId, body),
    onSuccess: () => refreshAll(client),
  });
}
