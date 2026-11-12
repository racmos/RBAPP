import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  type InfiniteData,
} from '@tanstack/react-query';
import { listWishlistAlertLists, listWishlistAlerts, readWishlistAlerts } from '@/api/endpoints';
import type { WishlistAlerts } from '@/api/types';
import { useOffline } from '@/auth';

const STALE_MS = 60 * 1000;
const PER_PAGE = 25;

/**
 * Every alerts query lives below `['wishlist-alerts']`: the badge (`'badge'`), the screen's pages
 * (`'list', unread`) and the lists of one alert (`id, 'lists'`).
 */
export const ALERTS_KEY = ['wishlist-alerts'] as const;
const BADGE_KEY = ['wishlist-alerts', 'badge'] as const;
const LIST_KEY = ['wishlist-alerts', 'list'] as const;

/**
 * The unread alerts of the user for the tab badges: `GET /wishlist-alerts?unread=true&per_page=25`
 * read for its `meta.unread_count` (one cheap call shared by both tabs). Undefined while loading
 * and on failure, so no badge shows then.
 */
export function useUnreadAlertCount(): number | undefined {
  const query = useQuery({
    queryKey: BADGE_KEY,
    queryFn: ({ signal }) => listWishlistAlerts({ unread: true, perPage: PER_PAGE }, signal),
    staleTime: STALE_MS,
    retry: false,
    select: (data) => data.meta.unread_count,
  });
  return query.isError ? undefined : query.data;
}

/**
 * The unread count the tabs show as a badge, or undefined: no badge while loading, on failure,
 * offline or when nothing is unread.
 */
export function useAlertsBadge(): number | undefined {
  const count = useUnreadAlertCount();
  const offline = useOffline();
  return !offline && count ? count : undefined;
}

/** The alerts newest first, 25 a page ("Show more" loads the next one). */
export function useWishlistAlerts(unread: boolean) {
  return useInfiniteQuery({
    queryKey: [...LIST_KEY, unread],
    queryFn: ({ pageParam, signal }) =>
      listWishlistAlerts({ unread, page: pageParam, perPage: PER_PAGE }, signal),
    initialPageParam: 1,
    getNextPageParam: (last) => (last.meta.page < last.meta.pages ? last.meta.page + 1 : undefined),
    staleTime: STALE_MS,
  });
}

/** The lists that hold an alert's card now; read when the alert is expanded. */
export function useAlertLists(id: number, enabled: boolean) {
  return useQuery({
    queryKey: [...ALERTS_KEY, id, 'lists'],
    queryFn: ({ signal }) => listWishlistAlertLists(id, signal),
    enabled,
    staleTime: STALE_MS,
  });
}

/**
 * Marks alerts read: `ids`, or every unread one when `ids` is absent. The loaded pages show it at
 * once (an alert read while open stays on screen even under "Unread only"); the badge is read
 * again, and marking all also reloads the pages.
 */
export function useMarkAlertsRead() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (ids?: number[]) => readWishlistAlerts(ids),
    onSuccess: async ({ marked }, ids) => {
      const now = new Date().toISOString();
      const hit = (id: number) => !ids || ids.includes(id);
      client.setQueriesData<InfiniteData<WishlistAlerts>>({ queryKey: LIST_KEY }, (data) =>
        data
          ? {
              ...data,
              pages: data.pages.map((page) => ({
                items: page.items.map((item) =>
                  item.read_at === null && hit(item.id) ? { ...item, read_at: now } : item,
                ),
                meta: { ...page.meta, unread_count: Math.max(0, page.meta.unread_count - marked) },
              })),
            }
          : data,
      );
      await client.invalidateQueries({ queryKey: BADGE_KEY });
      if (!ids) await client.invalidateQueries({ queryKey: LIST_KEY });
    },
  });
}
